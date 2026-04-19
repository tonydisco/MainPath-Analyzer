"""
MainPath Analysis Tool — Streamlit App
Implements: SPC/SPLC/SPNP, Local/Global search, Key-route, Multi-file input
"""
from __future__ import annotations
import tempfile, os
import streamlit as st
import networkx as nx
import pandas as pd
import streamlit.components.v1 as components

from parsers import (
    parse_wos_file, build_citation_network,
    parse_relationship_file, merge_multiple_wos_files,
)
from algorithms import (
    compute_weights, WeightMethod, get_edge_weight_df,
    find_main_path, find_multiple_main_paths, find_key_route_main_paths, find_main_paths_by_year,
    path_to_df, multiple_paths_to_df,
    build_coauthor_network, get_coauthor_stats, get_coauthor_edges_df,
    compute_keyword_frequency, build_keyword_cooccurrence_network,
    get_keyword_stats,
)
from algorithms.main_path import filter_graph_by_year
from output import (
    export_to_excel,
    build_citation_network_html, plot_main_path_network, plot_top_links,
    build_coauthor_html, plot_keyword_frequency,
    plot_publications_by_year, plot_citations_by_year,
)

st.set_page_config(
    page_title="MainPath Analysis Tool",
    page_icon="🔬",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# Session state init
# ---------------------------------------------------------------------------
for key in ["df", "G_raw", "G_weighted", "edge_df", "match_stats"]:
    if key not in st.session_state:
        st.session_state[key] = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def save_uploads(files) -> list[str]:
    """Save uploaded UploadedFile objects to temp files, return paths."""
    paths = []
    for f in files:
        suffix = "." + f.name.split(".")[-1]
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
        tmp.write(f.read())
        tmp.close()
        paths.append(tmp.name)
    return paths


# ---------------------------------------------------------------------------
# SIDEBAR
# ---------------------------------------------------------------------------
with st.sidebar:
    st.title("🔬 MainPath Tool")
    st.caption("Web of Science Citation Analysis")
    st.divider()

    # ── INPUT ──
    st.subheader("📂 Input Data")

    input_mode = st.radio(
        "Input mode",
        ["Multiple WOS files", "WOS file + Relationship List"],
        help="Choose how to provide data",
    )

    if input_mode == "Multiple WOS files":
        wos_files = st.file_uploader(
            "Upload WOS export files (one or more)",
            type=["txt", "csv", "tsv"],
            accept_multiple_files=True,
            help="Export from WOS with Full Record + Cited References",
        )
        rel_files = None
    else:
        wos_files = st.file_uploader(
            "Full Record Data (WOS export)",
            type=["txt", "csv", "tsv"],
            accept_multiple_files=True,
        )
        rel_files = st.file_uploader(
            "Relationship List (citation pairs)",
            type=["txt", "csv", "tsv"],
            accept_multiple_files=False,
            help="Tab/space separated: source_id [tab] target_id",
        )

    separator = st.selectbox("Separator", ["Tab or Space", "Tab", "Space"])
    sep_map = {"Tab or Space": "auto", "Tab": "tab", "Space": "space"}

    matching_mode = st.selectbox(
        "Citation Matching Mode",
        ["Strict (DOI only)", "Standard (DOI + Author+Year)", "Aggressive (all methods)"],
        index=1,
        help=(
            "Standard (recommended): DOI + Author+Year+Journal — best coverage\n"
            "Strict: chỉ DOI/WOS accession\n"
            "Aggressive: thêm unique Author+Year fallback"
        ),
    )
    matching_mode_key = {"Strict (DOI only)": "strict",
                         "Standard (DOI + Author+Year)": "standard",
                         "Aggressive (all methods)": "aggressive"}[matching_mode]

    load_btn = st.button("📥 Load Data", type="secondary", use_container_width=True)

    if load_btn and wos_files:
        with st.spinner("Parsing WOS files..."):
            tmp_paths = save_uploads(wos_files)
            if len(tmp_paths) == 1:
                df = parse_wos_file(tmp_paths[0])
            else:
                df = merge_multiple_wos_files(tmp_paths)
            for p in tmp_paths:
                os.unlink(p)
            st.session_state.df = df

        if rel_files is not None:
            with st.spinner("Parsing Relationship List..."):
                tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".txt")
                tmp.write(rel_files.read())
                tmp.close()
                rel_df = parse_relationship_file(tmp.name, separator=sep_map[separator])
                os.unlink(tmp.name)
                G_raw = nx.from_pandas_edgelist(
                    rel_df, source="source", target="target",
                    edge_attr="weight", create_using=nx.DiGraph(),
                )
                for wid in df["wos_id"].dropna():
                    if wid not in G_raw:
                        G_raw.add_node(wid)
                st.session_state.G_raw = G_raw
                st.session_state.match_stats = {
                    "total_refs": len(rel_df),
                    "matched_doi": len(rel_df),
                    "matched_wosid": 0,
                    "matched_author_year": 0,
                    "match_rate_pct": 100.0,
                    "source": "Relationship List",
                }
        else:
            with st.spinner("Building citation network from references..."):
                G_raw, _, match_stats = build_citation_network(df, matching_mode=matching_mode_key)
                st.session_state.G_raw = G_raw
                st.session_state.match_stats = match_stats

        st.success(
            f"Loaded **{len(df)}** records | "
            f"**{st.session_state.G_raw.number_of_edges()}** citation edges"
        )

    st.divider()

    # ── ANALYSIS SETTINGS ──
    st.subheader("⚙️ Analysis Settings")

    weight_method = st.selectbox(
        "Search Path Count Method",
        options=[m.value for m in WeightMethod],
        index=1,
        help="SPC: path count | SPLC: path-length weighted | SPNP: node-pair coverage",
    )

    decay_factor = st.number_input(
        "Decay Factor", min_value=0.0, max_value=1.0, value=0.2, step=0.05,
        help="Applied in weight decay computation (default 0.2)",
    )

    st.markdown("**TYPE OF MAIN PATH SEARCH**")

    analysis_type = st.radio(
        "Analysis Type",
        ["MPA — Main Path Analysis", "KRMPA — Key-route Main Path Analysis"],
        help=(
            "MPA: tìm một đường đi chính (xương sống của lĩnh vực)\n"
            "KRMPA: tìm top-N key route edges rồi mở rộng thành nhiều paths song song"
        ),
    )
    use_krmpa = "KRMPA" in analysis_type

    search_strategy = st.radio("Search Strategy", ["Global Search", "Local Search"])
    strategy_key = "global" if "Global" in search_strategy else "local"

    if strategy_key == "global":
        global_mode = st.radio("Global Mode", ["Standard", "Key-route"], horizontal=True,
                               help="Standard: DP tối ưu toàn cục | Key-route: dùng KRMPA")
        mode_key = "key-route" if global_mode == "Key-route" else "standard"
    else:
        local_mode = st.radio("Local Mode", ["Forward", "Backward"], horizontal=True)
        mode_key = local_mode.lower()

    n_significant_routes = st.select_slider(
        "Number of Significant Routes",
        options=[5, 10, 15, 20, 25, 30],
        value=20,
        help="Số key route edges — khuyến nghị 20 để tìm đủ branching paths",
    )

    tie_tolerance = st.number_input(
        "Tie Tolerance (fraction of SPx tie value)",
        min_value=0.0, max_value=1.0, value=0.0, step=0.01,
        help="Chấp nhận edges trong khoảng tolerance của max weight",
    )

    n_paths = st.slider(
        "Number of Paths (MPA only)",
        1, 10, 1,
        help="Chỉ dùng khi MPA — số paths tìm bằng cách lặp",
    )

    st.markdown("**Year Filter**")
    col_y1, col_y2 = st.columns(2)
    year_from = col_y1.number_input("From", value=1800, step=1)
    year_to = col_y2.number_input("To", value=2027, step=1)

    node_scope = st.selectbox(
        "Node Scope",
        ["Nodes in Full Record Data", "All nodes in network"],
    )

    run_btn = st.button("▶ Execute", type="primary", use_container_width=True)

    if run_btn and st.session_state.G_raw is not None:
        df_run = st.session_state.df
        G_input = st.session_state.G_raw

        # Apply year filter
        if df_run is not None:
            G_input = filter_graph_by_year(
                G_input, df_run,
                year_from=int(year_from), year_to=int(year_to),
            )

        # Apply node scope
        if node_scope == "Nodes in Full Record Data" and df_run is not None:
            known = set(df_run["wos_id"].dropna())
            remove = [n for n in G_input.nodes() if n not in known]
            G_input = G_input.copy()
            G_input.remove_nodes_from(remove)

        with st.spinner("Computing traversal weights..."):
            G_w = compute_weights(
                G_input,
                method=WeightMethod(weight_method),
                decay_factor=float(decay_factor),
            )
            st.session_state.G_weighted = G_w
            st.session_state.edge_df = get_edge_weight_df(G_w, top_n=5000)
        st.success("Analysis complete!")


