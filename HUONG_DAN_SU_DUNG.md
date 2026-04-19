# Hướng dẫn sử dụng MainPath Analysis Tool

> **Thay thế MainPath 492** — cross-platform, mã nguồn mở, không cần license.

## Mục lục
1. [Cài đặt](#1-cài-đặt)
2. [Khởi động tool](#2-khởi-động-tool)
3. [Chuẩn bị dữ liệu từ Web of Science](#3-chuẩn-bị-dữ-liệu-từ-web-of-science)
4. [Luồng sử dụng cơ bản](#4-luồng-sử-dụng-cơ-bản)
5. [Giải thích từng tab](#5-giải-thích-từng-tab)
6. [Cài đặt phân tích (Settings)](#6-cài-đặt-phân-tích-settings)
7. [Đọc kết quả và giải thích weight](#7-đọc-kết-quả-và-giải-thích-weight)
8. [Export kết quả](#8-export-kết-quả)
9. [Câu hỏi thường gặp](#9-câu-hỏi-thường-gặp)
10. [Phát triển và build release](#10-phát-triển-và-build-release)

---

## 1. Cài đặt

### Yêu cầu hệ thống
- Python 3.9 trở lên
- Windows 10/11 hoặc macOS 11+

### Cài đặt thư viện

Mở Terminal (macOS) hoặc Command Prompt (Windows), chạy:

```bash
cd đường_dẫn_đến_thư_mục/mainpath_tool
pip install -r requirements.txt
```

Các thư viện được cài đặt:
| Thư viện | Mục đích |
|---|---|
| `streamlit` | Giao diện web |
| `pandas` | Xử lý dữ liệu |
| `networkx` | Thuật toán đồ thị |
| `plotly` | Biểu đồ tương tác |
| `pyvis` | Visualize mạng tác giả |
| `openpyxl` | Xuất file Excel |

---

## 2. Khởi động tool

```bash
cd đường_dẫn_đến_thư_mục/mainpath_tool
python3 -m streamlit run app.py
```

Tool sẽ tự mở trình duyệt tại `http://localhost:8501`.

> **Lưu ý:** Không đóng cửa sổ Terminal trong khi sử dụng tool. Nhấn `Ctrl+C` để tắt.

---

## 3. Chuẩn bị dữ liệu từ Web of Science

Tool nhận file export từ **Web of Science (WOS)** ở 2 định dạng:

### Định dạng 1: Plain Text (khuyến nghị)

1. Vào Web of Science, thực hiện tìm kiếm
2. Chọn các bài báo cần phân tích (hoặc chọn tất cả)
3. Click **Export → Plain Text File**
4. Trong cửa sổ Export:
   - **Record Content:** chọn **Full Record and Cited References**
   - **File Format:** Plain Text
5. Tải file về (thường tên là `savedrecs.txt`)

### Định dạng 2: Tab-delimited

1. Export → Tab-delimited File
2. Chọn **Full Record**

> **Quan trọng:** Bắt buộc phải export kèm **Cited References** để tool xây dựng được mạng trích dẫn. Nếu thiếu phần này, Main Path Analysis sẽ không hoạt động.

### Giới hạn
- WOS chỉ cho export tối đa **500 records/lần**
- Nếu dataset lớn hơn, export nhiều lần rồi ghép file lại (tool hỗ trợ đọc file đã ghép)

---

## 4. Luồng sử dụng cơ bản

```
Upload file WOS
      ↓
Tool tự động parse + build citation network
      ↓
Chọn cài đặt (Weight Method, Search Strategy, Số paths)
      ↓
Click "Run Analysis"
      ↓
Xem kết quả ở các tab
      ↓
Export Excel
```

### Bước chi tiết

**Bước 1 — Upload file**
- Sidebar trái → khu vực "Upload WOS export file"
- Kéo thả hoặc click để chọn file `.txt` / `.csv` / `.tsv`
- Tool hiển thị: số records, số citation edges, match rate

**Bước 2 — Kiểm tra Citation Matching**
- Vào tab **Overview** → mở "📎 Citation Matching Details"
- Xem match rate. Match rate > 30% là chấp nhận được với WOS data
- Match rate thấp có thể do: dataset nhỏ, cited references trỏ ra ngoài dataset

**Bước 3 — Chọn cài đặt**
- Sidebar → **Analysis Settings**
- Chọn Weight Method, Search Strategy, số paths
- (Xem giải thích chi tiết ở mục 6)

**Bước 4 — Chạy phân tích**
- Click **▶ Run Analysis**
- Đợi vài giây (tùy kích thước dataset)

**Bước 5 — Xem kết quả**
- Duyệt qua các tab tương ứng

---

## 5. Giải thích từng tab

### Tab 📊 Overview
Tổng quan dataset:
- Số records, citation edges, khoảng năm, số journal
- **Match rate**: tỷ lệ cited references khớp với records trong dataset
- Biểu đồ số publications theo năm
- Biểu đồ tổng citations theo năm
- Bảng toàn bộ records

---

### Tab 🛤️ Main Path
**Đây là tab chính của tool.**

Hiển thị **một** đường đi quan trọng nhất trong mạng trích dẫn — chuỗi bài báo đại diện cho dòng chảy tri thức chính của lĩnh vực nghiên cứu.

**Nội dung:**
- **Network graph**: các node = bài báo, cạnh đỏ = main path, cạnh xám = các citation khác. Trục X = năm.
- **Edge weight bar chart**: top edges có traversal weight cao nhất
- **Bảng records**: danh sách bài báo trên main path, kèm:
  - `position`: thứ tự trên path
  - `edge_weight_to_next`: weight của cạnh nối sang bài tiếp theo
  - Thông tin bài báo: title, authors, year, journal, times_cited, doi

**Cách đọc:** Đọc từ trên xuống dưới theo `position`. Bài có `edge_weight_to_next` cao = kết nối tri thức mạnh.

---

### Tab 🔀 Multiple Paths
Tìm **N đường đi** quan trọng nhất (N được chọn ở sidebar).

Thuật toán: sau khi tìm xong Path 1, xóa các cạnh đó và tìm Path 2 trong phần còn lại, lặp lại.

**Ứng dụng:** Phát hiện nhiều nhánh phát triển song song trong một lĩnh vực nghiên cứu.

---

### Tab 📅 By Year
Main Path Analysis phân tầng theo năm xuất bản.

Mỗi năm, tool tìm main path trong tập con các bài báo của năm đó.

**Ứng dụng:** Theo dõi sự thay đổi trọng tâm nghiên cứu qua các giai đoạn thời gian.

**Cách dùng:** Chọn năm từ dropdown → xem path của năm đó.

---

### Tab 👥 Co-authors
Phân tích mạng cộng tác tác giả.

**Network graph (PyVis):** Tương tác được — kéo thả, zoom, hover để xem thông tin. Node to hơn = tác giả có nhiều bài báo hơn.

**Author Statistics:**
| Cột | Ý nghĩa |
|---|---|
| `paper_count` | Số bài báo trong dataset |
| `collaborator_count` | Số tác giả từng hợp tác |
| `total_collaborations` | Tổng số lần hợp tác |
| `degree_centrality` | Mức độ kết nối trung tâm (0–1) |

---

### Tab 🔑 Keywords
Phân tích từ khóa nghiên cứu.

**Nguồn từ khóa:**
- **DE (Author Keywords)**: từ khóa do tác giả tự đặt
- **ID (Keywords Plus)**: từ khóa do WOS tự generate từ title và references

**Nội dung:**
- Biểu đồ tần suất top keywords
- Bảng thống kê keyword với degree centrality và betweenness centrality trong mạng co-occurrence
- **Jaccard Similarity**: mức độ tương đồng giữa các bài báo dựa trên keywords chung

---

### Tab 📥 Export
Xuất toàn bộ kết quả ra một file Excel với nhiều sheet:

| Sheet | Nội dung |
|---|---|
| Records | Toàn bộ records |
| Main Path | Records trên main path + edge weights |
| Multiple Paths | Tất cả N paths gộp lại |
| Paths by Year | Paths theo từng năm |
| Edge Weights | Weight của tất cả edges trong network |
| Coauthor Stats | Thống kê tác giả |
| Coauthor Edges | Danh sách cặp cộng tác |
| Keywords | Tần suất từ khóa |

---

## 6. Cài đặt phân tích (Settings)

### Weight Method — Phương pháp tính trọng số

| Method | Tên đầy đủ | Khi nào dùng |
|---|---|---|
| **SPC** | Search Path Count | Mặc định, phù hợp hầu hết nghiên cứu |
| **SPLC** | Search Path Link Count | Khi muốn ưu tiên paths dài hơn |
| **SPNP** | Search Path Node Pair | Khi muốn đo phạm vi kết nối giữa các tài liệu |

**SPC là lựa chọn phổ biến nhất trong văn献 học thuật.**

#### Cách SPC hoạt động
Với mỗi cạnh (A → B) trong mạng:
```
SPC(A→B) = (số paths từ nguồn đến A) × (số paths từ B đến đích)
           ─────────────────────────────────────────────────────
                        tổng số paths trong network
```
Cạnh có SPC cao = nhiều "dòng chảy tri thức" đi qua cạnh đó.

### Search Strategy — Chiến lược tìm đường

| Strategy | Cách hoạt động | Ưu điểm |
|---|---|---|
| **global** | DP: tìm path có tổng weight lớn nhất | Tối ưu toàn cục, kết quả nhất quán |
| **local** | Greedy: mỗi bước chọn cạnh weight cao nhất | Nhanh hơn với network rất lớn |

**Khuyến nghị: dùng `global`.**

### Number of Main Paths
- Số lượng paths cần tìm trong tab **Multiple Paths**
- Thường chọn 3–5 để phân tích đủ nhưng không quá phức tạp

---

## 7. Đọc kết quả và giải thích weight

### Ý nghĩa của Main Path trong nghiên cứu

Main path đại diện cho **"xương sống tri thức"** (intellectual backbone) của lĩnh vực:
- Mỗi bài báo trên path là **bước ngoặt quan trọng** trong sự phát triển của lĩnh vực
- Cạnh (A → B) có weight cao = B được nhiều nghiên cứu sau này trích dẫn thông qua A

### Bảng kết quả Main Path

```
position | title          | year | edge_weight_to_next | times_cited
---------|----------------|------|---------------------|------------
1        | Bài đầu tiên   | 2001 | 0.142               | 450
2        | Bài thứ hai    | 2005 | 0.089               | 230
3        | Bài thứ ba     | 2010 | 0.034               | 89
4        | Bài cuối       | 2018 | null                | 12
```

- **position 1**: bài "nguồn" — xuất phát điểm của dòng chảy tri thức
- **edge_weight_to_next = 0.142**: 14.2% tổng search paths đi qua cạnh này
- **position cuối**: `edge_weight_to_next = null` vì là node cuối

### Lưu ý khi diễn giải

1. **Times cited cao ≠ nhất thiết trên main path**: một bài được trích dẫn nhiều nhưng không nằm trên dòng chảy chính
2. **Main path phụ thuộc vào dataset**: kết quả thay đổi nếu bạn thêm/bớt papers
3. **Match rate thấp (<20%) → kết quả kém tin cậy**: cần export đầy đủ Cited References

---

## 8. Export kết quả

### Từ tab Export
Click **📥 Download Excel Report** → file `mainpath_analysis.xlsx` được tải về.

### Sử dụng kết quả trong nghiên cứu
- **Sheet "Main Path"**: dùng để viết phần phân tích main path trong paper
- **Sheet "Edge Weights"**: dùng để vẽ lại network bằng Gephi/VOSviewer nếu cần
- **Sheet "Coauthor Stats"**: identify key researchers trong lĩnh vực
- **Sheet "Keywords"**: phân tích xu hướng nghiên cứu

---

## 9. Câu hỏi thường gặp

**Q: Match rate của tôi rất thấp (~5%), tại sao?**
A: Thường do WOS cited references trỏ đến papers nằm ngoài dataset. Ví dụ dataset chỉ có 200 papers nhưng chúng trích dẫn hàng nghìn papers khác. Đây là bình thường — chỉ cần match rate > 15–20% là đủ để có kết quả ý nghĩa.

**Q: Main path chỉ có 1–2 nodes, quá ngắn?**
A: Có 2 nguyên nhân: (1) dataset quá nhỏ, hoặc (2) các papers trong dataset ít trích dẫn lẫn nhau. Thử mở rộng dataset hoặc kiểm tra lại export có kèm Cited References chưa.

**Q: Tab Co-authors hiển thị trống?**
A: File WOS export cần có trường `AU` (Authors). Kiểm tra trong file export có dòng `AU ` không.

**Q: Nên chọn SPC, SPLC hay SPNP?**
A: Với nghiên cứu học thuật thông thường, **SPC** là chuẩn. SPLC và SPNP dùng khi bạn muốn so sánh sensitivity của kết quả với các phương pháp khác nhau (thường trong paper methodological).

**Q: Kết quả "global" và "local" search khác nhau nhiều không?**
A: Thường khác một vài nodes ở đầu/cuối. `global` cho kết quả tối ưu hơn về mặt toán học. Dùng `global` làm kết quả chính.

**Q: Tool có thể chạy offline không?**
A: Có. Tool chạy hoàn toàn local trên máy tính của bạn, không cần internet sau khi cài đặt.

---

## 10. Phát triển và build release

### Tổng quan kiến trúc source code

```
mainpath_tool/
├── app.py                      # Streamlit UI chính
├── parsers/
│   ├── wos_parser.py           # Đọc file WOS .txt → DataFrame
│   ├── citation_network.py     # Xây dựng DiGraph từ cited references
│   └── relationship_parser.py  # Đọc file relationship ngoài
├── algorithms/
│   ├── traversal_weights.py    # Tính SPC / SPLC / SPNP
│   ├── main_path.py            # MPA + KRMPA algorithms
│   ├── coauthor.py             # Mạng cộng tác tác giả
│   └── keyword.py              # Phân tích từ khóa
├── output/
│   ├── visualizer.py           # Biểu đồ plotly + pyvis
│   └── excel_export.py         # Xuất file Excel
├── .github/workflows/
│   └── build.yml               # CI/CD tự động build macOS + Windows
├── install_windows/
│   ├── build_exe.bat           # Build thủ công trên Windows
│   ├── install.bat             # Cài đặt môi trường Python
│   └── uninstall.bat
└── requirements.txt
```

---

### Luồng CI/CD — GitHub Actions

Toàn bộ quá trình build và phát hành được tự động hóa qua GitHub Actions:

```
Developer push code
        │
        ▼
┌─────────────────────────────────┐
│  github.com/tonydisco/          │
│  MainPath-Analyzer              │
│                                 │
│  .github/workflows/build.yml   │
└──────────┬──────────────────────┘
           │
     ┌─────┴──────┐
     │            │
     ▼            ▼
┌─────────┐  ┌──────────┐
│ macOS   │  │ Windows  │
│ runner  │  │ runner   │
│         │  │          │
│PyInstall│  │PyInstall │
│  er     │  │  er      │
└────┬────┘  └─────┬────┘
     │             │
     ▼             ▼
MainPath-     MainPath-
macOS.zip    Windows.zip
     │             │
     └──────┬──────┘
            │ (chỉ khi push tag v*)
            ▼
   GitHub Release tự động
   với cả 2 file đính kèm
```

**Trigger conditions:**

| Sự kiện | Build macOS | Build Windows | Tạo Release |
|---------|:-----------:|:-------------:|:-----------:|
| Push lên `main` | ✅ | ✅ | ❌ |
| Push tag `v*` | ✅ | ✅ | ✅ |
| Chạy tay (workflow_dispatch) | ✅ | ✅ | ❌ |

---

### Quy trình phát hành phiên bản mới

#### Bước 1 — Cập nhật code và commit

```bash
# Chỉnh sửa code xong, stage và commit như bình thường
git add <files>
git commit -m "feat: mô tả thay đổi"
git push
```

Lúc này GitHub Actions sẽ **tự động build** macOS + Windows (kết quả lưu trong tab Actions, có thể download thủ công để test).

#### Bước 2 — Tạo release chính thức

```bash
# Đặt tag version theo semantic versioning: vMAJOR.MINOR.PATCH
git tag v1.1.0
git push origin v1.1.0
```

GitHub Actions sẽ:
1. Build `MainPath-macOS.zip` trên `macos-latest`
2. Build `MainPath-Windows.zip` trên `windows-latest`
3. Tự động tạo **GitHub Release** tại `github.com/tonydisco/MainPath-Analyzer/releases`
4. Đính kèm cả 2 file zip vào release

#### Bước 3 — Kiểm tra release

Vào `github.com/tonydisco/MainPath-Analyzer/actions` để xem tiến trình build.
Vào `github.com/tonydisco/MainPath-Analyzer/releases` để xem release đã tạo.

---

### Convention đặt tên version

```
v MAJOR . MINOR . PATCH
  │        │       └── Bug fix, không thay đổi tính năng
  │        └────────── Thêm tính năng mới, backward-compatible
  └─────────────────── Breaking change hoặc redesign lớn
```

Ví dụ:
- `v1.0.0` — phiên bản đầu tiên
- `v1.1.0` — thêm tính năng mới (ví dụ: thêm tab mới)
- `v1.1.1` — fix bug nhỏ
- `v2.0.0` — thay đổi lớn về thuật toán hoặc UI

---

### Build thủ công (khi cần debug)

**macOS:**
```bash
pip install pyinstaller
cd mainpath_tool
pyinstaller mainpath.spec --clean --noconfirm
# Output: dist/MainPath/ → zip để phân phối
```

**Windows** (chạy trên máy Windows):
```bat
cd mainpath_tool\install_windows
build_exe.bat
# Output: dist\MainPath\MainPath.exe
```

> **Lưu ý:** PyInstaller không hỗ trợ cross-compile — macOS build phải chạy trên macOS, Windows build phải chạy trên Windows. Dùng GitHub Actions để build tự động cả hai nền tảng mà không cần có cả hai máy.

---

### Cấu trúc commit message

Tool này dùng **Conventional Commits**:

```
<type>: <mô tả ngắn>

[body tùy chọn]
```

| Type | Ý nghĩa |
|------|---------|
| `feat` | Thêm tính năng mới |
| `fix` | Sửa bug |
| `ci` | Thay đổi CI/CD pipeline |
| `docs` | Cập nhật tài liệu |
| `chore` | Công việc nền (config, deps) |
| `refactor` | Tái cấu trúc code, không thêm tính năng |
