"""
Graph and chart visualizations using Plotly and PyVis.
Node colors match reference tool: green=source, red=on-path, blue=sink, gray=other
"""
from __future__ import annotations
import networkx as nx
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from pyvis.network import Network
import tempfile
import os


# ---------------------------------------------------------------------------
# Citation network / Main path visualization
# ---------------------------------------------------------------------------

def build_citation_network_html(
    G: nx.DiGraph,
    paths: list[list[str]],
    df: pd.DataFrame | None = None,
    id_col: str = "wos_id",
    weight_attr: str = "weight",
    height: int = 600,
) -> str:
    """
    Build interactive citation network using PyVis with hierarchical LR layout.
    Matches reference tool appearance:
      Green  = source nodes
      Red    = nodes on main path(s)
      Blue   = sink nodes
      Gray   = other nodes
    Returns HTML string for st.components.v1.html().
    """
    from algorithms.main_path import make_author_year_label

    if not G.nodes():
        return "<p>No graph data.</p>"

    # ── Build lookup maps ──
    label_map: dict[str, str] = {}
    cited_map: dict[str, int] = {}
    year_map: dict[str, int] = {}

    if df is not None and not df.empty and id_col in df.columns:
        for _, row in df.iterrows():
            nid = row[id_col]
            yr = row.get("year")
            year_map[nid] = int(yr) if pd.notna(yr) else 0
            tc = row.get("times_cited")
            cited_map[nid] = int(tc) if pd.notna(tc) else 0
            label_map[nid] = make_author_year_label(row.to_dict())

    # ── Classify nodes ──
    path_edges = set()
    for path in paths:
        for i in range(len(path) - 1):
            path_edges.add((path[i], path[i + 1]))
    path_nodes = set(n for path in paths for n in path)
    sources = {n for n in G.nodes() if G.in_degree(n) == 0}
    sinks   = {n for n in G.nodes() if G.out_degree(n) == 0}

    COLOR_SOURCE = "#27AE60"   # green
    COLOR_SINK   = "#2980B9"   # blue
    COLOR_PATH   = "#E74C3C"   # red
    COLOR_OTHER  = "#BDC3C7"   # gray
    BG_COLOR     = "#F5F0E8"   # reference tool beige

    # ── Compute hierarchical x positions (topological level) ──
    # Use year if available, else topological rank
    topo_level: dict[str, int] = {}
    try:
        if nx.is_directed_acyclic_graph(G):
            topo = list(nx.topological_sort(G))
            level: dict[str, int] = {n: 0 for n in G.nodes()}
            for node in topo:
                for succ in G.successors(node):
                    level[succ] = max(level[succ], level[node] + 1)
            topo_level = level
    except Exception:
        pass

    def node_x(nid: str) -> int:
        yr = year_map.get(nid, 0)
        if yr > 0:
            return yr
        return topo_level.get(nid, 0) * 3 + 1990

    # ── Build PyVis network ──
    net = Network(
        height=f"{height}px",
        width="100%",
        bgcolor=BG_COLOR,
        font_color="#2C3E50",
        directed=True,
    )

    # Use hierarchical layout (LR = left-to-right like reference)
    net.set_options("""
    {
      "layout": {
        "hierarchical": {
          "enabled": true,
          "direction": "LR",
          "sortMethod": "directed",
          "levelSeparation": 180,
          "nodeSpacing": 80,
          "treeSpacing": 200,
          "blockShifting": true,
          "edgeMinimization": true,
          "parentCentralization": true
        }
      },
      "physics": {
        "enabled": false
      },
      "edges": {
        "arrows": { "to": { "enabled": true, "scaleFactor": 0.6 } },
        "color": { "color": "#999999", "highlight": "#E74C3C" },
        "smooth": { "enabled": true, "type": "cubicBezier", "roundness": 0.4 },
        "width": 1
      },
      "nodes": {
        "shape": "dot",
        "font": { "size": 11, "face": "Arial" },
        "borderWidth": 1,
        "borderWidthSelected": 2
      },
      "interaction": {
        "hover": true,
        "tooltipDelay": 100,
        "zoomView": true,
        "dragView": true
      }
    }
    """)

    # ── Add nodes ──
    for node in G.nodes():
        label = label_map.get(node, node[:20])
        tc = cited_map.get(node, 0)
        yr = year_map.get(node, 0)
        x_pos = node_x(node)

        if node in sources and node in path_nodes:
            color, size, border = COLOR_SOURCE, 14, "#1A8A50"
        elif node in sinks and node in path_nodes:
            color, size, border = COLOR_SINK, 14, "#1A5C8A"
        elif node in path_nodes:
            color, size, border = COLOR_PATH, 12, "#A93226"
        else:
            color, size, border = COLOR_OTHER, 8, "#999999"

        title = f"<b>{label}</b><br>Year: {yr}<br>Cited: {tc}<br>ID: {node}"

        net.add_node(
            node,
            label=label,
            title=title,
            color={"background": color, "border": border,
                   "highlight": {"background": "#F39C12", "border": "#D68910"}},
            size=size,
            level=x_pos,   # PyVis hierarchical uses 'level' for LR x-position
        )

    # ── Add edges ──
    for u, v, data in G.edges(data=True):
        is_main = (u, v) in path_edges
        w = data.get(weight_attr, 0)
        net.add_edge(
            u, v,
            title=f"Weight: {w:.1f}",
            color="#C0392B" if is_main else "#BBBBBB",
            width=2.5 if is_main else 0.8,
            arrows="to",
        )

    # ── Save to temp file and read HTML ──
    with tempfile.NamedTemporaryFile(suffix=".html", delete=False, mode="w", encoding="utf-8") as f:
        net.save_graph(f.name)
        html = open(f.name, encoding="utf-8").read()
    os.unlink(f.name)

    # Inject legend overlay
    legend_html = f"""
    <div style="position:absolute;top:10px;left:10px;background:rgba(255,255,255,0.85);
                padding:8px 12px;border-radius:6px;font-size:12px;font-family:Arial;z-index:999;">
      <b>Legend</b><br>
      <span style="color:{COLOR_SOURCE};">●</span> Source &nbsp;
      <span style="color:{COLOR_PATH};">●</span> Main Path &nbsp;
      <span style="color:{COLOR_SINK};">●</span> Sink &nbsp;
      <span style="color:{COLOR_OTHER};">●</span> Other
    </div>
    """
    html = html.replace("<body>", f"<body style='margin:0;padding:0;'>{legend_html}")
    return html


