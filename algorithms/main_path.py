"""
Main Path Analysis (MPA) và Key-route Main Path Analysis (KRMPA).

MPA  : tìm một đường đi chính (xương sống) trong mạng trích dẫn
       → Global Standard / Local Forward / Local Backward

KRMPA: tìm top-N key route edges → mở rộng mỗi edge thành path hoàn chỉnh
       → phản ánh nhiều nhánh phát triển song song
       → Global Key-route / Local Key-route

Reference: Liu & Lu (2012), Hummon & Doreian (1989)
"""
from __future__ import annotations
import networkx as nx
import pandas as pd
from typing import Literal

SearchStrategy = Literal["local", "global"]


# ---------------------------------------------------------------------------
# Public API — MPA
# ---------------------------------------------------------------------------

def find_main_path(
    G: nx.DiGraph,
    strategy: SearchStrategy = "global",
    mode: str = "standard",
    weight_attr: str = "weight",
    tie_tolerance: float = 0.0,
    n_significant_routes: int = 10,
) -> list[str]:
    """
    MPA: tìm một đường đi chính duy nhất.
    strategy='global', mode='standard' → DP optimal (khuyến nghị cho MPA)
    strategy='local', mode='forward'   → greedy forward
    strategy='local', mode='backward'  → greedy backward
    """
    if G.number_of_edges() == 0:
        return []
    if strategy == "local":
        return _local_search(G, mode, weight_attr, tie_tolerance)
    return _global_search(G, weight_attr)


def find_multiple_main_paths(
    G: nx.DiGraph,
    n_paths: int = 3,
    strategy: SearchStrategy = "global",
    mode: str = "standard",
    weight_attr: str = "weight",
    tie_tolerance: float = 0.0,
    n_significant_routes: int = 10,
) -> list[list[str]]:
    """
    MPA lặp: tìm N đường bằng cách xóa edges của path đã tìm rồi tìm tiếp.
    Mỗi path độc lập, không chia sẻ edges.
    """
    G_copy = G.copy()
    paths = []
    for _ in range(n_paths):
        if G_copy.number_of_edges() == 0:
            break
        path = find_main_path(
            G_copy, strategy=strategy, mode=mode,
            weight_attr=weight_attr, tie_tolerance=tie_tolerance,
        )
        if not path:
            break
        paths.append(path)
        for i in range(len(path) - 1):
            if G_copy.has_edge(path[i], path[i + 1]):
                G_copy.remove_edge(path[i], path[i + 1])
    return paths


# ---------------------------------------------------------------------------
# Public API — KRMPA (Key-route Main Path Analysis)
# ---------------------------------------------------------------------------

def find_key_route_main_paths(
    G: nx.DiGraph,
    n_significant_routes: int = 10,
    weight_attr: str = "weight",
    strategy: SearchStrategy = "global",
    tie_tolerance: float = 0.0,
) -> list[list[str]]:
    """
    Key-route Main Path Analysis (KRMPA).

    Thuật toán:
      1. Sắp xếp tất cả edges theo traversal weight giảm dần
      2. Chọn top-N edges làm "key routes"
      3. Với mỗi key route edge (u → v):
           - Trace ngược từ u → source (greedy theo weight)
           - Trace xuôi từ v → sink   (greedy theo weight)
           - Ghép: backward_path + [u, v] + forward_path
      4. Trả về danh sách N paths (có thể chia sẻ nodes/edges)

    Kết quả thể hiện nhiều nhánh phát triển song song của lĩnh vực.
    """
    if G.number_of_edges() == 0:
        return []

    # Bước 1: lấy top-N key route edges
    edges_sorted = sorted(
        G.edges(data=True),
        key=lambda e: e[2].get(weight_attr, 0),
        reverse=True,
    )
    key_edges = [(u, v) for u, v, _ in edges_sorted[:n_significant_routes]]

    paths = []
    seen_paths = set()

    def _add_path(full_path: list[str]) -> None:
        full_path = _deduplicate_path(full_path)
        key = tuple(full_path)
        if key not in seen_paths and len(full_path) >= 2:
            seen_paths.add(key)
            paths.append(full_path)

    for u, v in key_edges:
        back = _trace_backward(G, u, weight_attr, tie_tolerance)
        fwd  = _trace_forward(G, v, weight_attr, tie_tolerance)
        base_path = back + [u, v] + fwd
        _add_path(base_path)

        # Expand tied SOURCE alternatives (sibling nodes with same SPLC to next hop).
        source = back[0] if back else u
        next_hop = back[1] if len(back) > 1 else u
        tied_sources = _get_tied_predecessors(G, source, next_hop, weight_attr, tie_tolerance)
        for alt in tied_sources:
            _add_path([alt] + (back[1:] if back else []) + [u, v] + fwd)

        # Expand tied alternatives at the first forward step from v.
        # e.g. if v=MengWL2024 has tied successors [ZhangZ2025, ShaoL2024, LiuF2025],
        # generate a separate path for each alternative.
        if fwd:
            first_fwd = fwd[0]
            for alt_first in _get_tied_successors(G, v, first_fwd, weight_attr, tie_tolerance):
                alt_rest = _trace_forward(G, alt_first, weight_attr, tie_tolerance)
                _add_path(back + [u, v] + [alt_first] + alt_rest)

    return paths


