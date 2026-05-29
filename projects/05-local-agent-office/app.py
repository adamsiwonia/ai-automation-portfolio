from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any, Callable

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from agents.lead_finder import find_leads
from agents.lead_pre_filter import pre_filter_lead
from agents.lead_qualifier import qualify_lead
from agents.lead_researcher import research_lead
from services import control, database
from services.google_sheets_client import append_qualified_lead, sheet_lead_exists
from services.lead_safety import is_mock_or_demo_lead
from services.settings import lead_source_mode, minimum_qualification_score


BASE_DIR = Path(__file__).resolve().parent
WEB_DIR = BASE_DIR / "web"
DEFAULT_NICHE = "local businesses needing automation"
DEFAULT_MODEL = "qwen3:8b"

app = FastAPI(title="Local Agent Office", version="0.1.0")
app.mount("/static", StaticFiles(directory=WEB_DIR), name="static")


class AgentRequest(BaseModel):
    niche: str = Field(default=DEFAULT_NICHE, min_length=1, max_length=300)
    limit: int = Field(default=5, ge=1, le=50)
    model_name: str = Field(default=DEFAULT_MODEL, min_length=1, max_length=120)


def _request_payload(request: AgentRequest) -> dict[str, Any]:
    if hasattr(request, "model_dump"):
        return request.model_dump()
    return request.dict()


def _set_current_task(task: str) -> None:
    app.state.current_task = task


def _workflow_counts() -> dict[str, int]:
    return {
        "discovered": 0,
        "qualified": 0,
        "review": 0,
        "rejected": 0,
        "duplicates": 0,
        "errors": 0,
    }


def _as_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _add_status_count(counts: dict[str, int], status: str) -> None:
    if status == "QUALIFIED":
        counts["qualified"] += 1
    elif status == "REVIEW":
        counts["review"] += 1
    elif status == "REJECTED":
        counts["rejected"] += 1