# Keep a lightweight Plotly version for fallback / export thumbnail
def plot_main_path_network(
    G: nx.DiGraph,
    paths: list[list[str]],
    df: pd.DataFrame | None = None,
    id_col: str = "wos_id",
    weight_attr: str = "weight",
) -> go.Figure:
    """Plotly fallback — used only for static export thumbnail."""
    if not G.nodes():
        return go.Figure()

    from algorithms.main_path import make_author_year_label
    from collections import defaultdict

    year_map: dict = {}
    label_map: dict = {}
    cited_map: dict = {}

    if df is not None and not df.empty and id_col in df.columns:
        for _, row in df.iterrows():
            nid = row[id_col]
            yr = row.get("year")
            year_map[nid] = int(yr) if pd.notna(yr) else 0
            tc = row.get("times_cited")
            cited_map[nid] = int(tc) if pd.notna(tc) else 0
            label_map[nid] = make_author_year_label(row.to_dict())

    path_edges = {(paths[i][j], paths[i][j+1]) for i in range(len(paths)) for j in range(len(paths[i])-1)}
    path_nodes = {n for p in paths for n in p}
    sources = {n for n in G.nodes() if G.in_degree(n) == 0}
    sinks   = {n for n in G.nodes() if G.out_degree(n) == 0}

    # Hierarchical x from topological level, y spread within level
    topo_level: dict = {}
    try:
        if nx.is_directed_acyclic_graph(G):
            topo = list(nx.topological_sort(G))
            level: dict = {n: 0 for n in G.nodes()}
            for node in topo:
                for succ in G.successors(node):
                    level[succ] = max(level[succ], level[node] + 1)
            topo_level = level
    except Exception:
        pass

    level_nodes: dict = defaultdict(list)
    for node in G.nodes():
        yr = year_map.get(node, 0)
        lv = yr if yr > 0 else topo_level.get(node, 0)
        level_nodes[lv].append(node)

    pos: dict = {}
    for lv, nodes in level_nodes.items():
        for i, n in enumerate(nodes):
            pos[n] = (lv, (i - len(nodes) / 2) * 1.2)

    edge_traces = []
    for u, v, data in G.edges(data=True):
        x0, y0 = pos.get(u, (0, 0))
        x1, y1 = pos.get(v, (0, 0))
        is_main = (u, v) in path_edges
        edge_traces.append(go.Scatter(
            x=[x0, x1, None], y=[y0, y1, None], mode="lines",
            line=dict(width=2 if is_main else 0.5,
                      color="#C0392B" if is_main else "#D5D8DC"),
            hoverinfo="none", showlegend=False,
        ))

    groups = {"source": ([], "#27AE60", 14), "sink": ([], "#2980B9", 14),
              "path": ([], "#E74C3C", 11), "other": ([], "#BDC3C7", 7)}
    for n in G.nodes():
        if n in sources and n in path_nodes:   groups["source"][0].append(n)
        elif n in sinks and n in path_nodes:   groups["sink"][0].append(n)
        elif n in path_nodes:                  groups["path"][0].append(n)
        else:                                  groups["other"][0].append(n)

    node_traces = []
    for gname, (nodes, color, size) in groups.items():
        if not nodes: continue
        node_traces.append(go.Scatter(
            x=[pos.get(n,(0,0))[0] for n in nodes],
            y=[pos.get(n,(0,0))[1] for n in nodes],
            mode="markers+text" if gname != "other" else "markers",
            marker=dict(color=color, size=size, line=dict(width=1, color="white")),
            text=[label_map.get(n,"") for n in nodes] if gname != "other" else None,
            textposition="top center", textfont=dict(size=9),
            name=gname, showlegend=True,
            hovertext=[f"{label_map.get(n,n)}<br>Cited:{cited_map.get(n,0)}" for n in nodes],
            hoverinfo="text",
        ))

    fig = go.Figure(data=edge_traces + node_traces)
    fig.update_layout(
        xaxis_title="Publication Year / Topological Level",
        yaxis=dict(showticklabels=False, showgrid=False, zeroline=False),
        plot_bgcolor="#F5F0E8", paper_bgcolor="white",
        height=500, margin=dict(l=10, r=10, t=30, b=30),
        legend=dict(orientation="h", y=1.02),
    )
    return fig


