#!/usr/bin/env bash
# =============================================================================
#  MainPath Analysis Tool — Launcher (macOS / Linux)
#  -----------------------------------------------------------------------------
#  Chạy file này để tự động:
#    1. Pull code mới nhất từ GitHub (nếu có mạng)
#    2. Tạo virtualenv (nếu chưa có)
#    3. Cài đặt dependencies
#    4. Start Streamlit app
#    5. Mở browser
#
#  Usage:
#    chmod +x start.sh          # lần đầu: cấp quyền thực thi
#    ./start.sh                 # chạy
#
#  Tuỳ chọn:
#    ./start.sh --no-pull       # bỏ qua git pull
#    ./start.sh --no-browser    # không tự mở browser
#    ./start.sh --port 8600     # đổi port (mặc định 8501)
# =============================================================================

set -e

# -------- Config --------
PORT=8501
DO_PULL=1
DO_BROWSER=1
VENV_DIR=".venv"
APP_SCRIPT="app.py"
REQ_FILE="requirements.txt"

# -------- Parse arguments --------
while [[ $# -gt 0 ]]; do
    case "$1" in
        --no-pull)    DO_PULL=0; shift ;;
        --no-browser) DO_BROWSER=0; shift ;;
        --port)       PORT="$2"; shift 2 ;;
        -h|--help)
            sed -n '2,20p' "$0"; exit 0 ;;
        *) echo "Unknown option: $1"; exit 1 ;;
    esac
done

# -------- Colors --------
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
BOLD='\033[1m'
RESET='\033[0m'

info()  { echo -e "${BLUE}ℹ${RESET}  $1"; }
ok()    { echo -e "${GREEN}✓${RESET}  $1"; }
warn()  { echo -e "${YELLOW}⚠${RESET}  $1"; }
fail()  { echo -e "${RED}✗${RESET}  $1"; exit 1; }
step()  { echo -e "\n${BOLD}${BLUE}▸ $1${RESET}"; }

# -------- Move to script directory --------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo -e "${BOLD}============================================${RESET}"
echo -e "${BOLD}  🔬 MainPath Analysis Tool — Launcher${RESET}"
echo -e "${BOLD}============================================${RESET}"

# -------- 1. Check Python --------
step "1/5 Checking Python"
if command -v python3 >/dev/null 2>&1; then
    PYTHON=python3
elif command -v python >/dev/null 2>&1; then
    PYTHON=python
else
    fail "Python 3 không được tìm thấy. Cài đặt tại https://www.python.org/downloads/"
fi

PY_VER=$("$PYTHON" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
ok "Python $PY_VER ($(which "$PYTHON"))"

# -------- 2. Git pull --------
step "2/5 Updating source"
if [[ $DO_PULL -eq 1 ]] && [[ -d .git ]] && command -v git >/dev/null 2>&1; then
    if git remote get-url origin >/dev/null 2>&1; then
        BRANCH=$(git branch --show-current)
        info "Pulling latest from origin/$BRANCH..."
        if git pull --ff-only origin "$BRANCH" 2>&1 | grep -qE "Already up to date|fast-forward|Fast-forward"; then
            ok "Source đã được cập nhật"
        else
            warn "Git pull gặp vấn đề (có thể do local changes). Tiếp tục với code hiện tại."
        fi
    else
        warn "Chưa có remote 'origin' — bỏ qua git pull"
    fi
else
    info "Bỏ qua git pull"
fi

# -------- 3. Setup virtualenv --------
step "3/5 Setting up virtualenv"
if [[ ! -d "$VENV_DIR" ]]; then
    info "Tạo virtualenv tại $VENV_DIR..."
    "$PYTHON" -m venv "$VENV_DIR" || fail "Không thể tạo virtualenv. Cài: $PYTHON -m pip install virtualenv"
    ok "Virtualenv đã tạo"
else
    ok "Virtualenv đã tồn tại"
fi

# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate"
VENV_PY="$VENV_DIR/bin/python"

# -------- 4. Install dependencies --------
step "4/5 Installing dependencies"
REQ_HASH=$("$VENV_PY" -c "import hashlib; print(hashlib.md5(open('$REQ_FILE','rb').read()).hexdigest())" 2>/dev/null || echo "")
STAMP_FILE="$VENV_DIR/.req.hash"

if [[ -f "$STAMP_FILE" ]] && [[ "$(cat "$STAMP_FILE")" == "$REQ_HASH" ]]; then
    ok "Dependencies đã được cài đầy đủ (skip)"
else
    info "Đang cài dependencies từ $REQ_FILE..."
    "$VENV_PY" -m pip install --upgrade pip --quiet
    "$VENV_PY" -m pip install -r "$REQ_FILE" --quiet
    echo "$REQ_HASH" > "$STAMP_FILE"
    ok "Dependencies đã cài xong"
fi

# -------- 5. Start Streamlit --------
step "5/5 Starting Streamlit"
URL="http://localhost:$PORT"
info "Server URL: ${BOLD}$URL${RESET}"
info "Nhấn Ctrl+C để dừng server"
echo ""

# Open browser after short delay
if [[ $DO_BROWSER -eq 1 ]]; then
    (
        sleep 3
        if command -v open >/dev/null 2>&1; then
            open "$URL"
        elif command -v xdg-open >/dev/null 2>&1; then
            xdg-open "$URL"
        fi
    ) &
fi

exec "$VENV_PY" -m streamlit run "$APP_SCRIPT" \
    --server.port "$PORT" \
    --server.headless true \
    --browser.gatherUsageStats false
