import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from aviation_shortlist import load_leads, make_report  # noqa: E402


def test_applied_is_never_new():
    path = ROOT / "data" / "aviation_leads_example.csv"
    entries = load_leads(path)
    applied = [x for x in entries if x.application_status == "applied"]
    assert applied
    assert all(x.category() == "Already applied: follow up" for x in applied)
    report = make_report(entries, "2026-10-20")
    assert "Already applied: follow up" in report
    assert "New leads to review" in report


def test_french_requirement_blocks_new_shortlist():
    entries = load_leads(ROOT / "data" / "aviation_leads_example.csv")
    needs_french = [x for x in entries if x.french_requirement == "required"]
    assert needs_french
    assert all(
        x.category() in ("Lower priority or known mismatch", "Already applied: follow up")
        for x in needs_french
    )
    assert all(x.category() != "New leads to review" for x in needs_french)


def test_duplicate_detection(tmp_path):
    source = (ROOT / "data" / "aviation_leads_example.csv").read_text()
    sample = source.splitlines()
    duplicate = tmp_path / "dupe.csv"
    duplicate.write_text("\n".join([sample[0], sample[1], sample[1]]) + "\n")
    with pytest.raises(ValueError, match="repeated"):
        load_leads(duplicate)


def test_validation_rejects_http(tmp_path):
    source = (ROOT / "data" / "aviation_leads_example.csv").read_text()
    sample = source.splitlines()
    invalid = tmp_path / "invalid.csv"
    invalid.write_text("\n".join([sample[0], sample[1].replace("https://", "http://")]) + "\n")
    with pytest.raises(ValueError, match="HTTPS"):
        load_leads(invalid)