# ---------------------------------------------------------------------------
# MAIN CONTENT
# ---------------------------------------------------------------------------
df = st.session_state.df
G = st.session_state.G_weighted
edge_df = st.session_state.edge_df

if df is None:
    st.title("MainPath Analysis Tool")
    st.info("👈 Upload Web of Science export files from the sidebar to get started.")
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("""
**Supported input:**
- Multiple WOS export files (`.txt`, `.tsv`, `.csv`)
- WOS file + separate Relationship List
- Folder of WOS files

**Analyses:**
- 🛤️ Main Path (SPC / SPLC / SPNP)
- 🔀 Multiple Main Paths
- 📅 Main Path by Year
- 👥 Co-author Network
- 🔑 Keyword Analysis
        """)
    with col2:
        st.markdown("""
**Search types:**
- Global Search: Standard / Key-route
- Local Search: Forward / Backward / Key-route

**Output:**
- Interactive citation network (colored nodes)
- Top 5000 Links table (raw weights)
- Excel report with all sheets
        """)
    st.stop()

tab_overview, tab_mainpath, tab_krmpa, tab_links, tab_multi, tab_year, tab_coauthor, tab_keyword, tab_export = st.tabs([
    "📊 Overview",
    "🛤️ MPA",
    "🔀 KRMPA",
    "🔗 Top Links",
    "📋 Multiple MPA",
    "📅 By Year",
    "👥 Co-authors",
    "🔑 Keywords",
    "📥 Export",
])