def find_main_paths_by_year(
    G: nx.DiGraph,
    df: pd.DataFrame,
    strategy: SearchStrategy = "global",
    mode: str = "key-route",
    weight_attr: str = "weight",
    year_from: int | None = None,
    year_to: int | None = None,
    year_col: str = "year",
    id_col: str = "wos_id",
) -> dict[int, list[str]]:
    """Partition network by year and find main path per year."""
    if year_col not in df.columns or id_col not in df.columns:
        return {}

    year_map = dict(zip(df[id_col], df[year_col]))
    years = sorted(df[year_col].dropna().unique())

    if year_from:
        years = [y for y in years if y >= year_from]
    if year_to:
        years = [y for y in years if y <= year_to]

    results = {}
    for year in years:
        nodes_in_year = [n for n, y in year_map.items() if pd.notna(y) and y == year and n in G.nodes()]
        if len(nodes_in_year) < 2:
            continue
        subgraph = G.subgraph(nodes_in_year).copy()
        if subgraph.number_of_edges() == 0:
            continue
        path = find_main_path(subgraph, strategy=strategy, mode=mode, weight_attr=weight_attr)
        if path:
            results[int(year)] = path
    return results


def filter_graph_by_year(
    G: nx.DiGraph,
    df: pd.DataFrame,
    year_from: int | None = None,
    year_to: int | None = None,
    id_col: str = "wos_id",
    year_col: str = "year",
) -> nx.DiGraph:
    """Return subgraph containing only nodes within year range."""
    if year_from is None and year_to is None:
        return G

    import pandas as pd
    year_map = dict(zip(df[id_col], df[year_col]))
    keep = set()
    for node in G.nodes():
        yr = year_map.get(node)
        if yr is None or (hasattr(pd, "isna") and pd.isna(yr)):
            keep.add(node)
            continue
        try:
            yr_int = int(yr)
        except (ValueError, TypeError):
            keep.add(node)
            continue
        if year_from and yr_int < year_from:
            continue
        if year_to and yr_int > year_to:
            continue
        keep.add(node)

    return G.subgraph(keep).copy()


# ---------------------------------------------------------------------------
# Local search implementations
# ---------------------------------------------------------------------------

def _local_search(
    G: nx.DiGraph,
    mode: str,
    weight_attr: str,
    tie_tolerance: float,
) -> list[str]:
    if mode == "backward":
        return _local_backward(G, weight_attr, tie_tolerance)
    else:
        return _local_forward(G, weight_attr, tie_tolerance)


def _local_forward(G: nx.DiGraph, weight_attr: str, tie_tolerance: float) -> list[str]:
    """Forward greedy: from source, always follow highest-weight edge."""
    sources = [n for n in G.nodes() if G.in_degree(n) == 0]
    if not sources:
        sources = list(G.nodes())

    best_path, best_weight = [], -1.0

    for start in sources:
        path = [start]
        visited = {start}
        node = start
        while True:
            candidates = [
                (v, G[node][v].get(weight_attr, 0))
                for v in G.successors(node) if v not in visited
            ]
            if not candidates:
                break
            max_w = max(w for _, w in candidates)
            # Apply tie tolerance: accept edges within tolerance of max
            tied = [v for v, w in candidates if w >= max_w * (1 - tie_tolerance) - 1e-9]
            node = tied[0]
            path.append(node)
            visited.add(node)

        total = sum(
            G[path[i]][path[i + 1]].get(weight_attr, 0)
            for i in range(len(path) - 1)
        )
        if total > best_weight:
            best_weight = total
            best_path = path

    return best_path