def run_lead_workflow(
    niche: str,
    limit: int,
    model_name: str,
    respect_control: bool = True,
    set_task: Callable[[str], None] | None = None,
) -> dict[str, Any]:
    set_task = set_task or (lambda task: None)
    counts = _workflow_counts()
    run_id = database.create_run(niche, limit, model_name)
    status = "COMPLETED"
    source_mode = lead_source_mode()
    minimum_score = minimum_qualification_score()

    try:
        set_task("Finding leads")
        database.add_log(
            "INFO",
            f"Finding up to {limit} lead(s) for: {niche}",
            task="lead_finder",
            event="lead_discovery_started",
            details={"niche": niche, "limit": limit, "lead_source_mode": source_mode},
        )
        candidates = find_leads(niche=niche, limit=limit, lead_source_mode=source_mode)
        counts["discovered"] = len(candidates)
        database.add_log(
            "INFO",
            f"Discovered {len(candidates)} lead candidate(s) using {source_mode.upper()} mode.",
            task="lead_finder",
            event="lead_discovery_completed",
            details={"lead_source_mode": source_mode, "candidate_count": len(candidates)},
        )
        if not candidates and source_mode in {"manual", "search"}:
            database.add_log(
                "WARNING",
                f"{source_mode.upper()} lead source mode is configured, but no importer/search adapter is active yet.",
                task="lead_finder",
                event="lead_source_not_implemented",
                details={"lead_source_mode": source_mode},
            )

        for index, candidate in enumerate(candidates, start=1):
            if respect_control and not control.agents_enabled():
                status = "STOPPED"
                database.add_log("INFO", "Agents disabled; stopping before next lead.", task="control")
                break

            company = candidate.get("company_name", "Unknown Company")
            set_task(f"Researching {company} ({index}/{len(candidates)})")
            researched = research_lead(candidate)
            researched["lead_source_mode"] = researched.get("lead_source_mode") or source_mode

            pre_filter = pre_filter_lead(researched, niche=niche)
            pre_filter_fields = {
                "pre_filter_passed": pre_filter["passed"],
                "pre_filter_reason": pre_filter["reason"],
                "pre_filter_flags": pre_filter["flags"],
            }
            if not pre_filter["passed"]:
                skipped_lead = {
                    **researched,
                    **pre_filter_fields,
                    "status": "SKIPPED",
                    "reason": pre_filter["reason"],
                    "sheet_status": "NOT_ELIGIBLE",
                }
                database.insert_lead(skipped_lead)
                database.add_log(
                    "SKIPPED",
                    f"Skipped before Ollama: {pre_filter['reason']}",
                    task="lead_pre_filter",
                    event="pre_filter_rejected",
                    company_name=company,
                    details={"flags": pre_filter["flags"], "website_url": researched.get("website_url")},
                )
                continue

            duplicate_reason = database.find_duplicate_lead(researched)
            if duplicate_reason:
                counts["duplicates"] += 1
                database.insert_lead(
                    {
                        **researched,
                        **pre_filter_fields,
                        "status": "DUPLICATE_LOCAL",
                        "reason": "Lead already exists in Project 05 local database.",
                        "duplicate_reason": duplicate_reason,
                        "sheet_status": "NOT_CHECKED",
                    }
                )
                database.add_log(
                    "SKIPPED",
                    f"Skipped local duplicate: {company}",
                    task="duplicate_checker",
                    event="local_duplicate",
                    company_name=company,
                    details={"reason": duplicate_reason},
                )
                continue

            exists_in_sheet, sheet_reason = sheet_lead_exists(researched)
            if exists_in_sheet:
                counts["duplicates"] += 1
                duplicate_lead = {
                    **researched,
                    **pre_filter_fields,
                    "status": "DUPLICATE_SHEET",
                    "reason": "Lead already exists in the Project 03.5 Google Sheet.",
                    "sheet_status": "DUPLICATE",
                    "sheet_duplicate_reason": sheet_reason,
                    "duplicate_reason": sheet_reason,
                }
                database.insert_lead(duplicate_lead)
                database.add_log(
                    "SKIPPED",
                    f"Skipped Google Sheet duplicate: {company}",
                    task="sheets_writer",
                    event="sheet_duplicate",
                    company_name=company,
                    details={"reason": sheet_reason},
                )
                continue

            set_task(f"Qualifying {company} with {model_name}")
            qualification = qualify_lead(researched, model_name=model_name)
            lead = {
                **researched,
                **pre_filter_fields,
                **qualification,
                "source_query": niche,
                "sheet_status": "PENDING",
            }
            lead_id = database.insert_lead(lead)
            stored_lead = database.get_lead(lead_id) or {**lead, "id": lead_id}
            _add_status_count(counts, str(stored_lead.get("status", "")))
            database.add_log(
                "SUCCESS",
                f"Stored lead #{lead_id}: {company} ({stored_lead.get('status')})",
                task="database",
                event="lead_stored",
                company_name=company,
                details={"lead_id": lead_id, "status": stored_lead.get("status"), "score": stored_lead.get("score")},
            )

            if stored_lead.get("status") == "QUALIFIED" and _as_int(stored_lead.get("score")) >= minimum_score:
                set_task(f"Preparing Google Sheet row for {company}")
                appended = append_qualified_lead(stored_lead)
                database.update_lead_sheet_status(lead_id, "APPENDED" if appended else "LOCAL_ONLY")
            elif stored_lead.get("status") == "QUALIFIED":
                database.update_lead_sheet_status(
                    lead_id,
                    "BELOW_MIN_SCORE",
                    f"Score {_as_int(stored_lead.get('score'))} is below minimum {minimum_score}.",
                )
            else:
                database.update_lead_sheet_status(lead_id, "NOT_ELIGIBLE")

    except Exception as exc:
        status = "ERROR"
        counts["errors"] += 1
        database.add_log("ERROR", f"Workflow failed: {exc}", task="workflow", event="workflow_failed")

    finally:
        database.finish_run(run_id=run_id, status=status, counts=counts)
        set_task("Waiting for next run" if control.agents_enabled() else "Idle")

    return {"run_id": run_id, "status": status, "counts": counts}


async def agent_loop() -> None:
    database.add_log("INFO", "Background agents started.", task="control")
    try:
        while control.agents_enabled():
            params = dict(app.state.loop_params)
            async with app.state.run_lock:
                await asyncio.to_thread(
                    run_lead_workflow,
                    params["niche"],
                    params["limit"],
                    params["model_name"],
                    True,
                    _set_current_task,
                )

            for _ in range(60):
                if not control.agents_enabled():
                    break
                _set_current_task("Waiting for next run")
                await asyncio.sleep(1)
    finally:
        _set_current_task("Idle")
        database.add_log("INFO", "Background agents stopped.", task="control")