# ── OVERVIEW ──
with tab_overview:
    st.header("Dataset Overview")
    g_raw = st.session_state.G_raw
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Records", len(df))
    c2.metric("Citation Edges", g_raw.number_of_edges() if g_raw else 0)
    c3.metric("Year Range",
              f"{int(df['year'].dropna().min())} – {int(df['year'].dropna().max())}"
              if "year" in df.columns and df["year"].notna().any() else "N/A")
    c4.metric("Unique Journals", df["journal"].nunique() if "journal" in df.columns else 0)

    if st.session_state.match_stats:
        ms = st.session_state.match_stats
        with st.expander("📎 Citation Matching Details"):
            mc1, mc2, mc3, mc4, mc5 = st.columns(5)
            mc1.metric("Total References", ms.get("total_refs", 0))
            mc2.metric("Matched (DOI)", ms.get("matched_doi", 0))
            mc3.metric("Matched (WOS ID)", ms.get("matched_wosid", 0))
            mc4.metric("Matched (Author+Year)", ms.get("matched_author_year", 0))
            mc5.metric("Match Rate", f"{ms.get('match_rate_pct', 0)}%")

    col1, col2 = st.columns(2)
    with col1:
        st.plotly_chart(plot_publications_by_year(df), use_container_width=True, key="pub_by_year")
    with col2:
        st.plotly_chart(plot_citations_by_year(df), use_container_width=True, key="cite_by_year")

    display_cols = [c for c in ["wos_id", "title", "authors", "year", "journal", "times_cited", "doi"] if c in df.columns]
    show_df = df[display_cols].copy()
    if "authors" in show_df.columns:
        show_df["authors"] = show_df["authors"].apply(
            lambda x: "; ".join(x[:3]) + ("..." if len(x) > 3 else "") if isinstance(x, list) else x
        )
    st.subheader("Records")
    st.dataframe(show_df, use_container_width=True, height=300)


