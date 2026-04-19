# Tài liệu kỹ thuật — Thuật toán và Business Logic

> Tài liệu này mô tả các thuật toán, tham số đầu vào/đầu ra và luồng xử lý dữ liệu bên trong MainPath Analysis Tool.

## Mục lục
1. [Tổng quan kiến trúc](#1-tổng-quan-kiến-trúc)
2. [Luồng dữ liệu end-to-end](#2-luồng-dữ-liệu-end-to-end)
3. [Module Parsers](#3-module-parsers)
4. [Xây dựng Citation Network](#4-xây-dựng-citation-network)
5. [Traversal Weight Algorithms](#5-traversal-weight-algorithms)
6. [Main Path Analysis (MPA)](#6-main-path-analysis-mpa)
7. [Key-Route MPA (KRMPA)](#7-key-route-mpa-krmpa)
8. [Co-author Network](#8-co-author-network)
9. [Keyword Analysis](#9-keyword-analysis)
10. [Output — Excel Export](#10-output--excel-export)

---

## 1. Tổng quan kiến trúc

```
┌──────────────┐    ┌───────────────┐    ┌─────────────────┐
│   Parsers    │───▶│  Algorithms   │───▶│     Output      │
│              │    │               │    │                 │
│ wos_parser   │    │ traversal_    │    │ visualizer.py   │
│ citation_    │    │ weights.py    │    │ excel_export.py │
│ network      │    │ main_path.py  │    └─────────────────┘
│ relationship │    │ coauthor.py   │
│ _parser      │    │ keyword.py    │
└──────────────┘    └───────────────┘
        │                   │
        ▼                   ▼
   pd.DataFrame        nx.DiGraph
   (records)         (weighted DAG)
```

### Cấu trúc thư mục

```
mainpath_tool/
├── app.py                      # Streamlit UI — điều phối toàn bộ luồng
├── parsers/
│   ├── wos_parser.py           # Parse WOS .txt → pd.DataFrame
│   ├── citation_network.py     # DataFrame → nx.DiGraph (citation edges)
│   └── relationship_parser.py  # File relationship ngoài → edges
├── algorithms/
│   ├── traversal_weights.py    # SPC / SPLC / SPNP trên DAG
│   ├── main_path.py            # MPA (global DP + local greedy) + KRMPA
│   ├── coauthor.py             # Co-author undirected network
│   └── keyword.py              # Keyword frequency + co-occurrence
├── output/
│   ├── visualizer.py           # plotly + pyvis charts
│   └── excel_export.py         # Multi-sheet .xlsx export
└── requirements.txt
```

---

## 2. Luồng dữ liệu end-to-end

```
WOS .txt file(s)
      │
      ▼ parse_wos_file()
pd.DataFrame (717 rows × 15 cols)
      │
      ├──▶ build_citation_network() ──▶ nx.DiGraph (raw, unweighted)
      │           │
      │           ▼ compute_weights(method=SPLC)
      │    nx.DiGraph (weighted, edge attrs: weight, inflow, outflow)
      │           │
      │           ├──▶ find_main_path()         → list[wos_id]
      │           ├──▶ find_key_route_main_paths() → list[list[wos_id]]
      │           └──▶ get_edge_weight_df()     → pd.DataFrame (SPLC ranking)
      │
      ├──▶ build_coauthor_network()  → nx.Graph (co-author)
      └──▶ compute_keyword_frequency() → dict[keyword, count]
```

---

## 3. Module Parsers

### 3.1 `parse_wos_file(filepath)` — `parsers/wos_parser.py`

**Đầu vào:**
| Tham số | Kiểu | Mô tả |
|---------|------|-------|
| `filepath` | `str / Path` | Đường dẫn file WOS plain-text hoặc tab-delimited |

**Đầu ra:** `pd.DataFrame` với các cột:

| Cột | Kiểu | WOS tag | Mô tả |
|-----|------|---------|-------|
| `wos_id` | str | UT | WOS accession number (e.g. `WOS:000802155400001`) |
| `title` | str | TI | Tên bài báo |
| `authors` | list[str] | AU | Danh sách tác giả (format: `"LastName, FirstInitial"`) |
| `year` | int | PY | Năm xuất bản |
| `journal` | str | SO | Tên journal đầy đủ |
| `journal_abbr` | str | J9 | Tên journal viết tắt |
| `volume` | str | VL | Volume |
| `page_begin` | str | BP | Trang bắt đầu |
| `doi` | str | DI | DOI (không có prefix `https://doi.org/`) |
| `times_cited` | int | TC | Số lần được trích dẫn |
| `cited_references` | list[str] | CR | Danh sách raw cited reference strings |
| `abstract` | str | AB | Tóm tắt |
| `keywords_author` | list[str] | DE | Author Keywords |
| `keywords_plus` | list[str] | ID | Keywords Plus |

**Hỗ trợ multi-file:**

```python
merge_multiple_wos_files(file_list) → pd.DataFrame
```
Ghép nhiều file, loại bỏ trùng lặp theo `wos_id`.

---

### 3.2 `parse_wos_reference(ref_str)` — `parsers/citation_network.py`

Parse một chuỗi cited reference WOS thành struct:

```
Input:  "HUMMON NP, 1989, SOC NETWORKS, V11, P39, DOI 10.1016/0378-8733(89)90023-4"
Output: ParsedRef(
    first_author = "HUMMON",     # chỉ lấy last name token
    year         = "1989",
    journal      = "SOC NETWORKS",
    volume       = "11",
    page         = "39",
    doi          = "10.1016/0378-8733(89)90023-4",
    wos_accession = ""
)
```

**Lưu ý quan trọng:**
- `first_author` chỉ lấy token đầu tiên của phần author (last name), tránh lỗi trailing space với tên 5 ký tự ("WEILL P"[:6] = "WEILL " ≠ "WEILL")
- DOI được normalize: bỏ prefix `https://doi.org/`, uppercase, strip trailing punctuation

---

## 4. Xây dựng Citation Network

### `build_citation_network(df, matching_mode)` — `parsers/citation_network.py`

**Đầu vào:**

| Tham số | Kiểu | Giá trị | Mô tả |
|---------|------|---------|-------|
| `df` | `pd.DataFrame` | — | Output của `parse_wos_file` |
| `matching_mode` | `str` | `"strict"` / `"standard"` / `"aggressive"` | Chiến lược khớp cited references |

**Đầu ra:** `tuple[nx.DiGraph, pd.DataFrame, dict]`

| | Kiểu | Mô tả |
|--|------|-------|
| `G` | `nx.DiGraph` | Mạng trích dẫn: node = wos_id, edge = citation |
| `edge_df` | `pd.DataFrame` | Edge list kèm `match_type` |
| `stats` | `dict` | Thống kê matching |

**Chiều cạnh (Edge Direction):**
```
cited_paper ──▶ citing_paper
 (older)          (newer)

Ví dụ: VaiaAD2022 ──▶ HanischGFO2023
       (2022, được trích dẫn bởi bài 2023)
```

> **Quan trọng:** Chiều cạnh là **cited → citing** (cũ → mới), đồng nhất với MainPath 492. Đây không phải chiều ngược lại.

**Matching Strategies (theo thứ tự ưu tiên):**

| Level | Phương pháp | Mode |
|-------|------------|------|
| 1 | DOI exact match (after normalization) | strict / standard / aggressive |
| 2 | WOS accession number match | strict / standard / aggressive |
| 3 | Author[:6] + Year + Volume + Page | standard / aggressive |
| 4 | Author[:6] + Year + Journal[:6] | standard / aggressive |
| 5 | Author[:6] + Year (chỉ khi unique match) | aggressive |

**Match stats output:**

```python
{
    "total_refs": 47187,       # tổng cited references
    "matched_doi": 1145,       # khớp bằng DOI
    "matched_wosid": 0,        # khớp bằng WOS ID
    "matched_author_year": 350, # khớp bằng author+year
    "unmatched": 45692,        # không khớp
    "match_rate_pct": 3.2      # tỷ lệ khớp (%)
}
```

---

## 5. Traversal Weight Algorithms

### `compute_weights(G, method, decay_factor)` — `algorithms/traversal_weights.py`

**Đầu vào:**

| Tham số | Kiểu | Mặc định | Mô tả |
|---------|------|---------|-------|
| `G` | `nx.DiGraph` | — | Citation network (raw) |
| `method` | `WeightMethod` | `SPLC` | Phương pháp tính weight |
| `decay_factor` | `float` | `0.2` | (Không dùng trong công thức hiện tại) |

**Đầu ra:** `nx.DiGraph` — bản copy của G với edge attributes:

| Attribute | Kiểu | Mô tả |
|-----------|------|-------|
| `weight` | float | Traversal weight của cạnh (u→v) |
| `method` | str | Tên method đã dùng |
| `inflow` | int | fwd_count[u] — số paths từ sources đến u |
| `outflow` | int | bwd_count[v] — số paths từ v đến sinks |

---

### 5.1 SPLC — Search Path Link Count

**Tham chiếu:** Hummon & Doreian (1989), Liu & Lu (2012)

**Tiền xử lý:** Loại bỏ self-loops và cycles (back-edge pruning) để tạo DAG trước khi tính.

**Thuật toán:**

```python
# Bước 1: Forward pass (topological order)
fwd_count[source] = 1  for all sources (in_degree == 0)
fwd_count[v] += fwd_count[u]  for each edge u→v

# Bước 2: Backward pass (reverse topological order)  
bwd_count[sink] = 1  for all sinks (out_degree == 0)
bwd_count[u] += bwd_count[v]  for each edge u→v

# Bước 3: Edge weight
SPLC(u→v) = fwd_count[u] × bwd_count[v]
```

**Ý nghĩa:**
- `fwd_count[u]` = số paths từ tất cả sources đến node u
- `bwd_count[v]` = số paths từ node v đến tất cả sinks
- `SPLC(u→v)` = số paths nguồn-đích đi qua cạnh (u→v)

**Ví dụ thực tế (dataset ITG):**
```
VaiaAD2022 → HanischGFO2023:
  fwd[VaiaAD2022]       = 1092   (1092 paths từ các papers cũ đến VaiaAD2022)
  bwd[HanischGFO2023]   = 12     (12 paths từ HanischGFO2023 đến papers mới nhất)
  SPLC                  = 1092 × 12 = 13104

Reference tool (MainPath 492):
  fwd[VaiaAD2022]       = 1989   (nhiều hơn do match rate cao hơn)
  SPLC                  = 1989 × 12 = 23868
```

---

### 5.2 SPC — Search Path Count

Giống SPLC về công thức (fwd × bwd), khác nhau ở cách normalization trong reference tool. Trong implementation hiện tại, SPC = SPLC.

---

### 5.3 SPNP — Search Path Node Pair

**Công thức:**
```python
# reachable_from[u] = set of source nodes that can reach u
# reachable_sinks[v] = set of sink nodes reachable from v

SPNP(u→v) = |reachable_from[u]| × |reachable_sinks[v]|
```

Đo số cặp (source, sink) mà đường đi của chúng đi qua cạnh (u→v). Khác SPC ở chỗ đếm số cặp node thay vì số paths (loại bỏ ảnh hưởng của multiple paths giữa cùng cặp source-sink).

---

### `get_edge_weight_df(G, top_n)` — Output format

**Đầu ra:** `pd.DataFrame` với cột:

| Cột | Mô tả |
|-----|-------|
| `count` | Rank (1 = edge có weight cao nhất) |
| `SPLC` | Traversal weight |
| `relevancy` | Luôn = 1.0 (tương thích MainPath 492 format) |
| `from_to` | `"SourceLabel => TargetLabel"` |
| `inflow_paths` | fwd_count[source] |
| `outflow_paths` | bwd_count[target] |

---

## 6. Main Path Analysis (MPA)

### `find_main_path(G, strategy, mode, weight_attr, tie_tolerance)` — `algorithms/main_path.py`

**Đầu vào:**

| Tham số | Kiểu | Mặc định | Mô tả |
|---------|------|---------|-------|
| `G` | `nx.DiGraph` | — | Weighted citation network |
| `strategy` | `str` | `"global"` | `"global"` hoặc `"local"` |
| `mode` | `str` | `"standard"` | `"standard"`, `"forward"`, `"backward"` |
| `weight_attr` | `str` | `"weight"` | Tên edge attribute dùng làm weight |
| `tie_tolerance` | `float` | `0.0` | Ngưỡng chấp nhận tie (0 = chỉ exact ties) |

**Đầu ra:** `list[str]` — danh sách wos_id theo thứ tự từ source đến sink

---

### 6.1 Global Search (DP) — khuyến nghị

```python
# Khởi tạo
dp[source] = (0.0, None)  # (total_weight, previous_node)
dp[node]   = (-inf, None)  # cho tất cả nodes khác

# Forward DP theo topological order
for node in topological_sort(G):
    for succ in successors(node):
        candidate = dp[node].weight + edge_weight(node, succ)
        if candidate > dp[succ].weight:
            dp[succ] = (candidate, node)

# Traceback từ best sink
best_sink = argmax(dp[sink].weight for sink in sinks)
path = traceback(dp, best_sink)
```

**Đảm bảo tìm được path tối ưu toàn cục** (tổng weight lớn nhất).

---

### 6.2 Local Search (Greedy)

**Forward:** Bắt đầu từ tất cả sources, mỗi bước chọn cạnh outgoing có weight cao nhất. Trả về path có tổng weight lớn nhất trong tất cả sources.

**Backward:** Bắt đầu từ tất cả sinks, mỗi bước chọn cạnh incoming có weight cao nhất. Kết quả tương đương forward nhưng đôi khi khác 1–2 nodes ở biên.

---

### `make_author_year_label(row)` — Tạo nhãn hiển thị

Tạo nhãn dạng **AuthorYear** khớp với MainPath 492:

```
Format: FirstAuthorLastName + CoAuthorInitials + Year

Ví dụ:
  Authors: ["Bradley, R", "Brown, P", "Thatcher, T", "Parker, M"]
  → Label: "BradleyBPT2012"

  Authors: ["Hummon, N P", "Doreian, P"]
  → Label: "HummonD1989"
```

- Xử lý accent: `Héroux` → `Heroux` (via `unicodedata.normalize NFKD`)
- Chỉ lấy first letter của last name mỗi co-author

---

## 7. Key-Route MPA (KRMPA)

### `find_key_route_main_paths(G, n_significant_routes, weight_attr, tie_tolerance)` — `algorithms/main_path.py`

**Đầu vào:**

| Tham số | Kiểu | Mặc định | Mô tả |
|---------|------|---------|-------|
| `G` | `nx.DiGraph` | — | Weighted citation network |
| `n_significant_routes` | `int` | `10` | Số key route edges cần chọn (khuyến nghị: 20) |
| `weight_attr` | `str` | `"weight"` | Edge attribute làm weight |
| `tie_tolerance` | `float` | `0.0` | Ngưỡng tie |

**Đầu ra:** `list[list[str]]` — danh sách các paths, mỗi path là list[wos_id]

---

### Thuật toán KRMPA

```
Bước 1: Chọn top-N edges (sorted by weight descending)
        → key_edges = [(u1,v1), (u2,v2), ..., (uN,vN)]

Bước 2: Với mỗi key edge (u → v):
  a. back = _trace_backward(G, u)
     Từ u, trace ngược về source theo highest-weight incoming edge
     → back = [source, ..., prev_of_u]

  b. fwd  = _trace_forward(G, v)  
     Từ v, trace xuôi về sink theo highest-weight outgoing edge
     → fwd = [next_of_v, ..., sink]

  c. full_path = back + [u, v] + fwd

  d. Mở rộng tied SOURCE: nếu source có tied predecessors cùng vào
     next_hop với weight tương đương → thêm path với mỗi alt_source

  e. Mở rộng tied SINK: nếu v có nhiều tied successors (cùng SPLC)
     → thêm path riêng cho mỗi alt_first_successor

Bước 3: Dedup paths, trả về danh sách
```

**Ví dụ tied-sink expansion:**
```
MengWL2024 có 3 successors cùng SPLC = 1095:
  → ZhangZ2025 (1095)
  → ShaoL2024  (1095)  
  → LiuF2025   (1095)

Thay vì chỉ pick ZhangZ2025 (first), KRMPA generate 3 paths:
  Path A: ... → MengWL2024 → ZhangZ2025 → DavidWBA2025
  Path B: ... → MengWL2024 → ShaoL2024
  Path C: ... → MengWL2024 → LiuF2025
```

**Benchmark kết quả (dataset ITG, 717 records):**

| Mode | N | Standard papers found |
|------|---|----------------------|
| Strict | 15 | 19/23 |
| Strict | 20 | 19/23 |
| Standard | 20 | **23/23** ✅ |
| Standard | 25 | 23/23 ✅ |

---

## 8. Co-author Network

### `build_coauthor_network(df)` — `algorithms/coauthor.py`

**Đầu vào:** `pd.DataFrame`  
**Đầu ra:** `nx.Graph` — undirected, weighted

Edge weight = số bài báo cùng viết giữa hai tác giả.

```python
for each paper with authors [A, B, C]:
    add_edge(A, B, weight += 1)
    add_edge(A, C, weight += 1)
    add_edge(B, C, weight += 1)
```

Node attributes: `paper_count`, `degree_centrality`

### `get_coauthor_stats(G, df)` — Đầu ra:

`pd.DataFrame` với cột: `author`, `paper_count`, `collaborator_count`, `total_collaborations`, `degree_centrality`

---

## 9. Keyword Analysis

### `compute_keyword_frequency(df, source)` — `algorithms/keyword.py`

**Tham số `source`:** `"author"` (trường DE) hoặc `"plus"` (trường ID) hoặc `"both"`

**Đầu ra:** `dict[keyword: str, count: int]`

### `build_keyword_cooccurrence_network(df, min_cooccurrence)` — Đầu ra:

`nx.Graph` — undirected, edge weight = số bài cùng có 2 keywords đó.

### `compute_jaccard_similarity(df)` — Đầu ra:

`pd.DataFrame` — ma trận Jaccard similarity giữa các bài báo dựa trên keywords chung.

```
Jaccard(A, B) = |keywords_A ∩ keywords_B| / |keywords_A ∪ keywords_B|
```

---

## 10. Output — Excel Export

### `export_to_excel(...)` — `output/excel_export.py`

**Đầu vào:**

| Tham số | Mô tả |
|---------|-------|
| `df` | DataFrame records |
| `G` | Weighted DiGraph |
| `mpa_path` | list[wos_id] — MPA path |
| `krmpa_paths` | list[list[wos_id]] — KRMPA paths |
| `coauthor_G` | Co-author Graph |
| `keyword_freq` | Keyword frequency dict |

**Đầu ra:** `bytes` — nội dung file `.xlsx` (trả về để Streamlit download)

**Sheets:**

| Sheet | Nguồn dữ liệu | Cột chính |
|-------|--------------|-----------|
| Records | `df` | wos_id, title, authors, year, journal, doi, times_cited |
| Citation Links | `edge_df` | source, target, match_type |
| Main Path | `mpa_path` + `df` | position, label, title, year, edge_weight_to_next |
| KRMPA Paths | `krmpa_paths` | path_id, position, label, title, year |
| Top SPLC Links | `get_edge_weight_df(G)` | count, SPLC, relevancy, from_to, inflow, outflow |
| Co-author Stats | `get_coauthor_stats()` | author, paper_count, collaborator_count |
| Co-author Edges | `get_coauthor_edges_df()` | author_1, author_2, papers_together |
| Keywords | `keyword_freq` | keyword, frequency |

---

## Tham chiếu học thuật

- **Hummon, N. P., & Doreian, P. (1989)**. Connectivity in a citation network: The development of DNA theory. *Social Networks*, 11(1), 39–63.
- **Liu, J. S., & Lu, L. Y. Y. (2012)**. An integrated approach for main path analysis: Development of the Hirsch index as an example. *Journal of the American Society for Information Science and Technology*, 63(3), 528–542.
- **Batagelj, V. (2003)**. Efficient algorithms for citation network analysis. *arXiv preprint cs/0309023*.
