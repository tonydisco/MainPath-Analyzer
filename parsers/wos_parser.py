"""
Web of Science plain-text export parser.
Supports tab-delimited and plain-text (tagged) formats.
"""

from __future__ import annotations
import re
import pandas as pd
from pathlib import Path


WOS_FIELD_MAP = {
    "PT": "publication_type",
    "AU": "authors",
    "AF": "authors_full",
    "TI": "title",
    "SO": "journal",
    "AB": "abstract",
    "DE": "keywords_author",
    "ID": "keywords_plus",
    "CR": "cited_references",
    "J9": "journal_abbr",
    "PY": "year",
    "VL": "volume",
    "IS": "issue",
    "BP": "page_begin",
    "EP": "page_end",
    "DI": "doi",
    "UT": "wos_id",
    "TC": "times_cited",
    "C1": "affiliations",
    "RP": "reprint_author",
    "EM": "email",
    "RI": "researcher_id",
    "OI": "orcid",
    "NR": "cited_ref_count",
    "Z9": "total_times_cited",
    "SC": "subject_categories",
    "WC": "wos_categories",
    "LA": "language",
    "DT": "document_type",
    "SN": "issn",
    "EI": "eissn",
    "PD": "publication_date",
    "SU": "supplement",
    "SI": "special_issue",
    "PN": "part_number",
    "AR": "article_number",
    "MA": "meeting_abstract",
}

MULTI_VALUE_FIELDS = {"AU", "AF", "CR", "DE", "ID", "C1", "SC", "WC"}


def parse_wos_file(filepath: str | Path) -> pd.DataFrame:
    """Parse a WOS plain-text export file and return a DataFrame."""
    filepath = Path(filepath)
    text = filepath.read_text(encoding="utf-8-sig", errors="replace")

    # Detect format: tab-delimited starts with "PT\tAU\t..."
    first_line = text.strip().splitlines()[0] if text.strip() else ""
    if "\t" in first_line and first_line.startswith("PT"):
        return _parse_tab_delimited(text)
    else:
        return _parse_tagged(text)


def _parse_tagged(text: str) -> pd.DataFrame:
    """Parse WOS tagged plain-text format (2-char field codes)."""
    records = []
    current = {}
    current_field = None
    current_values = []

    def flush_field():
        if current_field is None:
            return
        raw = WOS_FIELD_MAP.get(current_field, current_field.lower())
        if current_field in MULTI_VALUE_FIELDS:
            current[raw] = current_values[:]
        else:
            current[raw] = " ".join(current_values).strip()

    for line in text.splitlines():
        if line.startswith("ER"):
            flush_field()
            if current:
                records.append(current)
            current = {}
            current_field = None
            current_values = []
        elif line.startswith("EF"):
            break
        elif len(line) >= 2 and line[2:3] == " " and line[:2].strip():
            flush_field()
            current_field = line[:2].strip()
            current_values = [line[3:].strip()] if line[3:].strip() else []
        elif line.startswith("   ") and current_field:
            current_values.append(line.strip())

    return _normalize(pd.DataFrame(records))


def _parse_tab_delimited(text: str) -> pd.DataFrame:
    """Parse WOS tab-delimited export format."""
    from io import StringIO
    df = pd.read_csv(StringIO(text), sep="\t", dtype=str, low_memory=False)
    df.columns = [c.strip() for c in df.columns]

    rename = {}
    for wos_col, py_col in WOS_FIELD_MAP.items():
        if wos_col in df.columns:
            rename[wos_col] = py_col

    df = df.rename(columns=rename)

    for field in MULTI_VALUE_FIELDS:
        col = WOS_FIELD_MAP.get(field, field.lower())
        if col in df.columns:
            df[col] = df[col].apply(
                lambda x: [v.strip() for v in str(x).split(";") if v.strip()]
                if pd.notna(x) else []
            )

    return _normalize(df)


def _normalize(df: pd.DataFrame) -> pd.DataFrame:
    """Normalize and clean the DataFrame."""
    if df.empty:
        return df

    if "year" in df.columns:
        df["year"] = pd.to_numeric(df["year"], errors="coerce").astype("Int64")

    if "times_cited" in df.columns:
        df["times_cited"] = pd.to_numeric(df["times_cited"], errors="coerce").fillna(0).astype(int)

    if "cited_ref_count" in df.columns:
        df["cited_ref_count"] = pd.to_numeric(df["cited_ref_count"], errors="coerce").fillna(0).astype(int)

    # Ensure list fields are lists
    for field in MULTI_VALUE_FIELDS:
        col = WOS_FIELD_MAP.get(field, field.lower())
        if col in df.columns:
            df[col] = df[col].apply(
                lambda x: x if isinstance(x, list) else
                ([v.strip() for v in str(x).split(";") if v.strip()] if pd.notna(x) else [])
            )

    # Ensure wos_id exists
    if "wos_id" not in df.columns:
        df["wos_id"] = [f"REC_{i}" for i in range(len(df))]

    df = df.reset_index(drop=True)
    return df


def build_citation_pairs(df: pd.DataFrame) -> pd.DataFrame:
    """
    Build a DataFrame of (citing_id, cited_id) pairs by matching
    cited references against known WOS records.
    Returns edges DataFrame with columns: source, target.
    """
    if "wos_id" not in df.columns or "cited_references" not in df.columns:
        return pd.DataFrame(columns=["source", "target"])

    # Build lookup: DOI and title fragment → wos_id
    doi_map = {}
    title_map = {}
    wosid_set = set(df["wos_id"].dropna())

    for _, row in df.iterrows():
        wid = row.get("wos_id", "")
        doi = str(row.get("doi", "")).strip().upper()
        title = str(row.get("title", "")).strip().lower()[:40]
        if doi and doi != "NAN":
            doi_map[doi] = wid
        if title:
            title_map[title] = wid

    edges = []
    for _, row in df.iterrows():
        citing = row.get("wos_id", "")
        refs = row.get("cited_references", [])
        if not isinstance(refs, list):
            continue
        for ref in refs:
            ref = str(ref).strip()
            matched = _match_reference(ref, wosid_set, doi_map, title_map)
            if matched and matched != citing:
                edges.append({"source": citing, "target": matched})

    return pd.DataFrame(edges).drop_duplicates() if edges else pd.DataFrame(columns=["source", "target"])


def _match_reference(ref: str, wosid_set: set, doi_map: dict, title_map: dict) -> str | None:
    """Try to match a reference string to a known WOS ID."""
    # Direct WOS ID match
    if ref in wosid_set:
        return ref

    # DOI match: look for "DOI 10.xxx" pattern
    doi_match = re.search(r"DOI\s+(10\.\S+)", ref, re.IGNORECASE)
    if doi_match:
        doi = doi_match.group(1).upper().rstrip(".,;")
        if doi in doi_map:
            return doi_map[doi]

    # Title fragment match (first 40 chars)
    ref_lower = ref.lower()
    for title_frag, wid in title_map.items():
        if title_frag and title_frag in ref_lower:
            return wid

    return None
