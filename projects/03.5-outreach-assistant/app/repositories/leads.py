from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from typing import Any

from app.core.enums import LeadClassification
from app.database.db import utc_now
from app.services.drafting import DraftContent
from app.services.normalization import NormalizedLeadRow


@dataclass(frozen=True)
class LeadSnapshot:
    lead_id: int
    source_sheet: str
    source_row_number: int
    company_name: str
    website: str | None
    notes: str | None
    segment: str | None
    angle: str | None
    source_status: str | None
    human_response: str | None
    last_contacted_at: str | None
    follow_up_due_at: str | None
    existing_follow_up_stage: int
    contact_id: int | None
    contact_name: str | None
    raw_contact_value: str | None
    email: str | None
    contact_form_url: str | None
    malformed_value: str | None


@dataclass(frozen=True)
class GmailDraftCandidate:
    outreach_item_id: int
    source_sheet: str
    source_row_number: int
    classification: str
    recipient: str
    subject: str
    body: str
    draft_record_id: int
    existing_gmail_draft_id: str | None


def _has_text(value: str | None) -> bool:
    return bool(value and value.strip())


def upsert_lead_and_contact(
    conn: sqlite3.Connection,
    row: NormalizedLeadRow,
) -> tuple[int, int | None]:
    now = utc_now()
    existing = conn.execute(
        """
        SELECT id, notes, human_response
        FROM leads
        WHERE source_sheet = ? AND source_row_number = ?
        """,
        (row.source_sheet, row.source_row_number),
    ).fetchone()

    if existing:
        lead_id = int(existing["id"])
        notes_value = existing["notes"] if _has_text(existing["notes"]) else row.notes
        human_response_value = (
            existing["human_response"]
            if _has_text(existing["human_response"])
            else row.human_response
        )
        conn.execute(
            """
            UPDATE leads
            SET external_id = ?,
                company_name = ?,
                website = ?,
                notes = ?,
                segment = ?,
                angle = ?,
                human_response = ?,
                source_status = ?,
                raw_contact_name = ?,
                raw_contact_value = ?,
                last_contacted_at = ?,
                follow_up_due_at = ?,
                updated_at = ?
            WHERE id = ?
            """,
            (
                row.external_id,
                row.company_name,
                row.website,
                notes_value,
                row.segment,
                row.angle,
                human_response_value,
                row.source_status,
                row.contact_name,
                row.raw_contact_value,
                row.last_contacted_at,
                row.follow_up_due_at,
                now,
                lead_id,
            ),
        )
    else:
        cursor = conn.execute(
            """
            INSERT INTO leads (
                external_id,
                source_sheet,
                source_row_number,
                company_name,
                website,
                notes,
                segment,
                angle,
                human_response,
                source_status,
                raw_contact_name,
                raw_contact_value,
                last_contacted_at,
                follow_up_due_at,
                created_at,
                updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                row.external_id,
                row.source_sheet,
                row.source_row_number,
                row.company_name,
                row.website,
                row.notes,
                row.segment,
                row.angle,
                row.human_response,
                row.source_status,
                row.contact_name,
                row.raw_contact_value,
                row.last_contacted_at,
                row.follow_up_due_at,
                now,
                now,
            ),
        )
        lead_id = int(cursor.lastrowid)

    existing_contact = conn.execute(
        "SELECT id FROM contacts WHERE lead_id = ?",
        (lead_id,),
    ).fetchone()

    if existing_contact:
        conn.execute(
            """
            UPDATE contacts
            SET full_name = ?,
                raw_value = ?,
                email = ?,
                contact_form_url = ?,
                malformed_value = ?,
                channel = ?,
                updated_at = ?
            WHERE lead_id = ?
            """,
            (
                row.contact_name,
                row.raw_contact_value,
                row.email,
                row.contact_form_url,
                row.malformed_contact_value,
                row.contact_channel,
                now,
                lead_id,
            ),
        )
        contact_id = int(existing_contact["id"])
    else:
        cursor = conn.execute(
            """
            INSERT INTO contacts (
                lead_id,
                full_name,
                raw_value,
                email,
                contact_form_url,
                malformed_value,
                channel,
                created_at,
                updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                lead_id,
                row.contact_name,
                row.raw_contact_value,
                row.email,
                row.contact_form_url,
                row.malformed_contact_value,
                row.contact_channel,
                now,
                now,
            ),
        )
        contact_id = int(cursor.lastrowid)

    return lead_id, contact_id