# ── MPA ──
with tab_mainpath:
    st.header("Main Path Analysis (MPA)")
    st.caption("Tìm một đường đi chính — xương sống tri thức của lĩnh vực nghiên cứu")
    if G is None:
        st.warning("Click **▶ Execute** in the sidebar to run analysis.")
    else:
        path = find_main_path(
            G, strategy=strategy_key, mode=mode_key,
            weight_attr="weight", tie_tolerance=float(tie_tolerance),
            n_significant_routes=n_significant_routes,
        )
        if not path:
            st.error("No main path found. Check that citation references match records in your dataset.")
        else:
            st.success(f"Main path: **{len(path)} nodes** | **{len(path)-1} edges** | Method: **{weight_method}** | Strategy: **{search_strategy} — {mode_key}**")

            components.html(build_citation_network_html(G, [path], df), height=620, scrolling=False)

            st.subheader("Main Path Records")
            path_df = path_to_df(path, df, G)
            st.dataframe(path_df, use_container_width=True)

            with st.expander("📖 How to interpret"):
                st.markdown(f"""
**Method: {weight_method}** — {"Counts raw number of search paths through each edge." if weight_method=="SPC" else "Raw path count weighted by path length (larger dataset → larger raw values)." if weight_method=="SPLC" else "Counts source-sink node pairs connected via each edge."}

- **label**: AuthorYear format (e.g., HummonNP1989)
- **edge_weight_to_next**: raw {weight_method} value of the edge to the next record
- **inflow_paths**: number of paths entering the source node
- **outflow_paths**: number of paths leaving the target node
- Records on main path = **intellectual backbone** of the research field
                """)


# ── KRMPA ──
with tab_krmpa:
    st.header("Key-route Main Path Analysis (KRMPA)")
    st.markdown("""
> **KRMPA** tìm top-N edges có traversal weight cao nhất (key routes),
> rồi mở rộng mỗi edge thành một path hoàn chỉnh bằng cách trace ngược về source và xuôi về sink.
> Kết quả thể hiện **nhiều nhánh phát triển song song** của lĩnh vực.
    """)

    if G is None:
        st.warning("Click **▶ Execute** in the sidebar first.")
    else:
        kr_paths = find_key_route_main_paths(
            G,
            n_significant_routes=n_significant_routes,
            weight_attr="weight",
            strategy=strategy_key,
            tie_tolerance=float(tie_tolerance),
        )

        if not kr_paths:
            st.error("No key route paths found.")
        else:
            # Deduplicate identical paths
            unique_paths = []
            seen = set()
            for p in kr_paths:
                key = tuple(p)
                if key not in seen:
                    seen.add(key)
                    unique_paths.append(p)

            all_nodes = {n for p in unique_paths for n in p}
            all_edges = {(p[i], p[i+1]) for p in unique_paths for i in range(len(p)-1)}

            c1, c2, c3 = st.columns(3)
            c1.metric("Key Routes (N)", n_significant_routes)
            c2.metric("Unique Paths", len(unique_paths))
            c3.metric("Nodes on paths", len(all_nodes))

            st.subheader("Network Visualization")
            # Show subgraph of path nodes only — includes ALL edges between them (not just path edges)
            G_krmpa = G.subgraph(all_nodes).copy()
            components.html(
                build_citation_network_html(G_krmpa, unique_paths, df),
                height=650, scrolling=False,
            )

            st.subheader("Path Details")
            kr_df = multiple_paths_to_df(unique_paths, df, G)
            for i, p in enumerate(unique_paths):
                with st.expander(f"Key Route {i+1} — {len(p)} nodes, {len(p)-1} edges"):
                    pdata = kr_df[kr_df["path_index"] == i + 1]
                    st.dataframe(pdata.drop(columns=["path_index"]), use_container_width=True)

            with st.expander("📖 MPA vs KRMPA — Sự khác biệt"):
                st.markdown(f"""
| | MPA | KRMPA |
|---|---|---|
| **Mục tiêu** | Tìm **một** đường xương sống chính | Tìm **nhiều nhánh** quan trọng song song |
| **Cách tìm** | DP/greedy trên toàn bộ mạng | Từ top-{n_significant_routes} edges → mở rộng thành paths |
| **Kết quả** | 1 path đơn giản, dễ đọc | {len(unique_paths)} paths, phong phú hơn |
| **Khi dùng** | Muốn biết dòng phát triển chính | Muốn thấy cấu trúc đầy đủ của lĩnh vực |
| **Paths chia sẻ edges** | Không (paths độc lập) | Có (nhiều paths qua cùng key route) |
                """)


