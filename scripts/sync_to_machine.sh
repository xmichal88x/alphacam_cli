#!/usr/bin/env bash
# sync_to_machine.sh — synchronizacja kodu repo z maszyną AlphaCAM
#
# Użycie (z katalogu repo):  bash scripts/sync_to_machine.sh
# Wymagania: klucz SSH (~/.ssh/id_ed25519) + Tailscale (dostęp do 100.71.109.69).
#
# Upload (tar+scp):
#   - src/alphacam_cli/                          -> <repo>\src\alphacam_cli
#   - tests/unit + tests/conftest.py + tests/__init__.py -> <repo>\tests
#   - scripts/                                   -> <repo>\scripts
#   - docs/gateway.md, AGENTS.md, tasks.md        -> <repo>
# Po uploadzie weryfikuje SHA1 każdego pliku src/alphacam_cli i scripts na maszynie
# (Get-FileHash przez ssh). Exit 0 = SYNC OK, exit 1 = DIFF lub błąd połączenia.

set -euo pipefail

MACHINE_USER="48797"
MACHINE_HOST="100.71.109.69"
MACHINE_KEY="$HOME/.ssh/id_ed25519"
MACHINE_REPO='C:\Users\48797\Documents\PROJEKTY\alphacam_cli\alphacam_cli'

TMP_DIR="/tmp/opencode"
DEST="$MACHINE_USER@$MACHINE_HOST"
SSH_OPTS=(-i "$MACHINE_KEY" -o ConnectTimeout=15)

[[ -d src/alphacam_cli ]] || { echo "BLAD: uruchom z katalogu repo" >&2; exit 1; }
mkdir -p "$TMP_DIR"

echo "Polaczenie SSH ..."
ssh "${SSH_OPTS[@]}" "$DEST" "echo ok" >/dev/null 2>&1 || {
  echo "BLAD: brak polaczenia z $DEST (klucz SSH / Tailscale?)" >&2
  exit 1
}

# --- [1/4] src/alphacam_cli ---
echo "[1/4] Upload src/alphacam_cli ..."
tar --exclude='__pycache__' --exclude='*.pyc' -C src/alphacam_cli -czf "$TMP_DIR/src_sync.tgz" .
scp "${SSH_OPTS[@]}" "$TMP_DIR/src_sync.tgz" "$DEST:src_sync.tgz"
ssh "${SSH_OPTS[@]}" "$DEST" "tar -xzf src_sync.tgz -C $MACHINE_REPO\\src\\alphacam_cli"

# --- [2/4] tests ---
echo "[2/4] Upload tests ..."
tar --exclude='__pycache__' --exclude='*.pyc' -C tests -czf "$TMP_DIR/tests_sync.tgz" unit conftest.py __init__.py
scp "${SSH_OPTS[@]}" "$TMP_DIR/tests_sync.tgz" "$DEST:tests_sync.tgz"
ssh "${SSH_OPTS[@]}" "$DEST" "tar -xzf tests_sync.tgz -C $MACHINE_REPO\\tests"

# --- [3/4] scripts ---
echo "[3/4] Upload scripts ..."
tar --exclude='__pycache__' --exclude='*.pyc' -C scripts -czf "$TMP_DIR/scripts_sync.tgz" .
scp "${SSH_OPTS[@]}" "$TMP_DIR/scripts_sync.tgz" "$DEST:scripts_sync.tgz"
ssh "${SSH_OPTS[@]}" "$DEST" "tar -xzf scripts_sync.tgz -C $MACHINE_REPO\\scripts"

# --- [4/4] pojedyncze pliki (docs + md) ---
echo "[4/4] Upload docs/gateway.md, AGENTS.md, tasks.md ..."
tar -czf "$TMP_DIR/misc_sync.tgz" docs/gateway.md AGENTS.md tasks.md
scp "${SSH_OPTS[@]}" "$TMP_DIR/misc_sync.tgz" "$DEST:misc_sync.tgz"
ssh "${SSH_OPTS[@]}" "$DEST" "tar -xzf misc_sync.tgz -C $MACHINE_REPO"

# --- Weryfikacja: SHA1 per plik (src/alphacam_cli + scripts) ---
echo "Weryfikacja hash (SHA1) ..."
FILES=()
while IFS= read -r f; do
  FILES+=("$f")
done < <(find src/alphacam_cli -type f ! -path '*/__pycache__/*')
while IFS= read -r f; do
  FILES+=("$f")
done < <(find scripts -type f ! -path '*/__pycache__/*')

DIFF_COUNT=0
for f in "${FILES[@]}"; do
  LOCAL=$(sha1sum "$f" | cut -d' ' -f1)
  W=$(echo "$f" | sed 's|/|\\\\|g')
  REMOTE=$(ssh "${SSH_OPTS[@]}" "$DEST" "powershell -Command \"(Get-FileHash '$MACHINE_REPO\\$W' -Algorithm SHA1).Hash.ToLower()\"" 2>/dev/null | tr -d '\r ' || true)
  if [[ "$LOCAL" != "$REMOTE" ]]; then
    echo "  DIFF: $f"
    DIFF_COUNT=$((DIFF_COUNT + 1))
  fi
done

if (( DIFF_COUNT > 0 )); then
  echo "BLAD: $DIFF_COUNT plikow roznych (DIFF)" >&2
  exit 1
fi
echo "SYNC OK"
