#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Madeira Converter Exception: see ../LICENSE-EXCEPTION.md (this file only).
"""Sync reviewed map JSON into its standalone HTML; do not re-analyze evidence."""
import argparse
import json
from pathlib import Path
import re

DOCS = Path(__file__).resolve().parents[1] / "docs"
HTML = DOCS / "build100-to-217-ramification-map-detailed.html"
DATA = HTML.with_suffix(".json")
PATTERN = r'(<script id="map-data" type="application/json">)(.*?)(</script>)'


def validate(data):
    if [entry["number"] for entry in data["builds"]] != list(range(100, 218)):
        raise ValueError("Expected exactly Build100–217, in order")
    nodes = {node["id"]: node for node in data["phases"]}
    if len(nodes) != len(data["phases"]):
        raise ValueError("Duplicate phase ID")
    references = {item["id"] for item in data["evidence"]}
    if len(references) != len(data["evidence"]):
        raise ValueError("Duplicate evidence ID")

    def visit(key, ancestors):
        if key in ancestors or key not in nodes:
            raise ValueError("Invalid or cyclic dependency")
        for parent in nodes[key]["parents"]:
            visit(parent, ancestors | {key})

    for key, node in nodes.items():
        if not 100 <= node["from_build"] <= node["to_build"] <= 217:
            raise ValueError("Invalid phase range")
        visit(key, set())
    for item in [*data["phases"], *data["builds"], *data["bands"]]:
        if not set(item["refs"]) <= references:
            raise ValueError("Unknown evidence reference")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Validate without modifying the HTML")
    args = parser.parse_args()
    data = json.loads(DATA.read_text(encoding="utf-8"))
    validate(data)
    source = HTML.read_text(encoding="utf-8")
    matches = list(re.finditer(PATTERN, source, flags=re.S))
    if len(matches) != 1:
        raise ValueError("Expected one embedded JSON block")
    match = matches[0]
    if args.check:
        if json.loads(match[2]) != data:
            raise ValueError("Embedded HTML data differs from the reviewed JSON")
    else:
        payload = json.dumps(data, ensure_ascii=False, indent=2).replace("<", "\\u003c")
        HTML.write_text(source[:match.start(2)] + payload + source[match.end(2):], encoding="utf-8")
    print("PASS: build coverage, unique IDs, dependency graph, evidence references and embedded data")


if __name__ == "__main__":
    main()
