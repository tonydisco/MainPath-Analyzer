# Hướng dẫn sử dụng — MainPath Analysis Tool

> **Thay thế MainPath 492** — cross-platform, mã nguồn mở, không cần license.  
> Repo: [github.com/tonydisco/MainPath-Analyzer](https://github.com/tonydisco/MainPath-Analyzer)

## Mục lục
1. [Giới thiệu](#1-giới-thiệu)
2. [Cài đặt](#2-cài-đặt)
3. [Khởi động tool](#3-khởi-động-tool)
4. [Chuẩn bị dữ liệu từ Web of Science](#4-chuẩn-bị-dữ-liệu-từ-web-of-science)
5. [Luồng sử dụng cơ bản](#5-luồng-sử-dụng-cơ-bản)
6. [Giải thích từng tab](#6-giải-thích-từng-tab)
7. [Cài đặt phân tích](#7-cài-đặt-phân-tích)
8. [Đọc và diễn giải kết quả](#8-đọc-và-diễn-giải-kết-quả)
9. [Export kết quả](#9-export-kết-quả)
10. [Câu hỏi thường gặp](#10-câu-hỏi-thường-gặp)

---

## 1. Giới thiệu

**MainPath Analysis Tool** là công cụ phân tích mạng trích dẫn học thuật, được phát triển để thay thế **MainPath 492** (phần mềm thương mại, chỉ chạy trên Windows, đã hết license).

| | MainPath 492 | MainPath Analysis Tool |
|--|--|--|
| Nền tảng | Windows only | Windows + macOS |
| License | Thương mại, hết hạn | Mã nguồn mở (MIT) |
| Giao diện | Desktop app | Web app (Streamlit) |
| Thuật toán | SPC, SPLC, SPNP | SPC, SPLC, SPNP |
| KRMPA | ✅ | ✅ |
| Benchmark | — | 23/23 papers khớp ground truth |

---

## 2. Cài đặt

### Yêu cầu hệ thống
- **Python** 3.9 trở lên
- **OS**: Windows 10/11 hoặc macOS 11+
- RAM: tối thiểu 4GB (khuyến nghị 8GB với dataset lớn)

### Cài đặt từ source

```bash
# 1. Clone repo
git clone https://github.com/tonydisco/MainPath-Analyzer.git
cd MainPath-Analyzer

# 2. Cài dependencies
pip install -r requirements.txt
```

### Cài đặt bằng bản build sẵn (không cần Python)

Tải bản build tương ứng hệ điều hành tại:  
[github.com/tonydisco/MainPath-Analyzer/releases](https://github.com/tonydisco/MainPath-Analyzer/releases)

| File | Dành cho |
|------|----------|
| `MainPath-macOS.zip` | macOS 11+ |
| `MainPath-Windows.zip` | Windows 10/11 |

Giải nén và chạy file `MainPath` (macOS) hoặc `MainPath.exe` (Windows) — không cần cài Python.

### Thư viện sử dụng

| Thư viện | Phiên bản | Mục đích |
|----------|-----------|----------|
| `streamlit` | ≥ 1.35 | Giao diện web |
| `pandas` | ≥ 2.0 | Xử lý dữ liệu |
| `networkx` | ≥ 3.0 | Thuật toán đồ thị |
| `plotly` | ≥ 5.18 | Biểu đồ tương tác |
| `pyvis` | ≥ 0.3.2 | Visualize mạng trích dẫn |
| `openpyxl` | ≥ 3.1 | Xuất file Excel |

---

## 3. Khởi động tool

### Chạy từ source

```bash
cd MainPath-Analyzer
python3 -m streamlit run app.py
```

Tool sẽ tự mở trình duyệt tại `http://localhost:8501`.

> **Lưu ý:** Không đóng cửa sổ Terminal trong khi sử dụng. Nhấn `Ctrl+C` để tắt.

### Chạy bản build sẵn

- **macOS**: Double-click `MainPath` trong thư mục đã giải nén
- **Windows**: Double-click `MainPath.exe`

Trình duyệt sẽ tự mở. Nếu không, truy cập `http://localhost:8501`.

---

## 4. Chuẩn bị dữ liệu từ Web of Science

Tool nhận file export từ **Web of Science (WOS)** ở 2 định dạng:

### Định dạng 1: Plain Text (khuyến nghị)

1. Vào [webofscience.com](https://webofscience.com), thực hiện tìm kiếm
2. Chọn các bài báo cần phân tích
3. Click **Export → Plain Text File**
4. Trong cửa sổ Export:
   - **Record Content:** chọn **Full Record and Cited References**
   - **File Format:** Plain Text
5. Tải file về (thường tên là `savedrecs.txt`)

### Định dạng 2: Tab-delimited

1. **Export → Tab-delimited File**
2. Chọn **Full Record**

> **Quan trọng:** Bắt buộc phải export kèm **Cited References**. Nếu thiếu phần này, Main Path Analysis sẽ không hoạt động vì tool không có dữ liệu để xây dựng mạng trích dẫn.

### Giới hạn của WOS

- WOS chỉ cho export tối đa **500 records/lần**
- Nếu dataset lớn hơn: export nhiều lần thành nhiều file, tool hỗ trợ upload và ghép nhiều file cùng lúc (tự động loại bỏ trùng lặp theo WOS ID)

---

## 5. Luồng sử dụng cơ bản

```
1. Upload file WOS (.txt / .tsv)
         │
         ▼
2. Tool parse + xây dựng citation network
   (hiển thị: số records, số edges, match rate)
         │
         ▼
3. Chọn cài đặt phân tích (Sidebar)
   - Citation Matching Mode
   - Weight Method (SPLC / SPC / SPNP)
   - Search Strategy (global / local)
   - Number of Significant Routes
         │
         ▼
4. Click "▶ Run Analysis"
         │
         ▼
5. Xem kết quả ở các tab
         │
         ▼
6. Export Excel
```

### Chi tiết từng bước

**Bước 1 — Upload file**
- Sidebar trái → khu vực "Upload WOS export file"
- Kéo thả hoặc click để chọn file `.txt` / `.csv` / `.tsv`
- Có thể upload nhiều file cùng lúc (ghép tự động)

**Bước 2 — Kiểm tra Citation Matching**
- Tab **Overview** → mục "Citation Matching Details"
- Match rate > 5% là đủ để phân tích. Match rate > 20% cho kết quả tốt hơn
- Match rate thấp là bình thường: WOS cited references thường trỏ đến papers nằm ngoài dataset

**Bước 3 — Cài đặt**
- Sidebar → **Analysis Settings** (xem chi tiết mục 7)

**Bước 4 — Chạy phân tích**
- Click **▶ Run Analysis** — đợi 1–10 giây tùy kích thước dataset

**Bước 5 — Xem kết quả**
- Duyệt qua các tab: Main Path, KRMPA, Citation Network, Co-authors, Keywords

---

## 6. Giải thích từng tab

### Tab 📊 Overview

Tổng quan dataset sau khi upload:

| Thông tin | Ý nghĩa |
|-----------|---------|
| Records | Số bài báo trong dataset |
| Citation Edges | Số cạnh trích dẫn khớp được trong dataset |
| Year Range | Khoảng thời gian của dataset |
| Match Rate | % cited references khớp với records trong dataset |

- Biểu đồ số publications theo năm
- Biểu đồ tổng lần được trích dẫn theo năm
- Bảng toàn bộ records

---

### Tab 🛤️ Main Path (MPA)

**Tab chính của tool.** Tìm **một** đường đi quan trọng nhất trong mạng trích dẫn — chuỗi bài báo đại diện cho dòng chảy tri thức chính của lĩnh vực.

**Hiển thị:**
- **Network graph**: node = bài báo (màu theo năm, kích thước theo times_cited), cạnh đỏ = main path, cạnh xám = các citation khác
- **Edge weight bar chart**: top edges có traversal weight cao nhất
- **Bảng records**: danh sách bài trên main path kèm `position`, `edge_weight_to_next`, `title`, `year`, `times_cited`

**Cách đọc:** Đọc từ trên xuống theo `position`. Bài có `edge_weight_to_next` cao = kết nối tri thức mạnh giữa hai giai đoạn nghiên cứu.

---

### Tab 🔑 KRMPA (Key-Route Main Path)

Tìm **nhiều nhánh phát triển song song** của lĩnh vực bằng Key-Route Main Path Analysis.

**Cách hoạt động:**
1. Chọn top-N edges có traversal weight cao nhất làm "key routes"
2. Mỗi key route edge → trace ngược về nguồn + trace xuôi đến đích
3. Ghép thành N paths hoàn chỉnh

**Điều chỉnh:**
- Sidebar → "Number of Significant Routes" (khuyến nghị: 20)

**Ứng dụng:** Phát hiện các sub-streams nghiên cứu song song, ví dụ một field có 3 hướng phát triển khác nhau cùng thời kỳ.

---

### Tab 🔀 Multiple Paths

Tìm **N đường đi** quan trọng nhất theo thứ tự (không chia sẻ edges):

1. Tìm Path 1 (tổng weight lớn nhất)
2. Xóa tất cả edges của Path 1
3. Tìm Path 2 trong mạng còn lại
4. Lặp lại N lần

---

### Tab 📅 By Year

Main Path phân tầng theo năm — mỗi năm tìm main path trong tập con bài báo của năm đó.

**Ứng dụng:** Theo dõi sự dịch chuyển trọng tâm nghiên cứu qua từng giai đoạn.

---

### Tab 👥 Co-authors

Mạng cộng tác tác giả (undirected graph, edge weight = số bài cùng viết).

| Cột | Ý nghĩa |
|-----|---------|
| `paper_count` | Số bài báo trong dataset |
| `collaborator_count` | Số tác giả từng hợp tác |
| `total_collaborations` | Tổng số lần hợp tác |
| `degree_centrality` | Mức độ kết nối trung tâm (0–1) |

Network graph tương tác: kéo thả, zoom, hover để xem chi tiết.

---

### Tab 🔑 Keywords

Phân tích từ khóa từ hai nguồn:
- **DE (Author Keywords)**: từ khóa do tác giả đặt
- **ID (Keywords Plus)**: từ khóa WOS tự sinh từ title và references

Bao gồm: biểu đồ tần suất, mạng co-occurrence, Jaccard similarity giữa các bài báo.

---

### Tab 📥 Export

Xuất toàn bộ kết quả ra file Excel (nhiều sheet):

| Sheet | Nội dung |
|-------|---------|
| Records | Toàn bộ records đã parse |
| Citation Links | Edge list của citation network |
| Main Path | Nodes trên MPA + edge weights |
| KRMPA Paths | Tất cả paths từ KRMPA |
| Top SPLC Links | Bảng edge weight ranking |
| Co-authors | Thống kê tác giả + edge list |
| Keywords | Tần suất từ khóa |

---

## 7. Cài đặt phân tích

### Citation Matching Mode

Quyết định cách khớp cited references với records trong dataset:

| Mode | Phương pháp | Match Rate | Khuyến nghị |
|------|------------|------------|-------------|
| **Standard** | DOI + Author+Year+Journal | ~3–5% | ✅ Mặc định |
| **Strict** | DOI / WOS accession only | ~2–3% | Khi cần độ chính xác cao |
| **Aggressive** | Thêm unique Author+Year | ~5–8% | Khi dataset nhỏ, ít DOI |

> Standard mode cho kết quả tốt nhất trong benchmark 23-paper ground truth (23/23 papers tìm thấy).

---

### Weight Method

| Method | Công thức | Khi nào dùng |
|--------|-----------|-------------|
| **SPLC** | `fwd[u] × bwd[v]` | ✅ Mặc định — khớp MainPath 492 |
| **SPC** | `fwd[u] × bwd[v]` (normalized) | Kết quả tương tự SPLC |
| **SPNP** | `sources_reaching[u] × sinks_reachable[v]` | Đo phạm vi kết nối |

---

### Search Strategy (cho MPA)

| Strategy | Cách hoạt động | Ưu điểm |
|----------|---------------|---------|
| **global** | DP: tìm path tổng weight lớn nhất | ✅ Tối ưu, kết quả nhất quán |
| **local forward** | Greedy: từ source, luôn chọn cạnh weight cao nhất | Nhanh với network rất lớn |
| **local backward** | Greedy: từ sink, trace ngược | Ít dùng |

---

### Number of Significant Routes (cho KRMPA)

- Số key-route edges được chọn làm điểm xuất phát
- **Khuyến nghị: 20** (tìm đủ branches mà không quá nhiễu)
- Tăng lên 25–30 nếu muốn thêm nhánh phụ

---

## 8. Đọc và diễn giải kết quả

### Ý nghĩa của Main Path

Main path = **"xương sống tri thức"** (intellectual backbone):
- Chuỗi bài báo đại diện cho dòng phát triển CHÍNH của lĩnh vực
- Mỗi node trên path là **bước ngoặt quan trọng** về mặt học thuật
- Cạnh (A → B): B được nhiều nghiên cứu sau trích dẫn thông qua A

### Đọc bảng kết quả MPA

```
pos  label            year   edge_weight   times_cited
 1   SambamurthyZ1999  1999      9300          890
 2   WeillR2005        2005      7200          650
 3   BradleyBPTPM2012  2012      4158          320
 4   WuSL2015          2015      3542          180
...
14   DavidWBA2025      2025       —             5
```

- **pos 1** = bài "nguồn" cổ nhất — gốc của dòng tri thức
- **edge_weight** = SPLC của cạnh nối sang bài tiếp theo (càng cao = kết nối càng mạnh)
- **pos cuối** = bài mới nhất — "đỉnh" hiện tại của lĩnh vực
- **edge_weight = —** ở pos cuối vì không có bài tiếp theo

### Lưu ý khi diễn giải

1. **Times cited cao ≠ nhất thiết trên main path** — có thể được trích dẫn nhiều nhưng không nằm trên dòng chảy chính
2. **Kết quả phụ thuộc dataset** — thêm/bớt papers sẽ thay đổi kết quả
3. **Match rate thấp (<5%) → kết quả kém tin cậy** — cần export đầy đủ Cited References
4. **KRMPA 33 nodes vs 23 standard** — tool có thể ra nhiều hơn standard, phần extra là papers liên quan nhưng không phải core stream

---

## 9. Export kết quả

Click **📥 Download Excel Report** ở tab Export → tải về `mainpath_analysis.xlsx`.

### Dùng kết quả trong nghiên cứu

| Sheet Excel | Dùng để |
|-------------|---------|
| Main Path | Viết phần phân tích main path trong paper |
| KRMPA Paths | Phân tích các nhánh phát triển song song |
| Top SPLC Links | Vẽ lại network bằng Gephi/VOSviewer |
| Co-authors | Identify key researchers trong lĩnh vực |
| Keywords | Phân tích xu hướng nghiên cứu theo thời gian |

---

## 10. Câu hỏi thường gặp

**Q: Match rate của tôi rất thấp (~2–3%), có bình thường không?**  
A: Hoàn toàn bình thường. WOS cited references thường trỏ đến papers nằm ngoài dataset (ví dụ dataset 700 papers nhưng trích dẫn hàng chục nghìn papers khác). Match rate 2–5% là điển hình với Standard mode. Chỉ cần > 2% là có thể phân tích được.

**Q: Main path chỉ có 2–3 nodes, quá ngắn?**  
A: Hai nguyên nhân phổ biến: (1) dataset quá nhỏ (< 100 papers), hoặc (2) export WOS thiếu Cited References. Kiểm tra lại file export có trường `CR` không.

**Q: KRMPA tìm ra nhiều nodes hơn standard result?**  
A: Bình thường. Tool ra 31–35 nodes nhưng bao gồm toàn bộ standard 23 papers. Nodes extra là papers liên quan nhưng không thuộc core stream của ground truth.

**Q: Nên chọn SPLC hay SPC?**  
A: **SPLC** — khớp với MainPath 492, dùng làm kết quả chính. SPC cho kết quả tương tự nhưng scale khác.

**Q: Kết quả global và local search khác nhau nhiều không?**  
A: Thường khác 1–3 nodes ở đầu hoặc cuối. `global` (DP) luôn cho kết quả tối ưu toàn cục. Dùng `global` làm kết quả chính để đảm bảo tính nhất quán.

**Q: Tool có chạy offline không?**  
A: Có. Chạy hoàn toàn local, không cần internet sau khi cài đặt.
