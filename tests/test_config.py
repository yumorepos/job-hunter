from pathlib import Path

from job_hunter.config import load_settings


def test_load_settings_config_file_and_cli_override(tmp_path: Path):
    config_path = tmp_path / "config.toml"
    config_path.write_text(
        'keywords=["python"]\nexclude=["staff"]\nlocations=["remote"]\nmin_score=12\n',
        encoding="utf-8",
    )
    settings = load_settings(config_path=config_path, cli_overrides={"min_relevance_score": 30})
    assert settings.include_keywords == ["python"]
    assert settings.exclude_keywords == ["staff"]
    assert settings.preferred_locations == ["remote"]
    assert settings.min_relevance_score == 30