def _layout_by_year(G: nx.DiGraph, year_map: dict) -> dict:
    from collections import defaultdict
    year_nodes: dict = defaultdict(list)
    for node in G.nodes():
        yr = year_map.get(node, 0)
        yr = int(yr) if yr and pd.notna(yr) else 0
        year_nodes[yr].append(node)
    pos: dict = {}
    for yr, nodes in year_nodes.items():
        for i, node in enumerate(nodes):
            pos[node] = (yr, i - len(nodes) / 2)
    return pos


# ---------------------------------------------------------------------------
# Top Links table chart (matching reference output)
# ---------------------------------------------------------------------------

def plot_top_links(edge_df: pd.DataFrame, top_n: int = 30) -> go.Figure:
    """Bar chart of top-N edges by weight (raw values)."""
    if edge_df.empty:
        return go.Figure()

    weight_col = [c for c in edge_df.columns if c in ("SPLC", "SPC", "SPNP")]
    if not weight_col:
        return go.Figure()
    wcol = weight_col[0]

    top = edge_df.head(top_n).copy()
    label_col = "from_to" if "from_to" in top.columns else top.columns[3]

    fig = px.bar(
        top, x=wcol, y=label_col, orientation="h",
        color=wcol, color_continuous_scale="Reds",
        title=f"Top {top_n} Links by {wcol}",
        labels={wcol: f"{wcol} (raw)", label_col: "Edge"},
    )
    fig.update_layout(yaxis=dict(autorange="reversed"), height=max(400, top_n * 18))
    return fig


