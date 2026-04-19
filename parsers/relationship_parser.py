"""
Parse Relationship List file — a pre-processed citation pairs file.

Supported formats:
  Tab/space separated: source_id [sep] target_id [optional: weight]
  e.g.:
    WOS:000123  WOS:000456
    AuthorA2001 AuthorB2005  1.5
"""
from __future__ import annotations
import re
import pandas as pd
import networkx as nx
from pathlib import Path


def parse_relationship_file(filepath: str | Path, separator: str = "auto") -> pd.DataFrame:
    """
    Parse a relationship/citation list file into a DataFrame of (source, target, weight).
    separator: 'tab', 'space', 'auto'
    """
    filepath = Path(filepath)
    lines = filepath.read_text(encoding="utf-8-sig", errors="replace").splitlines()

    rows = []
    for line in lines:
        line = line.strip()
        if not line or line.startswith("#"):
            continue

        if separator == "tab" or (separator == "auto" and "\t" in line):
            parts = line.split("\t")
        else:
            parts = re.split(r"\s+", line)

        if len(parts) >= 2:
            source = parts[0].strip()
            target = parts[1].strip()
            weight = float(parts[2]) if len(parts) >= 3 else 1.0
            if source and target and source != target:
                rows.append({"source": source, "target": target, "weight": weight})

    return pd.DataFrame(rows) if rows else pd.DataFrame(columns=["source", "target", "weight"])


def merge_multiple_wos_files(filepaths: list[str | Path]) -> pd.DataFrame:
    """
    Parse and merge multiple WOS export files into one DataFrame.
    Removes duplicate records by wos_id.
    """
    from .wos_parser import parse_wos_file
    dfs = []
    for fp in filepaths:
        try:
            df = parse_wos_file(fp)
            if not df.empty:
                dfs.append(df)
        except Exception as e:
            print(f"Warning: Could not parse {fp}: {e}")

    if not dfs:
        return pd.DataFrame()

    merged = pd.concat(dfs, ignore_index=True)
    if "wos_id" in merged.columns:
        merged = merged.drop_duplicates(subset=["wos_id"], keep="first")
    return merged.reset_index(drop=True)


def scan_folder_for_wos(folder: str | Path) -> list[Path]:
    """Return all .txt/.tsv/.csv files in a folder (non-recursive)."""
    folder = Path(folder)
    files = []
    for ext in ["*.txt", "*.tsv", "*.csv"]:
        files.extend(folder.glob(ext))
    return sorted(files)
