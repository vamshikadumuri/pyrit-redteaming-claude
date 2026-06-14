# tests/ingest/test_xlsx_reader.py
from pathlib import Path

from agentic_redteam.ingest.xlsx_reader import read_sheet

XLSX = Path(__file__).resolve().parents[2] / "promptfoo_plugins_catalog_1.xlsx"


def test_reads_plugins_sheet_as_dicts():
    rows = read_sheet(XLSX, "Plugins")
    assert len(rows) == 157
    assert "Plugin ID" in rows[0]
    ids = {r["Plugin ID"] for r in rows}
    assert "excessive-agency" in ids
    assert "pii:direct" in ids


def test_reads_strategy_and_preset_sheets():
    assert len(read_sheet(XLSX, "Strategy Map")) == 35
    assert len(read_sheet(XLSX, "Presets")) == 85


def test_unknown_sheet_raises():
    import pytest

    with pytest.raises(KeyError):
        read_sheet(XLSX, "NoSuchSheet")
