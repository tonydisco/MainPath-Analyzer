"""
Traversal weight algorithms for citation networks.

SPC  - Search Path Count
SPLC - Search Path Link Count
SPNP - Search Path Node Pair

Output: raw (unnormalized) values matching MainPath reference tool.
Reference: Hummon & Doreian (1989), Liu & Lu (2012)
"""
from __future__ import annotations
import networkx as nx
import pandas as pd
from enum import Enum


class WeightMethod(str, Enum):
    SPC = "SPC"
    SPLC = "SPLC"
    SPNP = "SPNP"


def compute_weights(
    G: nx.DiGraph,
    method: WeightMethod = WeightMethod.SPLC,
    decay_factor: float = 0.2,
) -> nx.DiGraph:
    """
    Compute raw traversal weights for all edges in the citation DAG.
    Returns a new DiGraph with edge attributes: weight, inflow, outflow.
    """
    G = G.copy()
    G.remove_edges_from(nx.selfloop_edges(G))
    if not nx.is_directed_acyclic_graph(G):
        G = _make_dag(G)

    topo_order = list(nx.topological_sort(G))

    if method == WeightMethod.SPC:
        weights, node_fwd, node_bwd = _compute_spc(G, topo_order, decay_factor)
    elif method == WeightMethod.SPLC:
        weights, node_fwd, node_bwd = _compute_splc(G, topo_order, decay_factor)
    elif method == WeightMethod.SPNP:
        weights, node_fwd, node_bwd = _compute_spnp(G, topo_order, decay_factor)
    else:
        raise ValueError(f"Unknown method: {method}")

    for (u, v), w in weights.items():
        G[u][v]["weight"] = w
        G[u][v]["method"] = method.value
        # inflow = paths coming INTO source node u
        # outflow = paths going OUT from target node v
        G[u][v]["inflow"] = int(node_fwd.get(u, 0))
        G[u][v]["outflow"] = int(node_bwd.get(v, 0))

    return G


def _make_dag(G: nx.DiGraph) -> nx.DiGraph:
    """Remove back-edges to create a DAG."""
    try:
        for cycle in nx.simple_cycles(G):
            if len(cycle) > 1:
                if G.has_edge(cycle[-1], cycle[0]):
                    G.remove_edge(cycle[-1], cycle[0])
    except Exception:
        pass
    return G


def _compute_spc(G, topo_order, decay_factor=0.2):
    """SPC: raw path count through each edge."""
    sources = [n for n in G.nodes() if G.in_degree(n) == 0]
    sinks = [n for n in G.nodes() if G.out_degree(n) == 0]

    fwd = {n: 0.0 for n in G.nodes()}
    for s in sources:
        fwd[s] = 1.0
    for node in topo_order:
        for succ in G.successors(node):
            fwd[succ] += fwd[node]

    bwd = {n: 0.0 for n in G.nodes()}
    for s in sinks:
        bwd[s] = 1.0
    for node in reversed(topo_order):
        for pred in G.predecessors(node):
            bwd[pred] += bwd[node]

    weights = {}
    for u, v in G.edges():
        weights[(u, v)] = fwd[u] * bwd[v]

    return weights, fwd, bwd


def _compute_splc(G, topo_order, decay_factor=0.2):
    """
    SPLC: Search Path Link Count — paths from any node to any sink through edge.
    Formula: SPLC(u,v) = fwd_splc[u] × bwd_count[v]
      fwd_splc[v] = 1 + Σ_{p predecessor} fwd_splc[p]
                  = number of directed paths from ANY node (including v itself)
                    to v, treating every node as a potential path start
      bwd_count[v] = number of paths from v to any sink (source-sink backward count)
    Each node can originate a search path (not only in-degree-0 sources), so
    SPLC > SPC in general, matching MainPath 492 SPLC output.
    Reference: Hummon & Doreian (1989), Liu & Lu (2012).
    """
    sinks = [n for n in G.nodes() if G.out_degree(n) == 0]

    # Forward: each node contributes +1 as its own path-start
    fwd_splc = {n: 1.0 for n in G.nodes()}
    for node in topo_order:
        for succ in G.successors(node):
            fwd_splc[succ] += fwd_splc[node]

    # Backward: classic source-sink path count from sinks
    bwd_count = {n: 0.0 for n in G.nodes()}
    for s in sinks:
        bwd_count[s] = 1.0
    for node in reversed(topo_order):
        for pred in G.predecessors(node):
            bwd_count[pred] += bwd_count[node]

    weights = {}
    for u, v in G.edges():
        weights[(u, v)] = fwd_splc[u] * bwd_count[v]

    return weights, fwd_splc, bwd_count


def _compute_spnp(G, topo_order, decay_factor=0.2):
    """SPNP: source-sink node pair count through each edge."""
    sources = [n for n in G.nodes() if G.in_degree(n) == 0]
    sinks = [n for n in G.nodes() if G.out_degree(n) == 0]

    reachable_sinks = {n: set() for n in G.nodes()}
    for node in reversed(topo_order):
        if node in sinks:
            reachable_sinks[node].add(node)
        for succ in G.successors(node):
            reachable_sinks[node].update(reachable_sinks[succ])

    reachable_from = {n: set() for n in G.nodes()}
    for node in topo_order:
        if node in sources:
            reachable_from[node].add(node)
        for pred in G.predecessors(node):
            reachable_from[node].update(reachable_from[pred])

    fwd = {n: float(len(reachable_from[n])) for n in G.nodes()}
    bwd = {n: float(len(reachable_sinks[n])) for n in G.nodes()}

    weights = {}
    for u, v in G.edges():
        weights[(u, v)] = fwd[u] * bwd[v]

    return weights, fwd, bwd


def get_edge_weight_df(G: nx.DiGraph, top_n: int = 5000) -> pd.DataFrame:
    """
    Return DataFrame matching reference tool output format:
    Count, SPLC/weight, Relevancy, From => To, inflow paths, outflow paths
    """
    rows = []
    for u, v, data in G.edges(data=True):
        rows.append({
            "source": u,
            "target": v,
            "weight": data.get("weight", 0.0),
            "method": data.get("method", ""),
            "inflow_paths": data.get("inflow", 0),
            "outflow_paths": data.get("outflow", 0),
        })

    df = pd.DataFrame(rows)
    if df.empty:
        return df

    df = df.sort_values("weight", ascending=False).reset_index(drop=True)
    df.insert(0, "count", range(1, len(df) + 1))

    # Add Relevancy column (1.0 default, can be updated if relevancy strategy applied)
    df["relevancy"] = 1.0

    # Format output to match reference
    method = df["method"].iloc[0] if not df.empty else "SPLC"
    df = df.rename(columns={"weight": method})
    df["from_to"] = df["source"].astype(str) + " => " + df["target"].astype(str)

    output_cols = ["count", method, "relevancy", "from_to", "inflow_paths", "outflow_paths"]
    return df[output_cols].head(top_n)
