#!/usr/bin/env bash
# ==============================================================================
# EasyDateien — Minimalistischer Terminal-Dateimanager für macOS
# Installationsskript
#
# Zwei Installationswege:
#   1. Aus dem geklonten Repository:  ./install.sh
#   2. Einzeilig ohne Klon (macOS, curl vorhanden):
#      curl -fsSL https://raw.githubusercontent.com/jonathank55/easydateien/main/install.sh | bash
#      bash <(curl -fsSL https://raw.githubusercontent.com/jonathank55/easydateien/main/install.sh)
# ==============================================================================

set -e

echo "=== Installation von EasyDateien ==="

RAW_BASE="https://raw.githubusercontent.com/jonathank55/easydateien/main"
PROGRAMM_DATEIEN=("easydateien" "easydateien_ui.py" "easydateien_actions.py" "easydateien_view.py" "easydateien_common.py" "easydateien_konfigurator.py" "config.json")

# ---------------------------------------------------------------- Quelle ermitteln
# Wurde das Skript aus einem vorhandenem Repository ausgeführt, liegt dieses
# Verzeichnis dort, wo die Programmdateien bereits lokal vorliegen. Wurde es
# per curl direkt in eine Shell gepipt, fehlen diese Dateien und werden
# vorübergehend in ein Arbeitsverzeichnis heruntergeladen.
SCRIPT_PATH="${BASH_SOURCE[0]:-$0}"
if [ -f "$SCRIPT_PATH" ]; then
    SCRIPT_DIR="$(cd "$(dirname "$SCRIPT_PATH")" && pwd)"
else
    SCRIPT_DIR=""
fi

if [ -n "$SCRIPT_DIR" ] && [ -f "$SCRIPT_DIR/easydateien" ] && [ -f "$SCRIPT_DIR/easydateien_common.py" ]; then
    SRC_DIR="$SCRIPT_DIR"
    CLEANUP_DIR=""
    echo "Installiere aus vorhandenem Verzeichnis: $SRC_DIR"
else
    command -v curl >/dev/null 2>&1 || { echo "Fehler: curl wird benötigt, um die Dateien herunterzuladen."; exit 1; }
    CLEANUP_DIR="$(mktemp -d "${TMPDIR:-/tmp}/easydateien-install.XXXXXX")"
    SRC_DIR="$CLEANUP_DIR"
    echo "Lade Programmdateien von GitHub nach $SRC_DIR ..."
    for DATEI in "${PROGRAMM_DATEIEN[@]}"; do
        curl -fsSL "$RAW_BASE/$DATEI" -o "$SRC_DIR/$DATEI"
    done
    # Clipboard-Quelle (optional; wird vom Programm sonst bei Bedarf kompiliert)
    curl -fsSL "$RAW_BASE/easydateien_clip.m" -o "$SRC_DIR/easydateien_clip.m" || rm -f "$SRC_DIR/easydateien_clip.m"
    trap 'rm -rf "$CLEANUP_DIR"' EXIT
fi

CONFIG_DIR="$HOME/.config/easydateien"

# 1. Zielverzeichnis im PATH ermitteln
INSTALL_DIR=""
if [ -d "$HOME/.local/bin" ] && [[ ":$PATH:" == *":$HOME/.local/bin:"* ]]; then
    INSTALL_DIR="$HOME/.local/bin"
elif [ -d "$HOME/bin" ] && [[ ":$PATH:" == *":$HOME/bin:"* ]]; then
    INSTALL_DIR="$HOME/bin"
elif [ -w "/usr/local/bin" ]; then
    INSTALL_DIR="/usr/local/bin"
else
    mkdir -p "$HOME/.local/bin"
    INSTALL_DIR="$HOME/.local/bin"
    echo "Hinweis: Bitte stellen Sie sicher, dass $HOME/.local/bin in Ihrem PATH liegt."
fi

# 2. Konfigurationsverzeichnis vorbereiten
mkdir -p "$CONFIG_DIR"

