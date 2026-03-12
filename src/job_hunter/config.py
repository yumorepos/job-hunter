from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
import os
from typing import Any


@dataclass(slots=True)
class ScoringWeights:
    title_keyword: float = 4.0
    description_keyword: float = 2.0
    tag_keyword: float = 3.0
    preferred_role: float = 3.0
    remote_preference: float = 2.0
    location_preference: float = 2.0
    junior_preference: float = 1.5
    company_preference: float = 2.0
    freshness_boost: float = 2.5
    stale_penalty_per_day: float = 0.2
    duplicate_penalty: float = 2.0


@dataclass(slots=True)
class Settings:
    db_path: Path = Path("jobs.db")
    digest_path: Path = Path("digest.md")
    request_timeout: float = 15.0
    max_retries: int = 2
    backoff_seconds: float = 0.7
    proxy_url: str = ""

    include_keywords: list[str] = field(
        default_factory=lambda: ["python", "data", "automation", "backend", "developer"]
    )
    exclude_keywords: list[str] = field(default_factory=lambda: ["senior", "staff", "principal"])
    preferred_locations: list[str] = field(default_factory=lambda: ["remote", "canada", "montreal"])
    preferred_roles: list[str] = field(
        default_factory=lambda: ["python developer", "data analyst", "automation", "backend"]
    )
    preferred_companies: list[str] = field(default_factory=list)
    seniority_target: str = "junior"
    min_relevance_score: float = 3.0
    similarity_threshold: float = 0.9

    weights: ScoringWeights = field(default_factory=ScoringWeights)


DEFAULT_SETTINGS = Settings()


def _split_list(value: str) -> list[str]:
    return [part.strip() for part in value.split(",") if part.strip()]


def _merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    result = dict(base)
    for key, value in override.items():
        if value is None:
            continue
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _merge(result[key], value)
        else:
            result[key] = value
    return result


def _parse_simple_toml(raw: str) -> dict[str, Any]:
    parsed: dict[str, Any] = {}
    for line in raw.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = [part.strip() for part in line.split("=", maxsplit=1)]
        if value.startswith("[") and value.endswith("]"):
            entries = [v.strip().strip('"').strip("'") for v in value[1:-1].split(",") if v.strip()]
            parsed[key] = entries
        elif value.replace(".", "", 1).isdigit():
            parsed[key] = float(value) if "." in value else int(value)
        else:
            parsed[key] = value.strip('"').strip("'")
    return parsed


def _from_toml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    content = _parse_simple_toml(path.read_text(encoding="utf-8"))
    return {
        "include_keywords": content.get("keywords"),
        "exclude_keywords": content.get("exclude"),
        "preferred_locations": content.get("locations"),
        "min_relevance_score": content.get("min_score"),
        "preferred_roles": content.get("roles"),
        "preferred_companies": content.get("companies"),
        "proxy_url": content.get("proxy_url"),
    }


def _from_env() -> dict[str, Any]:
    env: dict[str, Any] = {}
    if os.getenv("JOB_HUNTER_DB"):
        env["db_path"] = Path(os.environ["JOB_HUNTER_DB"])
    if os.getenv("JOB_HUNTER_DIGEST_PATH"):
        env["digest_path"] = Path(os.environ["JOB_HUNTER_DIGEST_PATH"])
    if os.getenv("JOB_HUNTER_TIMEOUT"):
        env["request_timeout"] = float(os.environ["JOB_HUNTER_TIMEOUT"])
    if os.getenv("JOB_HUNTER_MAX_RETRIES"):
        env["max_retries"] = int(os.environ["JOB_HUNTER_MAX_RETRIES"])
    if os.getenv("JOB_HUNTER_BACKOFF"):
        env["backoff_seconds"] = float(os.environ["JOB_HUNTER_BACKOFF"])
    if os.getenv("JOB_HUNTER_MIN_SCORE"):
        env["min_relevance_score"] = float(os.environ["JOB_HUNTER_MIN_SCORE"])
    if os.getenv("JOB_HUNTER_SENIORITY"):
        env["seniority_target"] = os.environ["JOB_HUNTER_SENIORITY"]
    if os.getenv("JOB_HUNTER_PROXY"):
        env["proxy_url"] = os.environ["JOB_HUNTER_PROXY"]
    if os.getenv("JOB_HUNTER_KEYWORDS"):
        env["include_keywords"] = _split_list(os.environ["JOB_HUNTER_KEYWORDS"])
    if os.getenv("JOB_HUNTER_EXCLUDE"):
        env["exclude_keywords"] = _split_list(os.environ["JOB_HUNTER_EXCLUDE"])
    if os.getenv("JOB_HUNTER_LOCATIONS"):
        env["preferred_locations"] = _split_list(os.environ["JOB_HUNTER_LOCATIONS"])
    if os.getenv("JOB_HUNTER_COMPANIES"):
        env["preferred_companies"] = _split_list(os.environ["JOB_HUNTER_COMPANIES"])
    return env


def load_settings(
    config_path: Path | None = None, cli_overrides: dict[str, Any] | None = None
) -> Settings:
    config_file = config_path or Path("config.toml")
    merged = _merge(asdict(DEFAULT_SETTINGS), _from_toml(config_file))
    merged = _merge(merged, _from_env())
    merged = _merge(merged, cli_overrides or {})

    weights = ScoringWeights(**merged.pop("weights", {}))
    for key in ("db_path", "digest_path"):
        value = merged.get(key)
        if value is not None and not isinstance(value, Path):
            merged[key] = Path(value)
    return Settings(weights=weights, **merged)
