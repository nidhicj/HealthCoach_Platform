"""Diet chart endpoints — template library CRUD + client chart CRUD."""
import csv
import io
from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, HTTPException, UploadFile, status
from pydantic import BaseModel
from sqlalchemy import and_, select

from src.api.deps import DbDep, HcClaimsDep, TenantDep
from src.db.models.clients import Client
from src.db.models.content import ContentAssignment, DietChart

router = APIRouter(tags=["diet-charts"])

DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
MAX_CSV_BYTES = 128 * 1024
MAX_PASTE_BYTES = 256 * 1024


# ── schemas ────────────────────────────────────────────────────────────────────


class DietChartOut(BaseModel):
    id: UUID
    name: str
    description: str | None
    parameters: dict | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class DietChartPatch(BaseModel):
    parameters: dict


class PasteTemplateIn(BaseModel):
    name: str
    text: str


class GenerateRequest(BaseModel):
    template_id: UUID
    modifications: str | None = None


class GenerateResponse(BaseModel):
    chart: DietChartOut
    generation_status: str  # "generated" | "fallback"


# ── helpers ────────────────────────────────────────────────────────────────────


def _parse_csv_bytes(data: bytes) -> dict:
    """Parse diet chart CSV → {meal_slots, grid}.
    Header: Day,<Slot1>,…  Cells: "food · timing".
    """
    text = data.decode("utf-8-sig").strip()
    reader = csv.DictReader(io.StringIO(text))
    if reader.fieldnames is None:
        raise ValueError("CSV has no header row")
    fieldnames = list(reader.fieldnames)
    if not fieldnames or fieldnames[0].strip() != "Day":
        raise ValueError("First column header must be 'Day'")
    meal_slots = [f.strip() for f in fieldnames[1:] if f.strip()]
    if not meal_slots:
        raise ValueError("CSV must have at least one meal slot column")
    grid: dict[str, dict[str, dict[str, str]]] = {}
    for row in reader:
        day = (row.get("Day") or "").strip()
        if day not in DAYS:
            continue
        grid[day] = {}
        for slot in meal_slots:
            raw = (row.get(slot) or "").strip()
            if "·" in raw:
                food_part, timing_part = raw.split("·", 1)
                grid[day][slot] = {"food": food_part.strip(), "timing": timing_part.strip()}
            else:
                grid[day][slot] = {"food": raw, "timing": ""}
    return {"meal_slots": meal_slots, "grid": grid}


def _parse_tsv_rows(text: str) -> list[list[str]]:
    """Parse TSV (Google Sheets copy-paste) into a 2-D array, trimming trailing empty cells."""
    rows = []
    for line in text.splitlines():
        cells = line.split("\t")
        while cells and not cells[-1].strip():
            cells.pop()
        if cells:
            rows.append(cells)
    return rows


def _to_out(chart: DietChart) -> DietChartOut:
    return DietChartOut.model_validate(chart)


async def _get_owned_client(db: DbDep, client_id: UUID, hc_id: str) -> Client:
    client = (await db.execute(
        select(Client).where(Client.id == client_id, Client.hc_user_id == UUID(hc_id))
    )).scalar_one_or_none()
    if client is None:
        raise HTTPException(status_code=404, detail="Client not found")
    return client


async def _get_active_chart(db: DbDep, client_id: UUID, hc_id: str) -> DietChart | None:
    return (await db.execute(
        select(DietChart)
        .join(ContentAssignment, and_(
            ContentAssignment.content_type == "diet_chart",
            ContentAssignment.content_id == DietChart.id,
        ))
        .where(
            ContentAssignment.client_id == client_id,
            ContentAssignment.hc_user_id == UUID(hc_id),
            DietChart.archived_at.is_(None),
        )
        .order_by(ContentAssignment.assigned_at.desc())
        .limit(1)
    )).scalar_one_or_none()


# ── template routes ────────────────────────────────────────────────────────────


@router.post("/api/diet-charts/templates/upload", status_code=status.HTTP_201_CREATED)
async def upload_template(
    file: UploadFile,
    claims: HcClaimsDep,
    hc_id: TenantDep,
    db: DbDep,
) -> DietChartOut:
    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=422, detail="File must be a .csv")
    data = await file.read(MAX_CSV_BYTES + 1)
    if len(data) > MAX_CSV_BYTES:
        raise HTTPException(status_code=422, detail="CSV exceeds 128 KB limit")
    try:
        parsed = _parse_csv_bytes(data)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    name = file.filename[:-4]
    template_key = name.lower().replace(" ", "-")
    chart = DietChart(
        hc_user_id=UUID(hc_id),
        name=name,
        description=None,
        parameters={"is_template": True, "template_key": template_key, **parsed},
    )
    db.add(chart)
    await db.flush()
    await db.commit()
    return _to_out(chart)


