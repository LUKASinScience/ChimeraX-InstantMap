#!/bin/bash
# Smoke test: build this bundle, install it into a THROWAWAY ChimeraX user dir (isolated HOME), run its commands.
# Your real ChimeraX settings/bundles are not touched.  Usage: tests/smoke_chimerax.sh [path/to/ChimeraX]
set -u
CX="${1:-$(ls -d /Applications/ChimeraX*.app/Contents/MacOS/ChimeraX 2>/dev/null | tail -1)}"
[ -x "$CX" ] || { echo "ChimeraX not found; pass its path as argument 1"; exit 2; }
HERE="$(cd "$(dirname "$0")/.." && pwd)"
TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT
rsync -a --exclude build --exclude dist --exclude '*.egg-info' --exclude site "$HERE/" "$TMP/bundle/"
export HOME="$TMP/home"; mkdir -p "$HOME"
fail=0; check() { if [ "$2" = "$3" ]; then echo "ok   $1"; else echo "FAIL $1 (got '$2', want '$3')"; fail=1; fi; }

"$CX" --nogui --exit --cmd "devel install $TMP/bundle user true" 2>&1 | grep -q "Installed ChimeraX-InstantMap" ; check "build + install" "$?" 0

out="$("$CX" --nogui --exit --cmd "usage instantmap listen; usage instantmap hint; usage instantmap tree" 2>&1)"
for c in "instantmap listen" "instantmap hint" "instantmap tree"; do echo "$out" | grep -q "'$c'" ; check "command registered: $c" "$?" 0; done

cat > "$TMP/listen_test.py" <<'PY'
import time
from chimerax.core.commands import run
from chimerax.instant_map import listen
listen.start(session); time.sleep(1.2)
alive = (listen.QUEUE / "alive").exists()
listen.stop(); time.sleep(0.2)
print("RESULT alive_while_on=%s alive_after_stop=%s" % (alive, (listen.QUEUE / "alive").exists()))
PY
res="$("$CX" --nogui --exit --script "$TMP/listen_test.py" 2>&1 | grep RESULT)"
check "listen start/stop" "$res" "RESULT alive_while_on=True alive_after_stop=False"

"$CX" --nogui --exit --cmd "instantmap hint false" 2>&1 | grep -q "hidden"; check "hint false persists a flag" "$?" 0
"$CX" --nogui --exit --cmd "instantmap hint true" 2>&1 | grep -q "will be shown"; check "hint true" "$?" 0
exit $fail
