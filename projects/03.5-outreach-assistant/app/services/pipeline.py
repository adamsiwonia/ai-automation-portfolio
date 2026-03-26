from __future__ import annotations

import sqlite3
from collections import Counter
from dataclasses import dataclass
from typing import Any

from app.core.config import Settings
from app.core.enums import LeadClassification
from app.repositories.leads import (
    LeadSnapshot,
    get_original_subject_for_lead,
    insert_draft_if_changed,
    list_lead_snapshots,
    list_sync_candidates,
    mark_synced,
    upsert_lead_and_contact,
    upsert_outreach_item,
)
from app.services.classification import classify_lead
from app.services.drafting import build_outreach_draft
from app.services.normalization import normalize_sheet_row
from app.services.sheets import GoogleSheetsClient, SheetRowUpdate

READY_CLASSIFICATIONS = {
    LeadClassification.FIRST_TOUCH_READY,
    LeadClassification.FOLLOW_UP_READY,
}


@dataclass(frozen=True)
class DuplicateDecision:
    duplicate_flag: bool
    duplicate_type: str | None
    duplicate_of_lead_id: int | None
    duplicate_reason: str | None

    @property
    def is_hard_duplicate(self) -> bool:
        return self.duplicate_type == "HARD"


def _normalize_key(value: str | None) -> str | None:
    if not value:
        return None
    normalized = value.strip().lower()
    return normalized or None


def _selected_contact_key(snapshot: LeadSnapshot) -> str | None:
    return _normalize_key(
        snapshot.email or snapshot.contact_form_url or snapshot.raw_contact_value
    )


def _email_domain(email: str | None) -> str | None:
    normalized = _normalize_key(email)
    if not normalized or "@" not in normalized:
        return None
    _, domain = normalized.rsplit("@", 1)
    return domain or None


def _detect_duplicates(snapshots: list[LeadSnapshot]) -> dict[int, DuplicateDecision]:
    seen_email: dict[str, int] = {}
    seen_contact_form: dict[str, int] = {}
    seen_selected_contact: dict[str, int] = {}
    seen_domain: dict[str, tuple[int, str]] = {}

    decisions: dict[int, DuplicateDecision] = {}

    for snapshot in snapshots:
        lead_id = snapshot.lead_id
        email_key = _normalize_key(snapshot.email)
        contact_form_key = _normalize_key(snapshot.contact_form_url)
        selected_contact_key = _selected_contact_key(snapshot)

        hard_duplicate_of: int | None = None
        hard_duplicate_reason: str | None = None

        if email_key:
            existing = seen_email.get(email_key)
            if existing and existing != lead_id:
                hard_duplicate_of = existing
                hard_duplicate_reason = "Hard duplicate: same normalized email address."
            else:
                seen_email[email_key] = lead_id

        if not hard_duplicate_reason and contact_form_key:
            existing = seen_contact_form.get(contact_form_key)
            if existing and existing != lead_id:
                hard_duplicate_of = existing
                hard_duplicate_reason = "Hard duplicate: same contact form URL."
            else:
                seen_contact_form[contact_form_key] = lead_id

        if not hard_duplicate_reason and selected_contact_key:
            existing = seen_selected_contact.get(selected_contact_key)
            if existing and existing != lead_id:
                hard_duplicate_of = existing
                hard_duplicate_reason = "Hard duplicate: same selected contact value."
            elif selected_contact_key not in seen_selected_contact:
                seen_selected_contact[selected_contact_key] = lead_id
        elif selected_contact_key and selected_contact_key not in seen_selected_contact:
            seen_selected_contact[selected_contact_key] = lead_id

        soft_duplicate_of: int | None = None
        soft_duplicate_reason: str | None = None
        domain = _email_domain(email_key)
        if domain and not hard_duplicate_reason:
            first_for_domain = seen_domain.get(domain)
            if not first_for_domain:
                seen_domain[domain] = (lead_id, email_key or "")
            else:
                existing_lead_id, existing_email = first_for_domain
                if existing_lead_id != lead_id and existing_email != (email_key or ""):
                    soft_duplicate_of = existing_lead_id
                    soft_duplicate_reason = (
                        "Soft duplicate: same email domain with different email address."
                    )

        if hard_duplicate_reason:
            decisions[lead_id] = DuplicateDecision(
                duplicate_flag=True,
                duplicate_type="HARD",
                duplicate_of_lead_id=hard_duplicate_of,
                duplicate_reason=hard_duplicate_reason,
            )
            continue

        if soft_duplicate_reason:
            decisions[lead_id] = DuplicateDecision(
                duplicate_flag=True,
                duplicate_type="SOFT",
                duplicate_of_lead_id=soft_duplicate_of,
                duplicate_reason=soft_duplicate_reason,
            )
            continue

        decisions[lead_id] = DuplicateDecision(
            duplicate_flag=False,
            duplicate_type=None,
            duplicate_of_lead_id=None,
            duplicate_reason=None,
        )

    return decisions


