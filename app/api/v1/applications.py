import uuid
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_partner
from app.db.session import get_db
from app.models.partner import Partner
from app.schemas.application import ApplicationCreate, ApplicationRead
from app.services import application_service

router = APIRouter(prefix="/applications", tags=["applications"])


@router.post("", response_model=ApplicationRead, status_code=201)
async def submit_application(
    data: ApplicationCreate,
    partner: Annotated[Partner, Depends(get_current_partner)],
    db: AsyncSession = Depends(get_db),
):
    """Submit a loan application. Returns an immediate APPROVED or DECLINED decision."""
    return await application_service.submit_application(data, partner.id, db)


@router.get("/{application_id}", response_model=ApplicationRead)
async def get_application(
    application_id: uuid.UUID,
    partner: Annotated[Partner, Depends(get_current_partner)],
    db: AsyncSession = Depends(get_db),
):
    app = await application_service.get_application(application_id, db)
    return app
