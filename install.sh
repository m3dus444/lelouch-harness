#!/usr/bin/env bash
# Install the `geass` command.
#
#   ./install.sh              install with the best tool available
#   ./install.sh --pipx       force pipx
#   ./install.sh --pip        force pip --user
#   ./install.sh --shim       no Python packaging at all; drop a shim on PATH
#
# The shim mode exists because geass has zero dependencies and runs straight
# from a checkout. If pip and pipx are both unavailable or unwanted, a two-line
# wrapper pointing at this directory is a complete install.

set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MODE="${1:-auto}"

have() { command -v "$1" >/dev/null 2>&1; }

python_bin() {
    for candidate in python3 python py; do
        if have "$candidate"; then echo "$candidate"; return 0; fi
    done
    echo "! no python found on PATH (need 3.9+)" >&2
    return 1
}

install_shim() {
    local py target dir
    py="$(python_bin)"

    for dir in "$HOME/.local/bin" "$HOME/bin"; do
        if [ -d "$dir" ]; then target="$dir/geass"; break; fi
    done
    if [ -z "${target:-}" ]; then
        mkdir -p "$HOME/.local/bin"
        target="$HOME/.local/bin/geass"
    fi

    cat > "$target" <<SHIM
#!/usr/bin/env bash
exec "$py" -m geass.cli "\$@"
SHIM
    # PYTHONPATH so `-m geass.cli` resolves without installing anything.
    sed -i.bak "2i export PYTHONPATH=\"$REPO:\${PYTHONPATH:-}\"" "$target" && rm -f "$target.bak"
    chmod +x "$target"

    echo "Installed shim: $target"
    case ":$PATH:" in
        *":$(dirname "$target"):"*) ;;
        *) echo "! $(dirname "$target") is not on your PATH — add it to use \`geass\`" >&2 ;;
    esac
}

case "$MODE" in
    --shim) install_shim ;;
    --pipx) pipx install --force "$REPO" ;;
    --pip)  "$(python_bin)" -m pip install --user --upgrade "$REPO" ;;
    auto)
        if have pipx; then
            echo "Using pipx (isolated, the tidiest option)."
            pipx install --force "$REPO"
        elif have pip3 || have pip; then
            echo "Using pip --user."
            "$(python_bin)" -m pip install --user --upgrade "$REPO"
        else
            echo "No pip or pipx found; falling back to a PATH shim."
            install_shim
        fi
        ;;
    *) echo "usage: ./install.sh [--pipx|--pip|--shim]" >&2; exit 2 ;;
esac

echo
echo "Verify with:  geass --help"
echo "Then, in any project:  geass cast"