def import_sheet_rows(
    conn: sqlite3.Connection,
    *,
    settings: Settings,
    sheet_name: str | None = None,
) -> dict[str, int]:
    client = GoogleSheetsClient(settings)
    source_sheet = sheet_name or settings.google_sheet_name
    rows = client.fetch_rows(source_sheet)

    stats = {
        "imported": 0,
        "valid_email": 0,
        "contact_form": 0,
        "malformed": 0,
    }

    for row_number, row in rows:
        normalized = normalize_sheet_row(
            row,
            settings=settings,
            source_sheet=source_sheet,
            source_row_number=row_number,
        )
        upsert_lead_and_contact(conn, normalized)
        stats["imported"] += 1
        if normalized.email:
            stats["valid_email"] += 1
        elif normalized.contact_form_url:
            stats["contact_form"] += 1
        elif normalized.malformed_contact_value:
            stats["malformed"] += 1

    conn.commit()
    return stats


def classify_and_generate(
    conn: sqlite3.Connection,
) -> dict[str, Any]:
    snapshots = list_lead_snapshots(conn)
    duplicate_decisions = _detect_duplicates(snapshots)
    classification_counts: Counter[str] = Counter()
    drafts_created = 0
    drafts_reused = 0

    for snapshot in snapshots:
        existing_stage = max(0, int(snapshot.existing_follow_up_stage or 0))
        target_follow_up_stage = existing_stage

        duplicate_decision = duplicate_decisions.get(
            snapshot.lead_id,
            DuplicateDecision(
                duplicate_flag=False,
                duplicate_type=None,
                duplicate_of_lead_id=None,
                duplicate_reason=None,
            ),
        )

        classification, reason = classify_lead(
            source_status=snapshot.source_status,
            human_response=snapshot.human_response,
            email=snapshot.email,
            contact_form_url=snapshot.contact_form_url,
            malformed_contact_value=snapshot.malformed_value,
            last_contacted_at=snapshot.last_contacted_at,
            follow_up_due_at=snapshot.follow_up_due_at,
        )

        if classification == LeadClassification.FIRST_TOUCH_READY:
            target_follow_up_stage = 0
        elif classification == LeadClassification.FOLLOW_UP_READY:
            if existing_stage >= 2:
                classification = LeadClassification.DONE
                reason = "Follow-up limit reached (max stage 2)."
                target_follow_up_stage = existing_stage
            else:
                target_follow_up_stage = existing_stage + 1

        if duplicate_decision.is_hard_duplicate and classification in READY_CLASSIFICATIONS:
            classification = LeadClassification.DONE
            reason = (
                "Hard duplicate blocked from outreach. "
                f"{duplicate_decision.duplicate_reason or ''}"
            ).strip()
            target_follow_up_stage = existing_stage
        elif duplicate_decision.duplicate_flag and duplicate_decision.duplicate_reason:
            reason = f"{reason} {duplicate_decision.duplicate_reason}".strip()

        draft_seed = (
            f"{snapshot.source_sheet}:{snapshot.source_row_number}:"
            f"{snapshot.company_name}:{snapshot.segment or ''}:{snapshot.angle or ''}:"
            f"{target_follow_up_stage}"
        )
        original_subject = (
            get_original_subject_for_lead(conn, lead_id=snapshot.lead_id)
            if classification == LeadClassification.FOLLOW_UP_READY
            else None
        )
        draft = build_outreach_draft(
            classification=classification,
            company_name=snapshot.company_name,
            contact_name=snapshot.contact_name,
            segment=snapshot.segment,
            notes=snapshot.notes,
            angle=snapshot.angle,
            follow_up_stage=target_follow_up_stage,
            original_subject=original_subject,
            seed_text=draft_seed,
        )

        classification_counts[classification.value] += 1
        outreach_item_id = upsert_outreach_item(
            conn,
            lead_id=snapshot.lead_id,
            contact_id=snapshot.contact_id,
            classification=classification,
            reason=reason,
            duplicate_flag=duplicate_decision.duplicate_flag,
            duplicate_type=duplicate_decision.duplicate_type,
            duplicate_of_lead_id=duplicate_decision.duplicate_of_lead_id,
            duplicate_reason=duplicate_decision.duplicate_reason,
            template_variant=draft.template_variant if draft else None,
            opener_variant=draft.opener_variant if draft else None,
            personalization_used=draft.personalization_used if draft else False,
            follow_up_stage=target_follow_up_stage,
        )
        if draft:
            _, created = insert_draft_if_changed(
                conn,
                outreach_item_id=outreach_item_id,
                draft=draft,
            )
            if created:
                drafts_created += 1
            else:
                drafts_reused += 1

    conn.commit()
    return {
        "processed": len(snapshots),
        "classifications": dict(classification_counts),
        "drafts_created": drafts_created,
        "drafts_reused": drafts_reused,
    }