@router.get("/api/diet-charts/templates")
async def list_templates(
    claims: HcClaimsDep,
    hc_id: TenantDep,
    db: DbDep,
) -> list[DietChartOut]:
    rows = (await db.execute(
        select(DietChart)
        .where(
            DietChart.hc_user_id == UUID(hc_id),
            DietChart.parameters["is_template"].as_boolean().is_(True),
            DietChart.archived_at.is_(None),
        )
        .order_by(DietChart.created_at.asc())
    )).scalars().all()
    return [_to_out(r) for r in rows]


@router.delete("/api/diet-charts/templates/{template_id}", status_code=status.HTTP_204_NO_CONTENT)
async def archive_template(
    template_id: UUID,
    claims: HcClaimsDep,
    hc_id: TenantDep,
    db: DbDep,
) -> None:
    chart = (await db.execute(
        select(DietChart).where(
            DietChart.id == template_id,
            DietChart.hc_user_id == UUID(hc_id),
            DietChart.parameters["is_template"].as_boolean().is_(True),
        )
    )).scalar_one_or_none()
    if chart is None:
        raise HTTPException(status_code=404, detail="Template not found")
    chart.archived_at = datetime.now(timezone.utc)
    await db.flush()
    await db.commit()


@router.post("/api/diet-charts/templates/paste", status_code=status.HTTP_201_CREATED)
async def paste_template(
    body: PasteTemplateIn,
    claims: HcClaimsDep,
    hc_id: TenantDep,
    db: DbDep,
) -> DietChartOut:
    if len(body.text.encode("utf-8")) > MAX_PASTE_BYTES:
        raise HTTPException(status_code=422, detail="Pasted content exceeds 256 KB limit")
    rows = _parse_tsv_rows(body.text)
    if not rows:
        raise HTTPException(status_code=422, detail="No content found in pasted text")
    name = body.name.strip() or "Untitled"
    template_key = name.lower().replace(" ", "-")
    chart = DietChart(
        hc_user_id=UUID(hc_id),
        name=name,
        description=None,
        parameters={
            "is_template": True,
            "template_type": "raw_table",
            "template_key": template_key,
            "rows": rows,
        },
    )
    db.add(chart)
    await db.flush()
    await db.commit()
    return _to_out(chart)


# ── client chart routes ────────────────────────────────────────────────────────


@router.get("/api/clients/{client_id}/diet-chart")
async def get_client_diet_chart(
    client_id: UUID,
    claims: HcClaimsDep,
    hc_id: TenantDep,
    db: DbDep,
) -> DietChartOut:
    await _get_owned_client(db, client_id, hc_id)
    chart = await _get_active_chart(db, client_id, hc_id)
    if chart is None:
        raise HTTPException(status_code=404, detail="No active diet chart for this client")
    return _to_out(chart)


@router.post("/api/clients/{client_id}/diet-chart/generate")
async def generate_client_diet_chart(
    client_id: UUID,
    body: GenerateRequest,
    claims: HcClaimsDep,
    hc_id: TenantDep,
    db: DbDep,
) -> GenerateResponse:
    await _get_owned_client(db, client_id, hc_id)
    template = (await db.execute(
        select(DietChart).where(
            DietChart.id == body.template_id,
            DietChart.hc_user_id == UUID(hc_id),
            DietChart.parameters["is_template"].as_boolean().is_(True),
            DietChart.archived_at.is_(None),
        )
    )).scalar_one_or_none()
    if template is None:
        raise HTTPException(status_code=404, detail="Template not found")
    existing = await _get_active_chart(db, client_id, hc_id)
    if existing is not None:
        existing.archived_at = datetime.now(timezone.utc)
        await db.flush()
    from src.llm_service.diet_chart_generate import generate_diet_chart  # noqa: PLC0415
    chart_params, generation_status = await generate_diet_chart(
        db=db,
        hc_user_id=UUID(hc_id),
        client_id=client_id,
        template_params=template.parameters or {},
        modifications=body.modifications,
    )
    chart = DietChart(
        hc_user_id=UUID(hc_id),
        name=f"{template.name} — {datetime.now(timezone.utc).strftime('%d %b %Y')}",
        description=None,
        parameters=chart_params,
    )
    db.add(chart)
    await db.flush()
    assignment = ContentAssignment(
        hc_user_id=UUID(hc_id),
        client_id=client_id,
        session_id=None,
        content_type="diet_chart",
        content_id=chart.id,
    )
    db.add(assignment)
    await db.flush()
    await db.commit()
    return GenerateResponse(chart=_to_out(chart), generation_status=generation_status)


@router.patch("/api/clients/{client_id}/diet-chart")
async def patch_client_diet_chart(
    client_id: UUID,
    body: DietChartPatch,
    claims: HcClaimsDep,
    hc_id: TenantDep,
    db: DbDep,
) -> DietChartOut:
    await _get_owned_client(db, client_id, hc_id)
    chart = await _get_active_chart(db, client_id, hc_id)
    if chart is None:
        raise HTTPException(status_code=404, detail="No active diet chart for this client")
    chart.parameters = body.parameters
    chart.updated_at = datetime.now(timezone.utc)
    await db.flush()
    await db.commit()
    return _to_out(chart)
