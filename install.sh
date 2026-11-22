#!/usr/bin/env bash
# Compatibility shim: install.py is the real, cross-platform installer.
#
#   curl -fsSL https://raw.githubusercontent.com/dirk-makerhafen/AgentOne/main/install.sh | bash
#
# When run from a checkout it uses the local install.py; otherwise it downloads
# it. Prefer running install.py directly with Python (works on Windows too):
#
#   curl -fsSL https://raw.githubusercontent.com/dirk-makerhafen/AgentOne/main/install.py | python3 -

set -euo pipefail

INSTALLER_URL="${AGENTONE_INSTALLER_URL:-https://raw.githubusercontent.com/dirk-makerhafen/AgentOne/main/install.py}"

installer=""
source_path="${BASH_SOURCE[0]:-}"
if [[ -n "$source_path" && -f "$source_path" ]]; then
    script_dir="$(cd -- "$(dirname -- "$source_path")" && pwd)"
    if [[ -f "$script_dir/install.py" ]]; then
        installer="$script_dir/install.py"
    fi
fi

if [[ -z "$installer" ]]; then
    tmpdir="$(mktemp -d "${TMPDIR:-/tmp}/agentone-install.XXXXXX")"
    installer="$tmpdir/install.py"
    trap 'rm -rf "$tmpdir"' EXIT
    if command -v curl >/dev/null 2>&1; then
        curl -fsSL "$INSTALLER_URL" -o "$installer"
    elif command -v wget >/dev/null 2>&1; then
        wget -qO "$installer" "$INSTALLER_URL"
    else
        echo "curl or wget is required to download the installer." >&2
        exit 1
    fi
fi

if command -v python3 >/dev/null 2>&1; then
    python=python3
elif command -v python >/dev/null 2>&1; then
    python=python
else
    echo "Python 3.10+ is required to install AgentOne." >&2
    exit 1
fi

exec "$python" "$installer" "$@"
