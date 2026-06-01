from dataclasses import dataclass, field
import os
from pathlib import Path

from dotenv import load_dotenv


load_dotenv()


def env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def env_str(name: str, default: str = "") -> str:
    return os.getenv(name, default)


def env_optional(name: str) -> str | None:
    value = os.getenv(name)
    return value or None


@dataclass(frozen=True)
class Settings:
    app_name: str = field(default_factory=lambda: env_str("APP_NAME", "OperaIQ"))
    app_env: str = field(default_factory=lambda: env_str("APP_ENV", "development"))
    qdrant_url: str = field(default_factory=lambda: env_str("QDRANT_URL", ":memory:"))
    qdrant_path: str | None = field(default_factory=lambda: env_optional("QDRANT_PATH"))
    qdrant_api_key: str | None = field(default_factory=lambda: env_optional("QDRANT_API_KEY"))
    qdrant_collection: str = field(
        default_factory=lambda: env_str("QDRANT_COLLECTION", "incident_memories")
    )
    embedding_model: str = field(
        default_factory=lambda: env_str("EMBEDDING_MODEL", "BAAI/bge-small-en-v1.5")
    )
    operaiq_api_token: str | None = field(default_factory=lambda: env_optional("OPERAIQ_API_TOKEN"))
    allow_unauthenticated_writes: bool = field(
        default_factory=lambda: env_bool(
            "ALLOW_UNAUTHENTICATED_WRITES",
            os.getenv("APP_ENV", "development").lower() != "production",
        )
    )
    allow_collection_reset: bool = field(
        default_factory=lambda: env_bool("ALLOW_COLLECTION_RESET", False)
    )
    proof_artifacts_dir: Path = field(
        default_factory=lambda: Path(env_str("PROOF_ARTIFACTS_DIR", "artifacts/proof"))
    )

    @property
    def qdrant_mode(self) -> str:
        if self.qdrant_url == ":memory:" and self.qdrant_path:
            return "local-path"
        if self.qdrant_url == ":memory:":
            return "memory"
        return "server"

    @property
    def is_production(self) -> bool:
        return self.app_env.lower() == "production"

    def production_issues(self) -> list[str]:
        if not self.is_production:
            return []
        issues: list[str] = []
        if self.qdrant_mode == "memory":
            issues.append("production cannot use QDRANT_URL=:memory:")
        if not self.operaiq_api_token and not self.allow_unauthenticated_writes:
            issues.append("production write paths require OPERAIQ_API_TOKEN")
        return issues

    def production_warnings(self) -> list[str]:
        if not self.is_production:
            return []
        warnings: list[str] = []
        if self.allow_unauthenticated_writes:
            warnings.append("production allows unauthenticated writes")
        if self.allow_collection_reset:
            warnings.append("collection reset is enabled")
        return warnings


def get_settings() -> Settings:
    return Settings()
