from dataclasses import dataclass
import os
from pathlib import Path

from dotenv import load_dotenv


load_dotenv()


@dataclass(frozen=True)
class Settings:
    app_name: str = os.getenv("APP_NAME", "OperaIQ")
    app_env: str = os.getenv("APP_ENV", "development")
    qdrant_url: str = os.getenv("QDRANT_URL", ":memory:")
    qdrant_path: str | None = os.getenv("QDRANT_PATH") or None
    qdrant_api_key: str | None = os.getenv("QDRANT_API_KEY") or None
    qdrant_collection: str = os.getenv("QDRANT_COLLECTION", "incident_memories")
    embedding_model: str = os.getenv("EMBEDDING_MODEL", "BAAI/bge-small-en-v1.5")
    allow_demo_reset: bool = os.getenv("ALLOW_DEMO_RESET", "true").lower() == "true"
    proof_artifacts_dir: Path = Path(os.getenv("PROOF_ARTIFACTS_DIR", "artifacts/proof"))

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
        if self.qdrant_mode == "memory":
            return ["production cannot use QDRANT_URL=:memory:"]
        return []


def get_settings() -> Settings:
    return Settings()