def _local_backward(G: nx.DiGraph, weight_attr: str, tie_tolerance: float) -> list[str]:
    """Backward greedy: from sinks, trace back through highest-weight predecessors."""
    sinks = [n for n in G.nodes() if G.out_degree(n) == 0]
    if not sinks:
        return []

    best_path, best_weight = [], -1.0

    for end in sinks:
        path = [end]
        visited = {end}
        node = end
        while True:
            candidates = [
                (u, G[u][node].get(weight_attr, 0))
                for u in G.predecessors(node) if u not in visited
            ]
            if not candidates:
                break
            max_w = max(w for _, w in candidates)
            tied = [u for u, w in candidates if w >= max_w * (1 - tie_tolerance) - 1e-9]
            node = tied[0]
            path.append(node)
            visited.add(node)

        path.reverse()
        total = sum(
            G[path[i]][path[i + 1]].get(weight_attr, 0)
            for i in range(len(path) - 1)
        )
        if total > best_weight:
            best_weight = total
            best_path = path

    return best_path


# ---------------------------------------------------------------------------
# Global search (DP)
# ---------------------------------------------------------------------------

def _global_search(G: nx.DiGraph, weight_attr: str) -> list[str]:
    """Global optimal: DP to find path with maximum total weight."""
    if not nx.is_directed_acyclic_graph(G):
        return _local_forward(G, weight_attr, 0.0)

    topo = list(nx.topological_sort(G))
    sources = {n for n in G.nodes() if G.in_degree(n) == 0}
    sinks = {n for n in G.nodes() if G.out_degree(n) == 0}

    dp = {n: (-float("inf"), None) for n in G.nodes()}
    for s in sources:
        dp[s] = (0.0, None)

    for node in topo:
        if dp[node][0] == -float("inf") and node not in sources:
            continue
        for succ in G.successors(node):
            edge_w = G[node][succ].get(weight_attr, 0)
            candidate = dp[node][0] + edge_w
            if candidate > dp[succ][0]:
                dp[succ] = (candidate, node)

    if not sinks:
        return []
    best_sink = max(sinks, key=lambda s: dp[s][0])
    if dp[best_sink][0] == -float("inf"):
        return []

    path = []
    node = best_sink
    while node is not None:
        path.append(node)
        node = dp[node][1]
    path.reverse()
    return path


# ---------------------------------------------------------------------------
# KRMPA helpers
# ---------------------------------------------------------------------------

def _get_tied_predecessors(
    G: nx.DiGraph, node: str, next_hop: str, weight_attr: str, tie_tolerance: float
) -> list[str]:
    """
    Return all OTHER predecessors of next_hop whose edge weight ties with the
    edge (node → next_hop). Used to expand sibling source paths in KRMPA.
    """
    ref_w = G[node][next_hop].get(weight_attr, 0) if G.has_edge(node, next_hop) else 0
    if ref_w == 0:
        return []
    threshold = ref_w * (1 - tie_tolerance) - 1e-9
    return [
        u for u in G.predecessors(next_hop)
        if u != node and G[u][next_hop].get(weight_attr, 0) >= threshold
    ]


def _get_tied_successors(
    G: nx.DiGraph, node: str, chosen_sink: str, weight_attr: str, tie_tolerance: float
) -> list[str]:
    """
    Return all OTHER successors of node whose edge weight ties with the
    edge (node → chosen_sink). Used to expand sibling sink paths in KRMPA.
    """
    ref_w = G[node][chosen_sink].get(weight_attr, 0) if G.has_edge(node, chosen_sink) else 0
    if ref_w == 0:
        return []
    threshold = ref_w * (1 - tie_tolerance) - 1e-9
    return [
        v for v in G.successors(node)
        if v != chosen_sink and G[node][v].get(weight_attr, 0) >= threshold
    ]


def _trace_backward(G: nx.DiGraph, start: str, weight_attr: str, tie_tolerance: float) -> list[str]:
    """Từ node 'start', trace ngược về source theo highest-weight incoming edge."""
    path = []
    node = start
    visited = {node}
    while True:
        candidates = [
            (u, G[u][node].get(weight_attr, 0))
            for u in G.predecessors(node) if u not in visited
        ]
        if not candidates:
            break
        max_w = max(w for _, w in candidates)
        best = [u for u, w in candidates if w >= max_w * (1 - tie_tolerance) - 1e-9]
        node = best[0]
        path.append(node)
        visited.add(node)
    path.reverse()
    return path


