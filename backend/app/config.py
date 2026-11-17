"""Settings loaded from .env, with sensible defaults matching .env.example."""

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[2]
ENV_PATH = PROJECT_ROOT / ".env"


@dataclass(frozen=True)
class TargetRange:
    min_pct: float
    max_pct: float


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(ENV_PATH),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # Server
    port: int = 8000
    host: str = "0.0.0.0"

    # Database
    database_url: str = "sqlite:///./data/pnl_monitor.db"

    # File uploads
    max_file_mb: int = 50
    upload_dir: str = "./data/uploads"

    # Per-line-item target ranges (% of revenue)
    target_manpower_min: float = 20
    target_manpower_max: float = 28
    target_packaging_min: float = 5
    target_packaging_max: float = 10
    target_power_fuel_min: float = 3
    target_power_fuel_max: float = 7
    target_rent_min: float = 8
    target_rent_max: float = 15
    target_equipment_min: float = 2
    target_equipment_max: float = 5
    target_overheads_min: float = 3
    target_overheads_max: float = 7

    # Margin targets
    target_cm1_min: float = 65
    target_cm1_max: float = 70
    target_cm2_min: float = 15
    target_cm2_max: float = 30
    cm_tolerance: float = 3

    # Ollama / LLM settings
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.2:3b"
    ollama_timeout: float = 10.0
    insight_mode: str = "auto"  # auto | llm | rule
    # In "auto" mode only: total wall-clock time the whole batch is allowed
    # to spend attempting LLM calls before every remaining FC-day in this
    # run falls back to rule-based instantly. Keeps a large upload's insight
    # step bounded (e.g. for a live demo) instead of scaling with row count.
    # "llm" (strict) mode ignores this — it always tries the LLM.
    insight_batch_budget_seconds: float = 8.0

    # Notifications
    notify_channel: str = "file"
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    digest_recipients: str = ""
    webhook_url: str = ""

    @property
    def manpower_range(self) -> TargetRange:
        return TargetRange(self.target_manpower_min, self.target_manpower_max)

    @property
    def packaging_range(self) -> TargetRange:
        return TargetRange(self.target_packaging_min, self.target_packaging_max)

    @property
    def power_fuel_range(self) -> TargetRange:
        return TargetRange(self.target_power_fuel_min, self.target_power_fuel_max)

    @property
    def fc_rent_range(self) -> TargetRange:
        return TargetRange(self.target_rent_min, self.target_rent_max)

    @property
    def equipment_range(self) -> TargetRange:
        return TargetRange(self.target_equipment_min, self.target_equipment_max)

    @property
    def overheads_range(self) -> TargetRange:
        return TargetRange(self.target_overheads_min, self.target_overheads_max)

    @property
    def cm1_range(self) -> TargetRange:
        return TargetRange(self.target_cm1_min, self.target_cm1_max)

    @property
    def cm2_range(self) -> TargetRange:
        return TargetRange(self.target_cm2_min, self.target_cm2_max)

    @property
    def upload_dir_path(self) -> Path:
        """upload_dir resolved against the project root, regardless of CWD at runtime."""
        p = Path(self.upload_dir)
        return p if p.is_absolute() else (PROJECT_ROOT / p).resolve()

    @property
    def database_url_resolved(self) -> str:
        """database_url with a relative sqlite file path resolved against the project root."""
        prefix = "sqlite:///"
        if self.database_url.startswith(prefix):
            raw_path = self.database_url[len(prefix):]
            if raw_path != ":memory:" and not raw_path.startswith("/"):
                abs_path = (PROJECT_ROOT / raw_path).resolve()
                return f"{prefix}{abs_path}"
        return self.database_url

    def line_item_ranges(self) -> dict[str, TargetRange]:
        """Canonical line-item display name -> its target range."""
        return {
            "Manpower Cost": self.manpower_range,
            "Packaging Cost": self.packaging_range,
            "Power & Fuel": self.power_fuel_range,
            "FC Rent": self.fc_rent_range,
            "Equipment Rentals": self.equipment_range,
            "Overheads": self.overheads_range,
        }


@lru_cache
def get_settings() -> Settings:
    return Settings()