def list_lead_snapshots(conn: sqlite3.Connection) -> list[LeadSnapshot]:
    rows = conn.execute(
        """
        SELECT
            l.id AS lead_id,
            l.source_sheet,
            l.source_row_number,
            l.company_name,
            l.website,
            l.notes,
            l.segment,
            l.angle,
            l.source_status,
            l.human_response,
            l.last_contacted_at,
            l.follow_up_due_at,
            COALESCE(o.follow_up_stage, 0) AS existing_follow_up_stage,
            c.id AS contact_id,
            c.full_name AS contact_name,
            c.raw_value AS raw_contact_value,
            c.email,
            c.contact_form_url,
            c.malformed_value
        FROM leads l
        LEFT JOIN outreach_items o ON o.lead_id = l.id
        LEFT JOIN contacts c ON c.lead_id = l.id
        ORDER BY l.id ASC
        """
    ).fetchall()

    return [
        LeadSnapshot(
            lead_id=int(row["lead_id"]),
            source_sheet=row["source_sheet"],
            source_row_number=int(row["source_row_number"]),
            company_name=row["company_name"],
            website=row["website"],
            notes=row["notes"],
            segment=row["segment"],
            angle=row["angle"],
            source_status=row["source_status"],
            human_response=row["human_response"],
            last_contacted_at=row["last_contacted_at"],
            follow_up_due_at=row["follow_up_due_at"],
            existing_follow_up_stage=int(row["existing_follow_up_stage"] or 0),
            contact_id=int(row["contact_id"]) if row["contact_id"] is not None else None,
            contact_name=row["contact_name"],
            raw_contact_value=row["raw_contact_value"],
            email=row["email"],
            contact_form_url=row["contact_form_url"],
            malformed_value=row["malformed_value"],
        )
        for row in rows
    ]


