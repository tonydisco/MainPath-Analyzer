"""
Co-author network analysis.
Builds an undirected weighted network where edge weight = number of co-authored papers.
"""

import networkx as nx
import pandas as pd
from itertools import combinations


def build_coauthor_network(df: pd.DataFrame, author_col: str = "authors") -> nx.Graph:
    """
    Build co-author network from a WOS DataFrame.
    Edge weight = number of papers co-authored together.
    """
    G = nx.Graph()

    for _, row in df.iterrows():
        authors = row.get(author_col, [])
        if not isinstance(authors, list):
            continue
        authors = [a.strip() for a in authors if a.strip()]
        if len(authors) < 2:
            continue
        for a1, a2 in combinations(authors, 2):
            if G.has_edge(a1, a2):
                G[a1][a2]["weight"] += 1
                G[a1][a2]["papers"].append(str(row.get("wos_id", "")))
            else:
                G.add_edge(a1, a2, weight=1, papers=[str(row.get("wos_id", ""))])

    # Add node attributes
    for node in G.nodes():
        papers = df[df["authors"].apply(
            lambda x: node in x if isinstance(x, list) else False
        )]
        G.nodes[node]["paper_count"] = len(papers)
        G.nodes[node]["years"] = sorted(papers["year"].dropna().astype(int).tolist()) if "year" in papers.columns else []

    return G


def get_coauthor_stats(G: nx.Graph) -> pd.DataFrame:
    """Return a DataFrame with author-level statistics."""
    rows = []
    for node in G.nodes():
        collaborators = list(G.neighbors(node))
        total_collabs = sum(G[node][c]["weight"] for c in collaborators)
        rows.append({
            "author": node,
            "paper_count": G.nodes[node].get("paper_count", 0),
            "collaborator_count": len(collaborators),
            "total_collaborations": total_collabs,
            "degree_centrality": nx.degree_centrality(G).get(node, 0),
        })
    return pd.DataFrame(rows).sort_values("paper_count", ascending=False).reset_index(drop=True)


def get_coauthor_edges_df(G: nx.Graph) -> pd.DataFrame:
    """Return a DataFrame with all co-author edges and weights."""
    rows = []
    for u, v, data in G.edges(data=True):
        rows.append({
            "author_1": u,
            "author_2": v,
            "co_authored_papers": data.get("weight", 1),
            "paper_ids": "; ".join(data.get("papers", [])),
        })
    return pd.DataFrame(rows).sort_values("co_authored_papers", ascending=False).reset_index(drop=True)
