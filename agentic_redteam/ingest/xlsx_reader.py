# agentic_redteam/ingest/xlsx_reader.py
"""Minimal stdlib xlsx reader (no pandas/openpyxl). Reads a worksheet into a
list of dicts keyed by the header row. Handles shared strings + inline strings."""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

_NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
_REL = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"


def _col_index(ref: str) -> int:
    m = re.match(r"[A-Z]+", ref)
    assert m is not None
    letters = m.group(0)
    idx = 0
    for ch in letters:
        idx = idx * 26 + (ord(ch) - ord("A") + 1)
    return idx - 1


def _shared_strings(z: zipfile.ZipFile) -> list[str]:
    if "xl/sharedStrings.xml" not in z.namelist():
        return []
    root = ET.fromstring(z.read("xl/sharedStrings.xml"))
    return ["".join(t.text or "" for t in si.iter(f"{_NS}t")) for si in root.findall(f"{_NS}si")]


def _sheet_paths(z: zipfile.ZipFile) -> dict[str, str]:
    wb = ET.fromstring(z.read("xl/workbook.xml"))
    rels = {
        r.get("Id"): r.get("Target") for r in ET.fromstring(z.read("xl/_rels/workbook.xml.rels"))
    }
    out: dict[str, str] = {}
    for s in wb.iter(f"{_NS}sheet"):
        rel_id = s.get(f"{_REL}id")
        assert rel_id is not None
        target: str = rels[rel_id]  # type: ignore[assignment]
        if target.startswith("/"):
            target = target[1:]
        elif not target.startswith("xl/"):
            target = "xl/" + target
        name = s.get("name")
        assert name is not None
        out[name] = target
    return out


def read_sheet(xlsx_path, sheet_name: str) -> list[dict[str, str]]:
    z = zipfile.ZipFile(Path(xlsx_path))
    shared = _shared_strings(z)
    paths = _sheet_paths(z)
    if sheet_name not in paths:
        raise KeyError(f"sheet {sheet_name!r} not found; have {list(paths)}")
    root = ET.fromstring(z.read(paths[sheet_name]))

    grid: list[list[str]] = []
    for row in root.iter(f"{_NS}row"):
        cells: dict[int, str] = {}
        maxc = -1
        for c in row.findall(f"{_NS}c"):
            ref = c.get("r")
            assert ref is not None
            ci = _col_index(ref)
            maxc = max(maxc, ci)
            t = c.get("t")
            v = c.find(f"{_NS}v")
            isel = c.find(f"{_NS}is")
            if t == "s" and v is not None:
                val = shared[int(v.text or 0)]
            elif t == "inlineStr" and isel is not None:
                val = "".join(x.text or "" for x in isel.iter(f"{_NS}t"))
            elif v is not None:
                val = v.text or ""
            else:
                val = ""
            cells[ci] = val.strip()
        grid.append([cells.get(i, "") for i in range(maxc + 1)])

    if not grid:
        return []
    header = grid[0]
    out = []
    for r in grid[1:]:
        r = r + [""] * (len(header) - len(r))
        out.append({header[i]: r[i] for i in range(len(header))})
    return out