def _trace_forward(G: nx.DiGraph, start: str, weight_attr: str, tie_tolerance: float) -> list[str]:
    """Từ node 'start', trace xuôi về sink theo highest-weight outgoing edge."""
    path = []
    node = start
    visited = {node}
    while True:
        candidates = [
            (v, G[node][v].get(weight_attr, 0))
            for v in G.successors(node) if v not in visited
        ]
        if not candidates:
            break
        max_w = max(w for _, w in candidates)
        best = [v for v, w in candidates if w >= max_w * (1 - tie_tolerance) - 1e-9]
        node = best[0]
        path.append(node)
        visited.add(node)
    return path


def _deduplicate_path(path: list[str]) -> list[str]:
    """Loại bỏ consecutive duplicates trong path."""
    if not path:
        return path
    result = [path[0]]
    for node in path[1:]:
        if node != result[-1]:
            result.append(node)
    return result


# ---------------------------------------------------------------------------
# Result utilities
# ---------------------------------------------------------------------------

def make_author_year_label(row: dict) -> str:
    """
    Create AuthorYear citation key matching the reference tool format.
    Format: FirstAuthorLastName + FirstInitialOfEachCoAuthorLastName + Year
    Example: ['Bradley, RV', 'Byrd, TA', 'Pridmore, JL'] → 'BradleyBP2012'
    """
    import pandas as pd
    authors = row.get("authors", [])
    if isinstance(authors, str):
        authors = [a.strip() for a in authors.split(";") if a.strip()]
    if not isinstance(authors, list):
        authors = []

    if not authors:
        return row.get("wos_id", "")[:10]

    import unicodedata

    def _ascii(s: str) -> str:
        """Normalize accented characters to ASCII (e.g. Héroux → Heroux)."""
        return unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode("ascii")

    # First author last name (part before the comma), accent-normalized
    first_last = _ascii(authors[0].split(",")[0].strip())

    # First letter of each co-author's last name, accent-normalized
    co_initials = "".join(
        _ascii(a.split(",")[0].strip())[0].upper()
        for a in authors[1:]
        if _ascii(a.split(",")[0].strip())
    )

    yr = row.get("year", "")
    year = str(int(yr)) if yr and pd.notna(yr) else ""
    return f"{first_last}{co_initials}{year}"


def path_to_df(
    path: list[str],
    df: pd.DataFrame,
    G: nx.DiGraph,
    weight_attr: str = "weight",
    id_col: str = "wos_id",
) -> pd.DataFrame:
    """Convert main path to DataFrame with record info and weights."""
    if not path or df is None or df.empty:
        return pd.DataFrame()

    record_map = df.set_index(id_col).to_dict("index") if id_col in df.columns else {}
    rows = []
    for i, node in enumerate(path):
        edge_weight = None
        inflow = outflow = None
        if i < len(path) - 1:
            next_node = path[i + 1]
            if G.has_edge(node, next_node):
                edge_data = G[node][next_node]
                edge_weight = edge_data.get(weight_attr)
                inflow = edge_data.get("inflow")
                outflow = edge_data.get("outflow")

        record = record_map.get(node, {})
        authors = record.get("authors", [])
        author_str = "; ".join(authors[:3]) + ("..." if len(authors) > 3 else "") if isinstance(authors, list) else str(authors)

        yr_val = record.get("year", "")
        tc_val = record.get("times_cited", "")
        rows.append({
            "position": i + 1,
            "label": make_author_year_label(record) if record else node,
            "wos_id": node,
            "title": record.get("title", ""),
            "authors": author_str,
            "year": int(yr_val) if yr_val and pd.notna(yr_val) else "",
            "journal": record.get("journal", ""),
            "times_cited": int(tc_val) if tc_val and pd.notna(tc_val) else 0,
            "doi": record.get("doi", ""),
            "edge_weight_to_next": round(edge_weight, 2) if edge_weight is not None else None,
            "inflow_paths": inflow,
            "outflow_paths": outflow,
        })

    return pd.DataFrame(rows)


def multiple_paths_to_df(
    paths: list[list[str]],
    df: pd.DataFrame,
    G: nx.DiGraph,
    weight_attr: str = "weight",
    id_col: str = "wos_id",
) -> pd.DataFrame:
    all_dfs = []
    for i, path in enumerate(paths):
        pdf = path_to_df(path, df, G, weight_attr, id_col)
        pdf.insert(0, "path_index", i + 1)
        all_dfs.append(pdf)
    return pd.concat(all_dfs, ignore_index=True) if all_dfs else pd.DataFrame()
