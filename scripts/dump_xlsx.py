"""Stdlib-only xlsx dumper. Writes each sheet to docs/_catalog_dump/<sheet>.tsv."""

import os
import re
import xml.etree.ElementTree as ET
import zipfile

NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
SRC = "promptfoo_plugins_catalog_1.xlsx"
OUT = "docs/_catalog_dump"
os.makedirs(OUT, exist_ok=True)

z = zipfile.ZipFile(SRC)

# shared strings
shared = []
if "xl/sharedStrings.xml" in z.namelist():
    sst = ET.fromstring(z.read("xl/sharedStrings.xml"))
    for si in sst.findall(f"{NS}si"):
        # concatenate all t descendants (handles rich text runs)
        text = "".join(t.text or "" for t in si.iter(f"{NS}t"))
        shared.append(text)


def col_index(ref):
    m = re.match(r"([A-Z]+)", ref)
    assert m is not None
    letters = m.group(1)
    idx = 0
    for ch in letters:
        idx = idx * 26 + (ord(ch) - ord("A") + 1)
    return idx - 1


sheet_files = {
    "Plugins": "xl/worksheets/sheet1.xml",
    "About": "xl/worksheets/sheet2.xml",
    "Presets": "xl/worksheets/sheet3.xml",
    "StrategyMap": "xl/worksheets/sheet4.xml",
}

for name, path in sheet_files.items():
    root = ET.fromstring(z.read(path))
    rows_out = []
    for row in root.iter(f"{NS}row"):
        cells = {}
        maxc = 0
        for c in row.findall(f"{NS}c"):
            ref = c.get("r")
            assert ref is not None
            ci = col_index(ref)
            maxc = max(maxc, ci)
            t = c.get("t")
            v = c.find(f"{NS}v")
            isel = c.find(f"{NS}is")
            if t == "s" and v is not None:
                val = shared[int(v.text or 0)]
            elif t == "inlineStr" and isel is not None:
                val = "".join(x.text or "" for x in isel.iter(f"{NS}t"))
            elif v is not None:
                val = v.text or ""
            else:
                val = ""
            cells[ci] = val.replace("\t", " ").replace("\n", " \\n ")
        rowlist = [cells.get(i, "") for i in range(maxc + 1)]
        rows_out.append(rowlist)
    with open(f"{OUT}/{name}.tsv", "w", encoding="utf-8") as f:
        for r in rows_out:
            f.write("\t".join(r) + "\n")
    print(f"{name}: {len(rows_out)} rows -> {OUT}/{name}.tsv")