@app.on_event("startup")
def startup() -> None:
    database.init_db()
    control.ensure_control_file()
    app.state.current_task = "Idle"
    app.state.loop_params = {
        "niche": DEFAULT_NICHE,
        "limit": 5,
        "model_name": DEFAULT_MODEL,
    }
    app.state.run_lock = asyncio.Lock()
    app.state.worker_task = None
    database.add_log("INFO", "Local Agent Office started.", task="startup")


@app.get("/")
def index() -> FileResponse:
    return FileResponse(WEB_DIR / "index.html")


@app.get("/api/status")
def api_status() -> dict[str, Any]:
    ctl = control.read_control()
    return {
        **ctl,
        "current_task": getattr(app.state, "current_task", "Idle"),
        "counts": database.get_counts(),
        "latest_run": database.get_latest_run(),
        "lead_source_mode": lead_source_mode(),
        "minimum_qualification_score": minimum_qualification_score(),
    }


@app.post("/api/start")
async def api_start(request: AgentRequest) -> dict[str, Any]:
    payload = _request_payload(request)
    app.state.loop_params = payload
    control.set_running()

    worker = getattr(app.state, "worker_task", None)
    if worker is None or worker.done():
        app.state.worker_task = asyncio.create_task(agent_loop())

    database.add_log("INFO", "Agents enabled from control panel.", task="control", metadata=payload)
    return api_status()


@app.post("/api/stop")
def api_stop() -> dict[str, Any]:
    control.set_stopped()
    worker = getattr(app.state, "worker_task", None)
    if worker is not None and not worker.done():
        _set_current_task("Stopping after current safe checkpoint")
    else:
        _set_current_task("Idle")
    database.add_log("INFO", "Agents disabled from control panel.", task="control")
    return api_status()


@app.post("/api/run-once")
async def api_run_once(request: AgentRequest) -> dict[str, Any]:
    previous_control = control.read_control()
    control.set_running()
    database.add_log("INFO", "Manual run started.", task="control", metadata=_request_payload(request))

    async with app.state.run_lock:
        result = await asyncio.to_thread(
            run_lead_workflow,
            request.niche,
            request.limit,
            request.model_name,
            True,
            _set_current_task,
        )

    if not previous_control["agents_enabled"]:
        control.set_stopped()
        _set_current_task("Idle")

    return {"result": result, "status": api_status()}


@app.get("/api/logs")
def api_logs(limit: int = 50) -> dict[str, Any]:
    return {"logs": database.get_recent_logs(limit=limit)}


@app.get("/api/leads")
def api_leads(limit: int = 50) -> dict[str, Any]:
    return {"leads": database.get_latest_leads(limit=limit)}


@app.post("/api/leads/{lead_id}/approve")
def api_approve_lead(lead_id: int) -> dict[str, Any]:
    lead = database.get_lead(lead_id)
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    if is_mock_or_demo_lead(lead):
        database.add_log(
            "WARNING",
            "Blocked mock/demo lead approval.",
            task="lead_control",
            event="mock_lead_approval_blocked",
            company_name=lead.get("company_name"),
            details={"lead_id": lead_id, "source": lead.get("source"), "lead_source_mode": lead.get("lead_source_mode")},
        )
        raise HTTPException(status_code=400, detail="Mock/demo leads cannot be approved for outreach by default.")

    updated = database.update_lead_status(lead_id, "APPROVED_FOR_OUTREACH")
    if not updated:
        raise HTTPException(status_code=404, detail="Lead not found")

    lead = database.get_lead(lead_id)
    database.add_log(
        "SUCCESS",
        "Lead approved for outreach.",
        task="lead_control",
        event="lead_approved_for_outreach",
        company_name=lead.get("company_name") if lead else None,
        details={"lead_id": lead_id},
    )
    return {"lead": lead}


@app.post("/api/leads/{lead_id}/reject")
def api_reject_lead(lead_id: int) -> dict[str, Any]:
    updated = database.update_lead_status(lead_id, "REJECTED", reason="Rejected in Project 05 control panel.")
    if not updated:
        raise HTTPException(status_code=404, detail="Lead not found")

    lead = database.get_lead(lead_id)
    database.add_log(
        "SKIPPED",
        "Lead rejected in control panel.",
        task="lead_control",
        event="lead_rejected",
        company_name=lead.get("company_name") if lead else None,
        details={"lead_id": lead_id},
    )
    return {"lead": lead}