# ── TOP LINKS ──
with tab_links:
    st.header(f"Top 5000 Links")
    if edge_df is None or edge_df.empty:
        st.warning("Click **▶ Execute** in the sidebar first.")
    else:
        weight_col = [c for c in edge_df.columns if c in ("SPLC", "SPC", "SPNP")]
        wcol = weight_col[0] if weight_col else edge_df.columns[1]

        col1, col2 = st.columns([1, 3])
        with col1:
            top_n_show = st.number_input("Show top N links", min_value=10, max_value=5000, value=30, step=10)
        with col2:
            st.plotly_chart(plot_top_links(edge_df, top_n=int(top_n_show)), use_container_width=True, key="top_links_chart")

        st.subheader(f"Top {top_n_show} Links Table")
        st.dataframe(edge_df.head(int(top_n_show)), use_container_width=True)

        st.caption(f"Columns: count | {wcol} (raw) | relevancy | from → to | inflow paths | outflow paths")


# ── MULTIPLE PATHS ──
with tab_multi:
    st.header("Multiple Main Paths")
    if G is None:
        st.warning("Click **▶ Execute** in the sidebar first.")
    else:
        paths = find_multiple_main_paths(
            G, n_paths=n_paths, strategy=strategy_key, mode=mode_key,
            weight_attr="weight", tie_tolerance=float(tie_tolerance),
            n_significant_routes=n_significant_routes,
        )
        if not paths:
            st.error("No paths found.")
        else:
            st.success(f"Found **{len(paths)}** main path(s) | Number of paths in search: **{n_paths}**")
            components.html(build_citation_network_html(G, paths, df), height=620, scrolling=False)

            multi_df = multiple_paths_to_df(paths, df, G)
            for i, path in enumerate(paths):
                with st.expander(f"Path {i+1} — {len(path)} nodes, {len(path)-1} edges"):
                    pdata = multi_df[multi_df["path_index"] == i + 1]
                    st.dataframe(pdata.drop(columns=["path_index"]), use_container_width=True)


# ── BY YEAR ──
with tab_year:
    st.header("Main Path by Year")
    if G is None:
        st.warning("Click **▶ Execute** in the sidebar first.")
    else:
        year_paths = find_main_paths_by_year(
            G, df, strategy=strategy_key, mode=mode_key,
            weight_attr="weight",
            year_from=int(year_from), year_to=int(year_to),
        )
        if not year_paths:
            st.warning("Not enough data to partition by year. Check year filter range.")
        else:
            st.success(f"Paths found for **{len(year_paths)}** years")
            year_select = st.selectbox("Select Year", sorted(year_paths.keys()))
            if year_select:
                ypath = year_paths[year_select]
                components.html(build_citation_network_html(G, [ypath], df), height=500, scrolling=False)
                st.dataframe(path_to_df(ypath, df, G), use_container_width=True)

            st.subheader("Summary by Year")
            summary_rows = []
            for yr, p in sorted(year_paths.items()):
                pdf = path_to_df(p, df, G)
                labels = pdf["label"].tolist() if "label" in pdf.columns else p
                summary_rows.append({
                    "year": yr,
                    "path_length (nodes)": len(p),
                    "path_length (edges)": len(p) - 1,
                    "key nodes": " → ".join(str(l) for l in labels[:4]) + ("..." if len(labels) > 4 else ""),
                })
            st.dataframe(pd.DataFrame(summary_rows), use_container_width=True)


