"""
Build citation network from WOS DataFrame.

WOS cited reference format:
  "Author LN FI, Year, Journal Abbr, Volume, Page, DOI 10.xxx"
  e.g. "HUMMON NP, 1989, SOC NETWORKS, V11, P39, DOI 10.1016/0378-8733(89)90023-4"

Matching strategy (in order of reliability):
  1. DOI exact match
  2. WOS accession number match (WOS:...)
  3. Author + Year + Journal + Volume + Page fuzzy match
"""
from __future__ import annotations
import re
import pandas as pd
import networkx as nx
from dataclasses import dataclass


@dataclass
class ParsedRef:
    raw: str
    first_author: str = ""
    year: str = ""
    journal: str = ""
    volume: str = ""
    page: str = ""
    doi: str = ""
    wos_accession: str = ""


def parse_wos_reference(ref_str: str) -> ParsedRef:
    """Parse a single WOS cited reference string into structured fields."""
    ref = ParsedRef(raw=ref_str.strip())
    parts = [p.strip() for p in ref_str.split(",")]

    if not parts:
        return ref

    # Author: first part — WOS format is "LASTNAME FI" (space, not comma).
    # Take only the first token (last name) to avoid trailing-space mismatches
    # when the last name is exactly 5 chars (e.g. "WEILL P"[:6] = "WEILL " ≠ "WEILL").
    raw_author = parts[0].strip().upper()
    ref.first_author = raw_author.split()[0] if raw_author else ""

    # Year: 4-digit number in parts
    for p in parts[1:4]:
        if re.match(r"^\d{4}$", p.strip()):
            ref.year = p.strip()
            break

    # Journal: typically 3rd or 4th part (uppercase abbreviation)
    year_idx = next((i for i, p in enumerate(parts) if re.match(r"^\d{4}$", p.strip())), 1)
    if year_idx + 1 < len(parts):
        ref.journal = parts[year_idx + 1].strip().upper()

    # Volume: starts with V followed by digits
    for p in parts:
        if re.match(r"^V\d+", p.strip(), re.IGNORECASE):
            ref.volume = re.sub(r"[^0-9]", "", p)
            break

    # Page: starts with P followed by digits
    for p in parts:
        if re.match(r"^P\d+", p.strip(), re.IGNORECASE):
            ref.page = re.sub(r"[^0-9]", "", p)
            break

    # DOI: look for "DOI 10.xxx" anywhere in the raw string
    doi_match = re.search(r"DOI\s+(10\.\S+)", ref_str, re.IGNORECASE)
    if doi_match:
        ref.doi = doi_match.group(1).upper().rstrip(".,;)")

    # WOS accession number
    wos_match = re.search(r"(WOS:\S+)", ref_str, re.IGNORECASE)
    if wos_match:
        ref.wos_accession = wos_match.group(1).upper()

    return ref


