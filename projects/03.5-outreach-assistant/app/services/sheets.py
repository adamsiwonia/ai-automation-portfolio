from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.core.config import Settings

GOOGLE_SHEETS_SCOPE = "https://www.googleapis.com/auth/spreadsheets"


@dataclass(frozen=True)
class SheetRowUpdate:
    row_number: int
    values: dict[str, str]


class GoogleSheetsClient:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._service = None

    def _get_service(self) -> Any:
        if self._service is not None:
            return self._service

        if not self.settings.google_credentials_path:
            raise RuntimeError(
                "GOOGLE_APPLICATION_CREDENTIALS is required for Sheets import/sync."
            )
        if not self.settings.google_spreadsheet_id:
            raise RuntimeError("GOOGLE_SPREADSHEET_ID is required for Sheets import/sync.")

        from google.oauth2.service_account import Credentials
        from googleapiclient.discovery import build

        credentials = Credentials.from_service_account_file(
            str(self.settings.google_credentials_path),
            scopes=[GOOGLE_SHEETS_SCOPE],
        )
        self._service = build("sheets", "v4", credentials=credentials)
        return self._service

    def fetch_rows(self, sheet_name: str | None = None) -> list[tuple[int, dict[str, str]]]:
        target_sheet = sheet_name or self.settings.google_sheet_name
        service = self._get_service()

        response = (
            service.spreadsheets()
            .values()
            .get(
                spreadsheetId=self.settings.google_spreadsheet_id,
                range=f"{target_sheet}!A1:ZZ",
            )
            .execute()
        )

        values = response.get("values", [])
        if not values:
            return []

        headers = [str(h).strip() for h in values[0]]
        rows: list[tuple[int, dict[str, str]]] = []

        for row_number, row_values in enumerate(values[1:], start=2):
            row_map: dict[str, str] = {}
            for column_index, header in enumerate(headers):
                value = row_values[column_index] if column_index < len(row_values) else ""
                row_map[header] = str(value).strip()
            rows.append((row_number, row_map))

        return rows

    def _fetch_headers(self, sheet_name: str) -> list[str]:
        service = self._get_service()
        response = (
            service.spreadsheets()
            .values()
            .get(
                spreadsheetId=self.settings.google_spreadsheet_id,
                range=f"{sheet_name}!1:1",
            )
            .execute()
        )
        values = response.get("values", [])
        if not values:
            return []
        return [str(h).strip() for h in values[0]]

    def ensure_columns(self, sheet_name: str, expected_columns: list[str]) -> list[str]:
        headers = self._fetch_headers(sheet_name)
        missing = [column for column in expected_columns if column not in headers]
        if not missing:
            return headers

        updated_headers = [*headers, *missing]
        service = self._get_service()
        (
            service.spreadsheets()
            .values()
            .update(
                spreadsheetId=self.settings.google_spreadsheet_id,
                range=f"{sheet_name}!A1",
                valueInputOption="RAW",
                body={"values": [updated_headers]},
            )
            .execute()
        )
        return updated_headers

    def batch_update_rows(
        self,
        *,
        updates: list[SheetRowUpdate],
        sheet_name: str | None = None,
    ) -> int:
        if not updates:
            return 0

        target_sheet = sheet_name or self.settings.google_sheet_name
        expected_columns = list(
            {
                column_name
                for update in updates
                for column_name in update.values.keys()
            }
        )
        headers = self.ensure_columns(target_sheet, expected_columns)
        header_to_index = {name: index for index, name in enumerate(headers, start=1)}

        payload_data = []
        for update in updates:
            for column_name, value in update.values.items():
                if column_name not in header_to_index:
                    continue
                column_index = header_to_index[column_name]
                cell_ref = f"{_column_number_to_letter(column_index)}{update.row_number}"
                payload_data.append(
                    {
                        "range": f"{target_sheet}!{cell_ref}",
                        "values": [[value]],
                    }
                )

        if not payload_data:
            return 0

        service = self._get_service()
        (
            service.spreadsheets()
            .values()
            .batchUpdate(
                spreadsheetId=self.settings.google_spreadsheet_id,
                body={"valueInputOption": "RAW", "data": payload_data},
            )
            .execute()
        )
        return len(payload_data)


def _column_number_to_letter(column_number: int) -> str:
    letters = ""
    current = column_number
    while current > 0:
        current, remainder = divmod(current - 1, 26)
        letters = chr(65 + remainder) + letters
    return letters
