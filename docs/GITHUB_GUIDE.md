# Hướng dẫn GitHub — CI/CD, Release, và Quy trình phát triển

> Tài liệu này mô tả cấu hình GitHub, quy trình build tự động, và workflow phát triển cho MainPath Analysis Tool.

## Mục lục
1. [Thông tin repo](#1-thông-tin-repo)
2. [Cấu trúc nhánh](#2-cấu-trúc-nhánh)
3. [Luồng CI/CD — GitHub Actions](#3-luồng-cicd--github-actions)
4. [Quy trình phát hành phiên bản mới](#4-quy-trình-phát-hành-phiên-bản-mới)
5. [Chi tiết workflow build.yml](#5-chi-tiết-workflow-buildyml)
6. [Quy ước commit message](#6-quy-ước-commit-message)
7. [Semantic versioning](#7-semantic-versioning)
8. [Build thủ công (local)](#8-build-thủ-công-local)
9. [Troubleshooting](#9-troubleshooting)

---

## 1. Thông tin repo

| | |
|--|--|
| **URL** | [github.com/tonydisco/MainPath-Analyzer](https://github.com/tonydisco/MainPath-Analyzer) |
| **Clone (SSH)** | `git@github.com:tonydisco/MainPath-Analyzer.git` |
| **Clone (HTTPS)** | `https://github.com/tonydisco/MainPath-Analyzer.git` |
| **Default branch** | `main` |
| **License** | MIT |

---

## 2. Cấu trúc nhánh

```
main ─────────────────────────────────────── (nhánh chính, luôn stable)
  │
  ├─── feature/ten-tinh-nang ──────────────── (nhánh phát triển tính năng)
  ├─── fix/ten-bug ────────────────────────── (nhánh fix bug)
  └─── v1.0.0 (tag) ───────────────────────── (đánh dấu release)
```

**Quy tắc:**
- Không commit trực tiếp lên `main` với thay đổi lớn
- Mỗi tính năng/bug làm trên nhánh riêng, merge vào `main` khi xong
- Tags `v*` được tạo từ `main` sau khi đã test ổn định

---

## 3. Luồng CI/CD — GitHub Actions

### Tổng quan

```
Developer push / tag
        │
        ▼
┌───────────────────────────────────────────┐
│         GitHub Actions Trigger            │
│     (.github/workflows/build.yml)         │
└───────────┬───────────────────────────────┘
            │
     ┌──────┴───────┐
     │              │
     ▼              ▼
┌──────────┐   ┌───────────┐
│  Job:    │   │  Job:     │
│ build-   │   │ build-    │
│ macos    │   │ windows   │
│          │   │           │
│macos-    │   │windows-   │
│latest    │   │latest     │
│          │   │           │
│Python3.11│   │Python3.11 │
│+ deps    │   │+ deps     │
│          │   │           │
│pyinstall │   │pyinstall  │
│er build  │   │er build   │
│          │   │           │
│MainPath- │   │MainPath-  │
│macOS.zip │   │Windows.zip│
└────┬─────┘   └─────┬─────┘
     │               │
     └──────┬─────────┘
            │
            ▼ (chỉ khi push tag v*)
    ┌───────────────┐
    │  Job: release │
    │  ubuntu-latest│
    │               │
    │ Download both │
    │ artifacts     │
    │               │
    │ Create GitHub │
    │ Release với   │
    │ changelog     │
    │ + 2 file zip  │
    └───────────────┘
```

### Điều kiện trigger

| Sự kiện | build-macos | build-windows | release |
|---------|:-----------:|:-------------:|:-------:|
| `git push origin main` | ✅ | ✅ | ❌ |
| `git push origin v*` (tag) | ✅ | ✅ | ✅ |
| Chạy tay từ GitHub UI | ✅ | ✅ | ❌ |
| Pull Request | ❌ | ❌ | ❌ |

### Xem kết quả build

- **Actions tab**: `github.com/tonydisco/MainPath-Analyzer/actions`
- **Download artifact** (build từ push thường): click vào workflow run → Artifacts section
- **Releases** (build từ tag): `github.com/tonydisco/MainPath-Analyzer/releases`

---

## 4. Quy trình phát hành phiên bản mới

### Bước 1 — Phát triển và commit

```bash
# Làm việc trên nhánh feature
git checkout -b feature/them-tinh-nang-moi

# Code, test, commit
git add <files>
git commit -m "feat: mô tả tính năng"

# Merge vào main khi xong
git checkout main
git merge feature/them-tinh-nang-moi
git push origin main
```

Sau khi push lên `main`: GitHub Actions tự build macOS + Windows (có thể download từ Actions tab để test thử).

---

### Bước 2 — Tạo release chính thức

```bash
# Đảm bảo đang ở main và đã pull latest
git checkout main
git pull

# Tạo tag version
git tag v1.1.0 -m "Release v1.1.0 — mô tả ngắn"
git push origin v1.1.0
```

GitHub Actions sẽ tự động:
1. Build `MainPath-macOS.zip` trên `macos-latest`
2. Build `MainPath-Windows.zip` trên `windows-latest`
3. Tạo GitHub Release với changelog + đính kèm 2 file

---

### Bước 3 — Kiểm tra

```bash
# Xem các tags đã tạo
git tag -l

# Xem log gần đây
git log --oneline -10
```

Trên GitHub:
- `Actions` → xem build đang chạy / đã xong
- `Releases` → xem release vừa tạo, download thử file

---

### Bước 4 — Xử lý nếu build fail

```bash
# Nếu cần xóa tag và tạo lại
git tag -d v1.1.0              # xóa local
git push origin :refs/tags/v1.1.0  # xóa remote

# Fix lỗi, commit, rồi tag lại
git commit -m "fix: sửa lỗi build"
git push
git tag v1.1.0
git push origin v1.1.0
```

---

## 5. Chi tiết workflow `build.yml`

File: `.github/workflows/build.yml`

### Job: `build-macos`

```yaml
runs-on: macos-latest
steps:
  - uses: actions/checkout@v4
  - uses: actions/setup-python@v5  # Python 3.11
  - pip install -r requirements.txt
  - pip install pyinstaller
  - pyinstaller mainpath.spec --clean --noconfirm
  - zip -r MainPath-macOS.zip dist/MainPath/
  - upload-artifact: MainPath-macOS
```

**Output:** `MainPath-macOS.zip` (chứa folder `MainPath/` với executable)

---

### Job: `build-windows`

```yaml
runs-on: windows-latest
steps:
  - uses: actions/checkout@v4
  - uses: actions/setup-python@v5  # Python 3.11
  - pip install -r requirements.txt
  - pip install pyinstaller
  - pyinstaller mainpath.spec --clean --noconfirm
  - Compress-Archive dist/MainPath MainPath-Windows.zip
  - upload-artifact: MainPath-Windows
```

**Output:** `MainPath-Windows.zip` (chứa folder `MainPath/` với `MainPath.exe`)

---

### Job: `release` (chỉ khi tag `v*`)

```yaml
needs: [build-macos, build-windows]
runs-on: ubuntu-latest
if: startsWith(github.ref, 'refs/tags/')
steps:
  - Download cả 2 artifacts
  - softprops/action-gh-release@v2:
      name: "MainPath Analyzer {tag}"
      body: changelog markdown
      files: MainPath-macOS.zip, MainPath-Windows.zip
```

---

### PyInstaller spec — `mainpath.spec`

Spec file điều khiển quá trình đóng gói:

```python
Analysis(
    ["launcher.py"],           # Entry point
    datas=[
        ("app.py", "."),
        ("parsers/", "parsers"),
        ("algorithms/", "algorithms"),
        ("output/", "output"),
        (streamlit_static, "streamlit/static"),  # Streamlit assets
    ],
    hiddenimports=[
        "streamlit", "pandas", "networkx",
        "plotly", "pyvis", "openpyxl",
        "parsers.*", "algorithms.*", "output.*",
    ],
    excludes=["matplotlib", "scipy", "PIL", "tensorflow"],
)
EXE(name="MainPath", console=False)  # Không hiện terminal window
COLLECT(...)  # Folder distribution (không single-file để dễ debug)
```

**Lưu ý:** Build tạo ra FOLDER `dist/MainPath/` (không phải single .exe) để tránh lỗi với Streamlit static assets.

---

## 6. Quy ước commit message

Tool dùng **Conventional Commits** (commitlint standard):

```
<type>(<scope>): <mô tả ngắn, tiếng Anh hoặc tiếng Việt>

[body tùy chọn — giải thích WHY, không phải WHAT]

[footer tùy chọn — breaking changes, issue refs]
```

### Loại commit (type)

| Type | Khi nào dùng | Ảnh hưởng version |
|------|-------------|-------------------|
| `feat` | Thêm tính năng mới | MINOR (1.x.0) |
| `fix` | Sửa bug | PATCH (1.0.x) |
| `ci` | Thay đổi CI/CD pipeline | — |
| `docs` | Cập nhật tài liệu | — |
| `chore` | Config, dependencies, tooling | — |
| `refactor` | Refactor không thêm tính năng | — |
| `perf` | Cải thiện hiệu năng | PATCH |
| `test` | Thêm/sửa tests | — |

### Ví dụ commit tốt

```bash
# Thêm tính năng
git commit -m "feat: add tied-sink expansion in KRMPA to recover all 23/23 standard papers"

# Fix bug
git commit -m "fix: correct edge direction from citing→cited to cited→citing"

# Cập nhật CI
git commit -m "ci: add macOS and Windows build jobs to GitHub Actions workflow"

# Tài liệu
git commit -m "docs: split documentation into 3 separate files by audience"
```

### Commit message KHÔNG tốt (tránh)

```bash
git commit -m "update"                    # Quá mơ hồ
git commit -m "fix bug"                   # Không biết bug gì
git commit -m "WIP"                       # Work in progress không nên push main
git commit -m "changes from yesterday"    # Không có ý nghĩa
```

---

## 7. Semantic Versioning

Format: `vMAJOR.MINOR.PATCH`

```
v  1  .  1  .  0
   │     │     └── PATCH: bug fix, không thay đổi API/tính năng
   │     └──────── MINOR: thêm tính năng mới, backward-compatible
   └────────────── MAJOR: breaking change, thay đổi lớn về API hoặc UX
```

### Ví dụ

| Version | Lý do tăng |
|---------|-----------|
| `v1.0.0` | Phiên bản đầu tiên public |
| `v1.0.1` | Fix bug SPLC formula |
| `v1.1.0` | Thêm tab KRMPA mới |
| `v1.2.0` | Thêm edge direction fix + tied-sink expansion |
| `v2.0.0` | Redesign UI hoàn toàn hoặc thay đổi format output |

### Xem lịch sử version

```bash
git tag -l           # Liệt kê tất cả tags
git tag -l "v1.*"    # Chỉ tags v1.x.x
git show v1.0.0      # Xem chi tiết tag v1.0.0
```

---

## 8. Build thủ công (local)

Dùng khi cần debug build hoặc không muốn chờ GitHub Actions.

### macOS

```bash
# Cài PyInstaller
pip install pyinstaller

# Build từ thư mục gốc
cd MainPath-Analyzer
pyinstaller mainpath.spec --clean --noconfirm

# Kết quả
ls dist/MainPath/          # → thư mục chứa app
# Để phân phối: zip cả thư mục dist/MainPath/
cd dist && zip -r MainPath-macOS.zip MainPath/
```

### Windows

```bat
rem Chạy file batch có sẵn
cd MainPath-Analyzer\install_windows
build_exe.bat

rem Hoặc chạy trực tiếp
cd MainPath-Analyzer
pip install pyinstaller
python -m PyInstaller mainpath.spec --clean --noconfirm
```

**Kết quả:** `dist\MainPath\MainPath.exe`

> **Quan trọng:** PyInstaller KHÔNG hỗ trợ cross-compile.
> - macOS build → chỉ chạy được trên macOS
> - Windows build → chỉ chạy được trên Windows
> - Cần 2 máy (hoặc dùng GitHub Actions) để có cả 2 bản

---

## 9. Troubleshooting

### Build fail — "Module not found"

Kiểm tra `hiddenimports` trong `mainpath.spec`, thêm module còn thiếu:

```python
hiddenimports=[
    ...,
    "ten.module.bi.thieu",
]
```

---

### Build fail — Streamlit assets missing

Đảm bảo `STREAMLIT_DIR` được detect đúng trong spec:

```python
import streamlit
STREAMLIT_DIR = Path(streamlit.__file__).parent
```

---

### Release không tạo tự động sau khi push tag

Kiểm tra:
1. Tag đúng format `v*` (ví dụ `v1.0.0`, không phải `1.0.0`)
2. Workflow có `permissions: contents: write` trong job release
3. Xem log tại `Actions` tab để biết lỗi cụ thể

---

### App chạy nhưng hiển thị trắng

Streamlit cần thời gian khởi động. Đợi 5–10 giây, reload trình duyệt. Nếu vẫn trắng, kiểm tra console log của app.

---

### Push bị reject do diverged history

```bash
# Không dùng --force trừ khi chắc chắn
git pull --rebase origin main
git push origin main
```

---

### Xóa tag nhầm và tạo lại

```bash
# Xóa local
git tag -d v1.1.0

# Xóa remote
git push origin --delete v1.1.0

# Tạo lại
git tag v1.1.0
git push origin v1.1.0
```
