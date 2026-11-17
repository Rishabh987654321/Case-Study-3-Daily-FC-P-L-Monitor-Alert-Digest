"""System endpoints: health check and read-only config."""

from fastapi import APIRouter

from app.config import get_settings
from app.schemas import ConfigRangePair, ConfigResponse, HealthResponse

router = APIRouter(tags=["system"])

_CONFIG_KEY_MAP = {
    "Manpower Cost": "manpower",
    "Packaging Cost": "packaging",
    "Power & Fuel": "power_fuel",
    "FC Rent": "rent",
    "Equipment Rentals": "equipment",
    "Overheads": "overheads",
}


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok", version="1.0.0")


@router.get("/config", response_model=ConfigResponse)
def config() -> ConfigResponse:
    settings = get_settings()
    targets = {
        _CONFIG_KEY_MAP[label]: ConfigRangePair(min=r.min_pct, max=r.max_pct)
        for label, r in settings.line_item_ranges().items()
    }
    return ConfigResponse(
        targets=targets,
        cm1=ConfigRangePair(min=settings.target_cm1_min, max=settings.target_cm1_max),
        cm2=ConfigRangePair(min=settings.target_cm2_min, max=settings.target_cm2_max),
        cm_tolerance=settings.cm_tolerance,
        max_file_mb=settings.max_file_mb,
        notify_channel=settings.notify_channel,
    )
