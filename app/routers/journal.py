import uuid

from fastapi import APIRouter, Depends, Form, Request
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.responses import RedirectResponse

from app.database import get_db
from app.services import journal_service

router = APIRouter(prefix="/journal")


@router.get("")
async def journal_list(request: Request, db: AsyncSession = Depends(get_db)):
    entries = await journal_service.list_entries(db)
    return request.app.state.templates.TemplateResponse(
        "journal/list.html",
        {"request": request, "entries": entries},
    )


@router.get("/{entry_id}")
async def journal_detail(request: Request, entry_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    entry = await journal_service.get_entry(db, entry_id)
    if entry is None:
        return RedirectResponse(url="/journal?msg=Entry+not+found&msg_type=error", status_code=303)
    all_tags = await journal_service.get_all_tags(db)
    return request.app.state.templates.TemplateResponse(
        "journal/detail.html",
        {
            "request": request,
            "entry": entry,
            "all_tags": all_tags,
        },
    )


@router.post("/{entry_id}/edit")
async def journal_edit(
    entry_id: uuid.UUID,
    what_went_well: str = Form(""),
    what_went_wrong: str = Form(""),
    lessons_learned: str = Form(""),
    emotions: str = Form(""),
    would_take_again: bool = Form(False),
    rating: int | None = Form(None),
    tags: str = Form(""),  # comma-separated tag names
    db: AsyncSession = Depends(get_db),
):
    entry = await journal_service.update_entry(
        db, entry_id,
        what_went_well=what_went_well or None,
        what_went_wrong=what_went_wrong or None,
        lessons_learned=lessons_learned or None,
        emotions=emotions or None,
        would_take_again=would_take_again,
        rating=rating,
    )
    if entry and tags:
        tag_names = [t.strip() for t in tags.split(",") if t.strip()]
        await journal_service.set_entry_tags(db, entry_id, tag_names)
    await db.commit()
    return RedirectResponse(url=f"/journal/{entry_id}?msg=Saved", status_code=303)


@router.post("/{entry_id}/complete")
async def journal_complete(entry_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    await journal_service.complete_entry(db, entry_id)
    await db.commit()
    return RedirectResponse(url=f"/journal/{entry_id}?msg=Marked+complete", status_code=303)


@router.post("/{entry_id}/delete")
async def journal_delete(entry_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    await journal_service.delete_entry(db, entry_id)
    await db.commit()
    return RedirectResponse(url="/journal?msg=Entry+deleted", status_code=303)
