#!/usr/bin/env bash
# AgentOne installer / bootstrap.
#
#   curl -fsSL https://raw.githubusercontent.com/dirk-makerhafen/AgentOne/main/install.sh | bash
#
# Environment overrides:
#   AGENTONE_REPO_URL   repository to clone (default: HTTPS GitHub URL)
#   AGENTONE_BRANCH     branch to check out (default: main)
#   AGENTONE_DIR        target directory (default: ./AgentOne)
#
# Flags:
#   --dir DIR           target directory
#   --branch BRANCH     branch to check out
#   --skip-setup        do not run `manage.py server setup`
#   --with-browser      also download the Camoufox browser build

set -euo pipefail

REPO_URL="${AGENTONE_REPO_URL:-https://github.com/dirk-makerhafen/AgentOne.git}"
BRANCH="${AGENTONE_BRANCH:-main}"
TARGET_DIR="${AGENTONE_DIR:-}"
SKIP_SETUP=0
WITH_BROWSER=0

usage() {
    cat <<'EOF'
Usage: install.sh [--dir DIR] [--branch BRANCH] [--skip-setup] [--with-browser]
EOF
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --dir) TARGET_DIR="${2:?--dir needs a path}"; shift 2 ;;
        --branch) BRANCH="${2:?--branch needs a name}"; shift 2 ;;
        --skip-setup) SKIP_SETUP=1; shift ;;
        --with-browser) WITH_BROWSER=1; shift ;;
        -h|--help) usage; exit 0 ;;
        *) echo "Unknown argument: $1" >&2; usage >&2; exit 2 ;;
    esac
done

TARGET_DIR="${TARGET_DIR:-$PWD/AgentOne}"

for tool in git python3; do
    if ! command -v "$tool" >/dev/null 2>&1; then
        echo "Missing required tool: $tool" >&2
        exit 1
    fi
done

if ! python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)'; then
    echo "AgentOne needs Python 3.10 or newer." >&2
    exit 1
fi

mkdir -p "$(dirname "$TARGET_DIR")"

if [[ ! -d "$TARGET_DIR/.git" ]]; then
    if [[ -e "$TARGET_DIR" && -n "$(ls -A "$TARGET_DIR" 2>/dev/null)" ]]; then
        echo "Target directory is not empty and is not a git checkout: $TARGET_DIR" >&2
        exit 1
    fi
    echo "==> Cloning $REPO_URL ($BRANCH) into $TARGET_DIR"
    git clone --branch "$BRANCH" "$REPO_URL" "$TARGET_DIR"
else
    echo "==> Using existing checkout: $TARGET_DIR"
fi

cd "$TARGET_DIR"

if [[ ! -d venv ]]; then
    echo "==> Creating virtual environment"
    python3 -m venv venv || {
        echo "Could not create venv. On Debian/Ubuntu install python3-venv first." >&2
        exit 1
    }
fi

PYTHON="$TARGET_DIR/venv/bin/python"
if [[ ! -x "$PYTHON" ]]; then
    echo "Virtual environment is missing its Python at $PYTHON" >&2
    exit 1
fi

echo "==> Installing Python dependencies"
"$PYTHON" -m pip install --upgrade pip
"$PYTHON" -m pip install -r requirements.txt

if [[ ! -f config/settings_local.py && "$SKIP_SETUP" -eq 0 ]]; then
    echo "==> Interactive setup (database, Redis, listen address, TLS)"
    "$PYTHON" manage.py server setup
fi

echo "==> Migrating database"
"$PYTHON" manage.py migrate --noinput

echo "==> Collecting static files"
"$PYTHON" manage.py collectstatic --noinput

echo "==> Reloading manifests"
"$PYTHON" manage.py reload_all

if [[ "$WITH_BROWSER" -eq 1 ]]; then
    echo "==> Fetching Camoufox browser build (large download)"
    "$PYTHON" manage.py server browser fetch
fi

if command -v redis-server >/dev/null 2>&1; then
    if ! redis-cli ping >/dev/null 2>&1; then
        echo "NOTE: Redis is installed but not responding on localhost:6379." >&2
    fi
else
    echo "NOTE: Redis was not found. Install/start it before running AgentOne." >&2
fi

cat <<EOF

AgentOne installed in $TARGET_DIR

Next steps:
  cd "$TARGET_DIR"
  source venv/bin/activate
  python manage.py server run

Optional (needs sudo/root):
  python manage.py server service install

Future updates:
  python manage.py server update
  ...or use Settings -> System -> Update AgentOne in the UI.
EOF