def sync_outputs_to_sheet(
    conn: sqlite3.Connection,
    *,
    settings: Settings,
    sheet_name: str | None = None,
    only_selected: bool = True,
    limit: int = 200,
) -> dict[str, int]:
    candidates = list_sync_candidates(
        conn,
        only_selected=only_selected,
        limit=limit,
    )
    if not candidates:
        return {"rows": 0, "cells": 0, "drafts": 0}

    updates: list[SheetRowUpdate] = []
    outreach_ids: list[int] = []
    draft_ids: list[int] = []

    for candidate in candidates:
        updates.append(
            SheetRowUpdate(
                row_number=int(candidate["source_row_number"]),
                values={
                    settings.sync_lead_type_column: candidate["lead_type"],
                    settings.sync_assistant_status_column: candidate["assistant_status"],
                    settings.sync_selected_contact_column: candidate["selected_contact"],
                    settings.sync_draft_type_column: candidate["draft_type"],
                    settings.sync_draft_subject_column: candidate["subject"],
                    settings.sync_draft_body_column: candidate["body"],
                    settings.sync_personalization_note_column: candidate[
                        "personalization_note"
                    ],
                    settings.sync_last_processed_at_column: candidate["last_processed_at"],
                    settings.sync_error_flag_column: candidate["error_flag"],
                    settings.sync_duplicate_flag_column: candidate["duplicate_flag"],
                    settings.sync_duplicate_type_column: candidate["duplicate_type"],
                    settings.sync_duplicate_of_column: candidate["duplicate_of"],
                    settings.sync_duplicate_reason_column: candidate["duplicate_reason"],
                },
            )
        )
        outreach_ids.append(int(candidate["outreach_item_id"]))
        if candidate["draft_id"] is not None:
            draft_ids.append(int(candidate["draft_id"]))

    client = GoogleSheetsClient(settings)
    cells_written = client.batch_update_rows(
        updates=updates,
        sheet_name=sheet_name or settings.google_sheet_name,
    )

    mark_synced(conn, outreach_item_ids=outreach_ids, draft_ids=draft_ids)
    conn.commit()

    return {"rows": len(updates), "cells": cells_written, "drafts": len(draft_ids)}


def run_full_pipeline(
    conn: sqlite3.Connection,
    *,
    settings: Settings,
    sheet_name: str | None = None,
    sync: bool = True,
    only_selected_sync: bool = True,
) -> dict[str, Any]:
    import_stats = import_sheet_rows(conn, settings=settings, sheet_name=sheet_name)
    process_stats = classify_and_generate(conn)

    sync_stats = {"rows": 0, "cells": 0, "drafts": 0}
    if sync:
        sync_stats = sync_outputs_to_sheet(
            conn,
            settings=settings,
            sheet_name=sheet_name,
            only_selected=only_selected_sync,
        )

    return {
        "import": import_stats,
        "process": process_stats,
        "sync": sync_stats,
    }