# ── CO-AUTHORS ──
with tab_coauthor:
    st.header("Co-author Network")
    with st.spinner("Building co-author network..."):
        G_ca = build_coauthor_network(df)

    c1, c2, c3 = st.columns(3)
    c1.metric("Authors", G_ca.number_of_nodes())
    c2.metric("Co-author Links", G_ca.number_of_edges())
    c3.metric("Network Density", f"{nx.density(G_ca):.4f}" if G_ca.number_of_nodes() > 1 else "N/A")

    top_n_ca = st.slider("Show top N authors in network", 10, 100, 50)
    html = build_coauthor_html(G_ca, top_n=top_n_ca)
    components.html(html, height=520)

    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Author Statistics")
        st.dataframe(get_coauthor_stats(G_ca), use_container_width=True)
    with col2:
        st.subheader("Co-authorship Edges")
        st.dataframe(get_coauthor_edges_df(G_ca), use_container_width=True)


# ── KEYWORDS ──
with tab_keyword:
    st.header("Keyword Analysis")
    col1, col2 = st.columns([1, 3])
    with col1:
        use_author_kw = st.checkbox("Author Keywords (DE)", value=True)
        use_plus_kw = st.checkbox("Keywords Plus (ID)", value=True)
        min_freq = st.number_input("Min keyword frequency", min_value=1, value=2)

    kw_df = compute_keyword_frequency(df, use_author_kw, use_plus_kw)
    with col2:
        st.plotly_chart(plot_keyword_frequency(kw_df), use_container_width=True, key="keyword_freq_chart")

    G_kw = build_keyword_cooccurrence_network(
        df, min_frequency=min_freq,
        use_author_keywords=use_author_kw, use_keywords_plus=use_plus_kw,
    )
    st.subheader("Keyword Statistics")
    st.dataframe(get_keyword_stats(G_kw), use_container_width=True)


# ── EXPORT ──
with tab_export:
    st.header("Export Results")

    export_sheets = {}
    show_df2 = df[[c for c in ["wos_id", "title", "year", "journal", "times_cited", "doi"] if c in df.columns]].copy()
    export_sheets["Records"] = show_df2

    if G is not None:
        path = find_main_path(G, strategy=strategy_key, mode=mode_key, weight_attr="weight")
        if path:
            export_sheets["Main Path"] = path_to_df(path, df, G)

        paths = find_multiple_main_paths(G, n_paths=n_paths, strategy=strategy_key, mode=mode_key, weight_attr="weight")
        if paths:
            export_sheets["Multiple Paths"] = multiple_paths_to_df(paths, df, G)

        if edge_df is not None and not edge_df.empty:
            export_sheets["Top Links"] = edge_df

        year_paths = find_main_paths_by_year(G, df, strategy=strategy_key, mode=mode_key,
                                             year_from=int(year_from), year_to=int(year_to))
        if year_paths:
            year_rows = []
            for yr, p in sorted(year_paths.items()):
                ypdf = path_to_df(p, df, G)
                ypdf.insert(0, "partition_year", yr)
                year_rows.append(ypdf)
            if year_rows:
                export_sheets["Paths by Year"] = pd.concat(year_rows, ignore_index=True)

    G_ca2 = build_coauthor_network(df)
    export_sheets["Coauthor Stats"] = get_coauthor_stats(G_ca2)
    export_sheets["Coauthor Edges"] = get_coauthor_edges_df(G_ca2)
    export_sheets["Keywords"] = compute_keyword_frequency(df)

    st.write("**Sheets in Excel report:**")
    for name, sdf in export_sheets.items():
        st.write(f"- **{name}**: {len(sdf) if sdf is not None else 0} rows")

    xlsx_bytes = export_to_excel(export_sheets)
    st.download_button(
        label="📥 Download Excel Report",
        data=xlsx_bytes,
        file_name="mainpath_analysis.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        type="primary",
        use_container_width=True,
    )
