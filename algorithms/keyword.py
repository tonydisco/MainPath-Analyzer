"""
Keyword analysis.
- Frequency analysis (author keywords + Keywords Plus)
- Keyword co-occurrence network
- Jaccard similarity between documents based on keywords
- Keyword route (key_routes from MainPath)
"""

import networkx as nx
import pandas as pd
from collections import Counter
from itertools import combinations


def compute_keyword_frequency(
    df: pd.DataFrame,
    use_author_keywords: bool = True,
    use_keywords_plus: bool = True,
) -> pd.DataFrame:
    """Count keyword frequencies across all documents."""
    counts = Counter()
    for _, row in df.iterrows():
        kws = []
        if use_author_keywords:
            kws += row.get("keywords_author", []) or []
        if use_keywords_plus:
            kws += row.get("keywords_plus", []) or []
        for kw in kws:
            if isinstance(kw, str) and kw.strip():
                counts[kw.strip().lower()] += 1

    return pd.DataFrame(
        [{"keyword": k, "frequency": v} for k, v in counts.most_common()],
    )


def build_keyword_cooccurrence_network(
    df: pd.DataFrame,
    min_frequency: int = 2,
    use_author_keywords: bool = True,
    use_keywords_plus: bool = True,
) -> nx.Graph:
    """
    Build keyword co-occurrence network.
    Edge weight = number of documents where both keywords appear together.
    """
    freq_df = compute_keyword_frequency(df, use_author_keywords, use_keywords_plus)
    valid_kws = set(freq_df[freq_df["frequency"] >= min_frequency]["keyword"])

    G = nx.Graph()

    for _, row in df.iterrows():
        kws = []
        if use_author_keywords:
            kws += row.get("keywords_author", []) or []
        if use_keywords_plus:
            kws += row.get("keywords_plus", []) or []

        kws = list({kw.strip().lower() for kw in kws if isinstance(kw, str) and kw.strip().lower() in valid_kws})

        for k in kws:
            if k not in G:
                G.add_node(k, frequency=int(freq_df[freq_df["keyword"] == k]["frequency"].iloc[0]))

        for k1, k2 in combinations(kws, 2):
            if G.has_edge(k1, k2):
                G[k1][k2]["weight"] += 1
            else:
                G.add_edge(k1, k2, weight=1)

    return G


def compute_jaccard_similarity(df: pd.DataFrame, id_col: str = "wos_id") -> pd.DataFrame:
    """
    Compute pairwise Jaccard similarity between documents based on keywords.
    Returns DataFrame with columns: doc1, doc2, jaccard.
    """
    doc_keywords = {}
    for _, row in df.iterrows():
        doc_id = row.get(id_col, "")
        kws = set()
        for kw_list in [row.get("keywords_author", []), row.get("keywords_plus", [])]:
            if isinstance(kw_list, list):
                kws.update(kw.strip().lower() for kw in kw_list if isinstance(kw, str))
        if kws:
            doc_keywords[doc_id] = kws

    rows = []
    doc_ids = list(doc_keywords.keys())
    for i, d1 in enumerate(doc_ids):
        for d2 in doc_ids[i + 1:]:
            s1, s2 = doc_keywords[d1], doc_keywords[d2]
            intersection = len(s1 & s2)
            union = len(s1 | s2)
            if union > 0:
                rows.append({
                    "doc1": d1,
                    "doc2": d2,
                    "jaccard": round(intersection / union, 4),
                    "shared_keywords": "; ".join(sorted(s1 & s2)),
                })

    return pd.DataFrame(rows).sort_values("jaccard", ascending=False).reset_index(drop=True)


def get_keyword_stats(G: nx.Graph) -> pd.DataFrame:
    """Return keyword-level stats from co-occurrence network."""
    rows = []
    centrality = nx.degree_centrality(G)
    betweenness = nx.betweenness_centrality(G, weight="weight")
    for node in G.nodes():
        rows.append({
            "keyword": node,
            "frequency": G.nodes[node].get("frequency", 0),
            "co_occurrence_links": G.degree(node),
            "degree_centrality": round(centrality.get(node, 0), 4),
            "betweenness_centrality": round(betweenness.get(node, 0), 4),
        })
    return pd.DataFrame(rows).sort_values("frequency", ascending=False).reset_index(drop=True)