echo "Verlinke Programmdateien nach $CONFIG_DIR..."
ln -sf "$SRC_DIR/easydateien" "$CONFIG_DIR/easydateien"
ln -sf "$SRC_DIR/easydateien_ui.py" "$CONFIG_DIR/easydateien_ui.py"
    ln -sf "$SRC_DIR/easydateien_actions.py" "$CONFIG_DIR/easydateien_actions.py"
    ln -sf "$SRC_DIR/easydateien_view.py" "$CONFIG_DIR/easydateien_view.py"
    ln -sf "$SRC_DIR/easydateien_common.py" "$CONFIG_DIR/easydateien_common.py"
ln -sf "$SRC_DIR/easydateien_konfigurator.py" "$CONFIG_DIR/easydateien_konfigurator.py"
chmod +x "$CONFIG_DIR/easydateien" "$CONFIG_DIR/easydateien_konfigurator.py"

# Bei einer curl-Installation wurden die Dateien in ein temporäres Verzeichnis
# geladen, das nach Abschluss gelöscht wird. Damit die Verweise in $CONFIG_DIR
# gültig bleiben, werden sie in diesem Fall fest kopiert statt nur verlinkt.
if [ -n "$CLEANUP_DIR" ]; then
    rm -f "$CONFIG_DIR/easydateien" "$CONFIG_DIR/easydateien_ui.py" "$CONFIG_DIR/easydateien_actions.py" "$CONFIG_DIR/easydateien_view.py" "$CONFIG_DIR/easydateien_common.py" "$CONFIG_DIR/easydateien_konfigurator.py"
    cp "$SRC_DIR/easydateien" "$CONFIG_DIR/easydateien"
    cp "$SRC_DIR/easydateien_ui.py" "$CONFIG_DIR/easydateien_ui.py"
        cp "$SRC_DIR/easydateien_actions.py" "$CONFIG_DIR/easydateien_actions.py"
        cp "$SRC_DIR/easydateien_view.py" "$CONFIG_DIR/easydateien_view.py"
        cp "$SRC_DIR/easydateien_common.py" "$CONFIG_DIR/easydateien_common.py"
    cp "$SRC_DIR/easydateien_konfigurator.py" "$CONFIG_DIR/easydateien_konfigurator.py"
    chmod +x "$CONFIG_DIR/easydateien" "$CONFIG_DIR/easydateien_konfigurator.py"
    trap - EXIT
    rm -rf "$CLEANUP_DIR"
fi

if command -v clang >/dev/null 2>&1 && [ -f "$SRC_DIR/easydateien_clip.m" ]; then
    echo "Kompiliere natives macOS-Clipboard-Modul..."
    clang -O3 -framework AppKit -framework Foundation "$SRC_DIR/easydateien_clip.m" -o "$CONFIG_DIR/easydateien_clip"
    chmod +x "$CONFIG_DIR/easydateien_clip"
fi

# 3. Standard-Konfiguration initialisieren, falls noch nicht vorhanden
if [ ! -f "$CONFIG_DIR/config.json" ]; then
    echo "Erstelle Standard-Konfiguration in $CONFIG_DIR/config.json..."
    cp "$SRC_DIR/config.json" "$CONFIG_DIR/config.json"
else
    echo "Bestehende Konfiguration in $CONFIG_DIR/config.json bleibt unberührt."
fi

# Verwaiste Reste aus älteren Installationen entfernen (config.example.json
# wurde zu config.json umbenannt; alte Kopien werden nicht mehr gelesen)
if [ -f "$CONFIG_DIR/config.example.json" ]; then
    rm -f "$CONFIG_DIR/config.example.json"
    echo "Verwaiste Datei entfernt: $CONFIG_DIR/config.example.json"
fi

# 4. Ausführbares Programm verlinken
for TARGET_BIN in "$HOME/.local/bin" "$HOME/bin"; do
    if [ -d "$TARGET_BIN" ]; then
        ln -sf "$CONFIG_DIR/easydateien" "$TARGET_BIN/easydateien"
        ln -sf "$CONFIG_DIR/easydateien" "$TARGET_BIN/ed"
    fi
done

echo "=============================================================================="
echo "ERFOLG: EasyDateien wurde erfolgreich installiert!"
echo "Befehl:  easydateien (oder kurz: ed)"
echo "Menü:    Tastenkürzel 'm' oder: easydateien --config"
echo "=============================================================================="