def upsert_outreach_item(
    conn: sqlite3.Connection,
    *,
    lead_id: int,
    contact_id: int | None,
    classification: LeadClassification,
    reason: str,
    duplicate_flag: bool = False,
    duplicate_type: str | None = None,
    duplicate_of_lead_id: int | None = None,
    duplicate_reason: str | None = None,
    template_variant: str | None = None,
    opener_variant: str | None = None,
    personalization_used: bool = False,
    follow_up_stage: int = 0,
) -> int:
    now = utc_now()
    existing = conn.execute(
        "SELECT id FROM outreach_items WHERE lead_id = ?",
        (lead_id,),
    ).fetchone()

    pipeline_state = "DONE" if classification == LeadClassification.DONE else "PENDING"

    if existing:
        outreach_item_id = int(existing["id"])
        conn.execute(
            """
            UPDATE outreach_items
            SET contact_id = ?,
                classification = ?,
                reason = ?,
                duplicate_flag = ?,
                duplicate_type = ?,
                duplicate_of_lead_id = ?,
                duplicate_reason = ?,
                template_variant = ?,
                opener_variant = ?,
                personalization_used = ?,
                follow_up_stage = ?,
                pipeline_state = ?,
                updated_at = ?
            WHERE id = ?
            """,
            (
                contact_id,
                classification.value,
                reason,
                1 if duplicate_flag else 0,
                duplicate_type,
                duplicate_of_lead_id,
                duplicate_reason,
                template_variant,
                opener_variant,
                1 if personalization_used else 0,
                max(0, follow_up_stage),
                pipeline_state,
                now,
                outreach_item_id,
            ),
        )
        return outreach_item_id

    cursor = conn.execute(
        """
        INSERT INTO outreach_items (
            lead_id,
            contact_id,
            classification,
            reason,
            duplicate_flag,
            duplicate_type,
            duplicate_of_lead_id,
            duplicate_reason,
            template_variant,
            opener_variant,
            personalization_used,
            follow_up_stage,
            pipeline_state,
            created_at,
            updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            lead_id,
            contact_id,
            classification.value,
            reason,
            1 if duplicate_flag else 0,
            duplicate_type,
            duplicate_of_lead_id,
            duplicate_reason,
            template_variant,
            opener_variant,
            1 if personalization_used else 0,
            max(0, follow_up_stage),
            pipeline_state,
            now,
            now,
        ),
    )
    return int(cursor.lastrowid)


def insert_draft_if_changed(
    conn: sqlite3.Connection,
    *,
    outreach_item_id: int,
    draft: DraftContent,
) -> tuple[int, bool]:
    latest = conn.execute(
        """
        SELECT id, subject, body, generator, version
        FROM drafts
        WHERE outreach_item_id = ?
        ORDER BY version DESC
        LIMIT 1
        """,
        (outreach_item_id,),
    ).fetchone()

    if latest and latest["subject"] == draft.subject and latest["body"] == draft.body:
        return int(latest["id"]), False

    next_version = 1 if not latest else int(latest["version"]) + 1
    now = utc_now()

    cursor = conn.execute(
        """
        INSERT INTO drafts (
            outreach_item_id,
            version,
            subject,
            body,
            generator,
            selected_for_sync,
            synced_to_sheet,
            created_at
        ) VALUES (?, ?, ?, ?, ?, 1, 0, ?)
        """,
        (outreach_item_id, next_version, draft.subject, draft.body, draft.generator, now),
    )

    conn.execute(
        """
        UPDATE outreach_items
        SET pipeline_state = 'DRAFTED',
            updated_at = ?
        WHERE id = ?
        """,
        (now, outreach_item_id),
    )

    return int(cursor.lastrowid), True


def get_original_subject_for_lead(
    conn: sqlite3.Connection,
    *,
    lead_id: int,
) -> str | None:
    row = conn.execute(
        """
        SELECT d.subject
        FROM drafts d
        JOIN outreach_items o ON o.id = d.outreach_item_id
        WHERE o.lead_id = ?
        ORDER BY d.version ASC
        LIMIT 1
        """,
        (lead_id,),
    ).fetchone()
    if not row:
        return None

    subject = str(row["subject"] or "").strip()
    return subject or None


def _draft_type_for_classification(classification: str) -> str:
    if classification == LeadClassification.FIRST_TOUCH_READY.value:
        return "FIRST_TOUCH"
    if classification == LeadClassification.FOLLOW_UP_READY.value:
        return "FOLLOW_UP"
    return ""


def list_sync_candidates(
    conn: sqlite3.Connection,
    *,
    only_selected: bool = True,
    limit: int = 200,
) -> list[dict[str, Any]]:
    selected_filter = (
        "AND o.selected_for_sync = 1 AND (ld.id IS NULL OR ld.selected_for_sync = 1)"
        if only_selected
        else ""
    )

    query = f"""
    WITH latest_drafts AS (
        SELECT d.*
        FROM drafts d
        JOIN (
            SELECT outreach_item_id, MAX(version) AS max_version
            FROM drafts
            GROUP BY outreach_item_id
        ) latest
            ON latest.outreach_item_id = d.outreach_item_id
           AND latest.max_version = d.version
    )
    SELECT
        o.id AS outreach_item_id,
        l.source_row_number,
        l.source_sheet,
        l.segment,
        o.classification,
        o.reason,
        o.duplicate_flag,
        o.duplicate_type,
        o.duplicate_reason,
        o.duplicate_of_lead_id,
        dl.source_sheet AS duplicate_of_sheet,
        dl.source_row_number AS duplicate_of_row,
        ld.id AS draft_id,
        ld.subject,
        ld.body,
        c.email AS contact_email,
        c.contact_form_url AS contact_form_url,
        c.raw_value AS raw_contact_value,
        ld.synced_to_sheet,
        o.source_last_synced_at,
        o.updated_at
    FROM outreach_items o
    JOIN leads l ON l.id = o.lead_id
    LEFT JOIN leads dl ON dl.id = o.duplicate_of_lead_id
    LEFT JOIN latest_drafts ld ON ld.outreach_item_id = o.id
    LEFT JOIN contacts c ON c.id = o.contact_id
    WHERE (
        o.source_last_synced_at IS NULL
        OR o.updated_at > o.source_last_synced_at
        OR (ld.id IS NOT NULL AND ld.synced_to_sheet = 0)
    )
    {selected_filter}
    ORDER BY l.source_row_number ASC
    LIMIT ?
    """

    rows = conn.execute(query, (limit,)).fetchall()
    results: list[dict[str, Any]] = []
    processed_at = utc_now()

    for row in rows:
        classification = str(row["classification"])
        is_draftable = classification in (
            LeadClassification.FIRST_TOUCH_READY.value,
            LeadClassification.FOLLOW_UP_READY.value,
        )
        error_flag = (
            "REVIEW_REQUIRED"
            if classification in ("CONTACT_FORM_REVIEW", "EMAIL_NEEDS_REVIEW")
            else ""
        )
        selected_contact = (
            row["contact_email"] or row["contact_form_url"] or row["raw_contact_value"] or ""
        )
        results.append(
            {
                "outreach_item_id": int(row["outreach_item_id"]),
                "source_row_number": int(row["source_row_number"]),
                "source_sheet": row["source_sheet"],
                "lead_type": classification,
                "assistant_status": classification,
                "classification": classification,
                "reason": row["reason"] or "",
                "selected_contact": selected_contact,
                "draft_type": _draft_type_for_classification(classification) if is_draftable else "",
                "draft_id": int(row["draft_id"]) if row["draft_id"] is not None else None,
                "subject": (row["subject"] or "") if is_draftable else "",
                "body": (row["body"] or "") if is_draftable else "",
                "personalization_note": row["reason"] or "",
                "last_processed_at": processed_at,
                "error_flag": error_flag,
                "duplicate_flag": "YES" if int(row["duplicate_flag"] or 0) == 1 else "",
                "duplicate_type": row["duplicate_type"] or "",
                "duplicate_of": (
                    f"{row['duplicate_of_sheet']}:{int(row['duplicate_of_row'])}"
                    if row["duplicate_of_row"] is not None
                    else ""
                ),
                "duplicate_reason": row["duplicate_reason"] or "",
            }
        )

    return results


def list_gmail_draft_candidates(
    conn: sqlite3.Connection,
    *,
    limit: int = 200,
    only_selected: bool = True,
    force: bool = False,
) -> list[GmailDraftCandidate]:
    selected_filter = "AND o.selected_for_sync = 1 AND ld.selected_for_sync = 1" if only_selected else ""
    force_filter = (
        ""
        if force
        else "AND (o.gmail_draft_for_draft_id IS NULL OR o.gmail_draft_for_draft_id <> ld.id)"
    )

    query = f"""
    WITH latest_drafts AS (
        SELECT d.*
        FROM drafts d
        JOIN (
            SELECT outreach_item_id, MAX(version) AS max_version
            FROM drafts
            GROUP BY outreach_item_id
        ) latest
            ON latest.outreach_item_id = d.outreach_item_id
           AND latest.max_version = d.version
    )
    SELECT
        o.id AS outreach_item_id,
        o.classification,
        o.gmail_draft_id,
        l.source_sheet,
        l.source_row_number,
        ld.id AS draft_record_id,
        ld.subject,
        ld.body,
        COALESCE(c.email, c.raw_value, '') AS selected_contact
    FROM outreach_items o
    JOIN leads l ON l.id = o.lead_id
    JOIN latest_drafts ld ON ld.outreach_item_id = o.id
    LEFT JOIN contacts c ON c.id = o.contact_id
    WHERE o.classification IN ('FIRST_TOUCH_READY', 'FOLLOW_UP_READY')
      AND COALESCE(o.duplicate_type, '') <> 'HARD'
      AND COALESCE(ld.subject, '') <> ''
      AND COALESCE(ld.body, '') <> ''
      AND COALESCE(c.email, c.raw_value, '') <> ''
      {selected_filter}
      {force_filter}
    ORDER BY l.source_row_number ASC
    LIMIT ?
    """

    rows = conn.execute(query, (limit,)).fetchall()
    return [
        GmailDraftCandidate(
            outreach_item_id=int(row["outreach_item_id"]),
            source_sheet=row["source_sheet"],
            source_row_number=int(row["source_row_number"]),
            classification=str(row["classification"]),
            recipient=str(row["selected_contact"]).strip(),
            subject=str(row["subject"]),
            body=str(row["body"]),
            draft_record_id=int(row["draft_record_id"]),
            existing_gmail_draft_id=row["gmail_draft_id"],
        )
        for row in rows
    ]


def mark_gmail_draft_created(
    conn: sqlite3.Connection,
    *,
    outreach_item_id: int,
    gmail_draft_id: str,
    draft_record_id: int | None = None,
) -> None:
    now = utc_now()
    conn.execute(
        """
        UPDATE outreach_items
        SET gmail_draft_id = ?,
            gmail_draft_for_draft_id = ?,
            gmail_draft_created_at = ?,
            updated_at = ?
        WHERE id = ?
        """,
        (gmail_draft_id, draft_record_id, now, now, outreach_item_id),
    )


def mark_synced(
    conn: sqlite3.Connection,
    *,
    outreach_item_ids: list[int],
    draft_ids: list[int],
) -> None:
    now = utc_now()

    if outreach_item_ids:
        placeholders = ",".join("?" for _ in outreach_item_ids)
        conn.execute(
            f"""
            UPDATE outreach_items
            SET source_last_synced_at = ?,
                pipeline_state = CASE
                    WHEN classification = 'DONE' THEN 'DONE'
                    ELSE 'REVIEWED'
                END,
                updated_at = updated_at
            WHERE id IN ({placeholders})
            """,
            [now, *outreach_item_ids],
        )

    if draft_ids:
        placeholders = ",".join("?" for _ in draft_ids)
        conn.execute(
            f"""
            UPDATE drafts
            SET synced_to_sheet = 1,
                synced_at = ?
            WHERE id IN ({placeholders})
            """,
            [now, *draft_ids],
        )