def build_citation_network(
    df: pd.DataFrame,
    matching_mode: str = "strict",
) -> tuple[nx.DiGraph, pd.DataFrame, dict]:
    """
    Build a directed citation network from a WOS DataFrame.

    matching_mode:
      "strict"     — DOI + WOS accession only (matches reference tool behavior)
      "standard"   — adds Author+Year+Vol+Page and Author+Year+Journal
      "aggressive" — adds unique Author+Year fallback

    Returns:
        G          : DiGraph where nodes = wos_id, edges = citations
        edge_df    : DataFrame(source, target, match_type)
        match_stats: dict with matching statistics
    """
    if "wos_id" not in df.columns or "cited_references" not in df.columns:
        return nx.DiGraph(), pd.DataFrame(columns=["source", "target", "match_type"]), {}

    # --- Build lookup indexes ---
    doi_index: dict[str, str] = {}       # DOI → wos_id
    wosid_index: dict[str, str] = {}     # WOS accession → wos_id
    author_year_index: dict[tuple, str] = {}  # (author, year, journal) → wos_id
    avp_index: dict[tuple, str] = {}     # (author, year, vol, page) → wos_id
    ay_index: dict[tuple, list] = {}     # (author, year) → [wos_id, ...] for unique-match fallback

    for _, row in df.iterrows():
        wid = str(row.get("wos_id", "")).strip()
        if not wid:
            continue

        doi = str(row.get("doi", "")).strip().upper()
        if doi and doi != "NAN":
            # Normalize DOI: strip URL prefixes and trailing junk
            doi = re.sub(r"^HTTPS?://DOI\.ORG/", "", doi)
            doi_index[doi] = wid

        wosid_index[wid.upper()] = wid

        authors = row.get("authors", [])
        first_author = ""
        if isinstance(authors, list) and authors:
            parts = authors[0].upper().split(",")
            first_author = parts[0].strip()
        elif isinstance(authors, str):
            first_author = authors.split(",")[0].strip().upper()

        year = str(row.get("year", "")).strip()
        if year == "nan" or year == "<NA>":
            year = ""
        journal = str(row.get("journal_abbr", row.get("journal", ""))).strip().upper()[:10]
        volume = str(row.get("volume", "")).strip()
        page = str(row.get("page_begin", "")).strip()

        if first_author and year:
            key3 = (first_author[:6], year, journal[:6])
            author_year_index[key3] = wid

            key_ay = (first_author[:6], year)
            ay_index.setdefault(key_ay, []).append(wid)

            if volume and page:
                key4 = (first_author[:6], year, volume, page)
                avp_index[key4] = wid

    # --- Match references ---
    edges = []
    stats = {"total_refs": 0, "matched_doi": 0, "matched_wosid": 0,
             "matched_author_year": 0, "unmatched": 0}

    for _, row in df.iterrows():
        citing_id = str(row.get("wos_id", "")).strip()
        refs = row.get("cited_references", [])
        if not isinstance(refs, list):
            continue

        for ref_str in refs:
            if not isinstance(ref_str, str) or not ref_str.strip():
                continue

            stats["total_refs"] += 1
            ref = parse_wos_reference(ref_str)
            matched_id = None
            match_type = ""

            # 1. DOI match (try both with and without URL prefix)
            if ref.doi:
                doi_clean = re.sub(r"^HTTPS?://DOI\.ORG/", "", ref.doi)
                if doi_clean in doi_index:
                    matched_id = doi_index[doi_clean]
                    match_type = "doi"
                    stats["matched_doi"] += 1

            # 2. WOS accession match
            if not matched_id and ref.wos_accession and ref.wos_accession in wosid_index:
                matched_id = wosid_index[ref.wos_accession]
                match_type = "wos_id"
                stats["matched_wosid"] += 1

            if matching_mode in ("standard", "aggressive"):
                # 3. Author + Year + Volume + Page
                if not matched_id and ref.first_author and ref.year and ref.volume and ref.page:
                    key4 = (ref.first_author[:6], ref.year, ref.volume, ref.page)
                    if key4 in avp_index:
                        matched_id = avp_index[key4]
                        match_type = "author_year_vol_page"
                        stats["matched_author_year"] += 1

                # 4. Author + Year + Journal (fallback after method 3)
                if not matched_id and ref.first_author and ref.year:
                    key3 = (ref.first_author[:6], ref.year, ref.journal[:6])
                    if key3 in author_year_index:
                        matched_id = author_year_index[key3]
                        match_type = "author_year_journal"
                        stats["matched_author_year"] += 1

            if matching_mode == "aggressive":
                # 5. Author + Year only — use only when exactly one candidate exists
                if not matched_id and ref.first_author and ref.year:
                    key_ay = (ref.first_author[:6], ref.year)
                    candidates = ay_index.get(key_ay, [])
                    if len(candidates) == 1:
                        matched_id = candidates[0]
                        match_type = "author_year_unique"
                        stats["matched_author_year"] += 1

            if matched_id and matched_id != citing_id:
                edges.append({
                    "source": matched_id,   # cited paper (older) → citing paper (newer)
                    "target": citing_id,
                    "match_type": match_type,
                })
            elif not matched_id:
                stats["unmatched"] += 1

    edge_df = pd.DataFrame(edges).drop_duplicates(subset=["source", "target"]) if edges else pd.DataFrame(columns=["source", "target", "match_type"])

    G = nx.from_pandas_edgelist(edge_df, source="source", target="target", create_using=nx.DiGraph())

    # Add all records as nodes (including isolated ones)
    for wid in df["wos_id"].dropna():
        if wid not in G:
            G.add_node(wid)

    # Add node attributes
    for _, row in df.iterrows():
        wid = str(row.get("wos_id", "")).strip()
        if wid in G:
            G.nodes[wid]["year"] = row.get("year", None)
            G.nodes[wid]["title"] = str(row.get("title", ""))[:80]
            G.nodes[wid]["times_cited"] = row.get("times_cited", 0)

    match_rate = (stats["total_refs"] - stats["unmatched"]) / max(stats["total_refs"], 1) * 100
    stats["match_rate_pct"] = round(match_rate, 1)

    return G, edge_df, stats
