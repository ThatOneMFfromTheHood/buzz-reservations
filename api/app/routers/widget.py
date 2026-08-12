"""White-label widget endpoints (ТЗ §7, §9)."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Venue, WidgetConfig
from ..schemas import InfoItem, WidgetConfigOut
from .public import booking_config

router = APIRouter(prefix="/widget", tags=["widget"])


@router.get("/{slug}/config", response_model=WidgetConfigOut)
def get_widget_config(slug: str, db: Session = Depends(get_db)):
    cfg = db.scalar(select(WidgetConfig).where(WidgetConfig.slug == slug))
    if cfg is None:
        raise HTTPException(404, detail={"code": "widget_not_found", "message": "Unknown widget slug"})
    venue = db.get(Venue, cfg.venue_id)
    return WidgetConfigOut(
        slug=cfg.slug, venue_id=venue.id, venue_name=venue.name, address=venue.address,
        primary_color=cfg.primary_color, text_color=cfg.text_color, bg_color=cfg.bg_color,
        form_control_color=cfg.form_control_color, font=cfg.font,
        corner_style=cfg.corner_style, text_alignment=cfg.text_alignment,
        default_lang=cfg.default_lang, logo_url=cfg.logo_url,
        photo_url=cfg.photo_url, policy_text=cfg.policy_text,
        info_items=[InfoItem(**i) for i in (cfg.info_items or [])],
        booking=booking_config(db, venue))