# ---------------------------------------------------------------------------
# Co-author network (PyVis → HTML)
# ---------------------------------------------------------------------------

def build_coauthor_html(G: nx.Graph, top_n: int = 50) -> str:
    top_authors = sorted(
        G.nodes(), key=lambda n: G.nodes[n].get("paper_count", 0), reverse=True
    )[:top_n]
    sub = G.subgraph(top_authors).copy()

    net = Network(height="500px", width="100%", bgcolor="#FDFEFE", font_color="#2C3E50", directed=False)
    net.set_options("""{
      "physics": {"barnesHut": {"gravitationalConstant": -8000, "springLength": 120}},
      "edges": {"color": {"color": "#85C1E9"}, "smooth": false},
      "nodes": {"font": {"size": 12}}
    }""")

    max_papers = max((sub.nodes[n].get("paper_count", 1) for n in sub.nodes()), default=1)
    for node in sub.nodes():
        pc = sub.nodes[node].get("paper_count", 1)
        size = 10 + (pc / max_papers) * 30
        net.add_node(node, label=node, size=size, title=f"{node}\nPapers: {pc}",
                     color="#2ECC71")

    max_w = max((sub[u][v]["weight"] for u, v in sub.edges()), default=1)
    for u, v, data in sub.edges(data=True):
        w = data.get("weight", 1)
        net.add_edge(u, v, value=w, title=f"Co-authored: {w}")

    with tempfile.NamedTemporaryFile(suffix=".html", delete=False, mode="w") as f:
        net.save_graph(f.name)
        html = open(f.name).read()
    os.unlink(f.name)
    return html


# ---------------------------------------------------------------------------
# Overview charts
# ---------------------------------------------------------------------------

def plot_keyword_frequency(kw_df: pd.DataFrame, top_n: int = 30) -> go.Figure:
    if kw_df.empty:
        return go.Figure()
    top = kw_df.head(top_n)
    fig = px.bar(top, x="frequency", y="keyword", orientation="h",
                 color="frequency", color_continuous_scale="Blues",
                 title=f"Top {top_n} Keywords by Frequency")
    fig.update_layout(yaxis=dict(autorange="reversed"), height=500)
    return fig


def plot_publications_by_year(df: pd.DataFrame) -> go.Figure:
    if "year" not in df.columns:
        return go.Figure()
    counts = df["year"].dropna().value_counts().sort_index()
    fig = px.line(x=counts.index.astype(int), y=counts.values, markers=True,
                  title="Publications per Year",
                  labels={"x": "Year", "y": "Count"})
    fig.update_traces(line_color="#2980B9", marker_color="#E74C3C")
    fig.update_layout(height=350)
    return fig


def plot_citations_by_year(df: pd.DataFrame) -> go.Figure:
    if "year" not in df.columns or "times_cited" not in df.columns:
        return go.Figure()
    yearly = df.groupby("year")["times_cited"].sum().reset_index()
    yearly = yearly.dropna(subset=["year"])
    yearly["year"] = yearly["year"].astype(int)
    fig = px.bar(yearly, x="year", y="times_cited",
                 title="Total Citations per Year",
                 labels={"year": "Year", "times_cited": "Total Citations"},
                 color="times_cited", color_continuous_scale="Oranges")
    fig.update_layout(height=350)
    return fig
