#!/usr/bin/env bash
# ==============================================================================
# EasyDateien — Minimalistischer Terminal-Dateimanager für macOS
# Installationsskript
# ==============================================================================

set -e

echo "=== Installation von EasyDateien ==="

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
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
ln -sf "$SCRIPT_DIR/easydateien" "$CONFIG_DIR/easydateien"
ln -sf "$SCRIPT_DIR/easydateien_common.py" "$CONFIG_DIR/easydateien_common.py"
ln -sf "$SCRIPT_DIR/easydateien_konfigurator.py" "$CONFIG_DIR/easydateien_konfigurator.py"
chmod +x "$SCRIPT_DIR/easydateien" "$SCRIPT_DIR/easydateien_konfigurator.py"

if command -v clang >/dev/null 2>&1 && [ -f "$SCRIPT_DIR/easydateien_clip.m" ]; then
    echo "Kompiliere natives macOS-Clipboard-Modul..."
    clang -O3 -framework AppKit -framework Foundation "$SCRIPT_DIR/easydateien_clip.m" -o "$CONFIG_DIR/easydateien_clip"
    chmod +x "$CONFIG_DIR/easydateien_clip"
fi

# 3. Standard-Konfiguration initialisieren, falls noch nicht vorhanden
if [ ! -f "$CONFIG_DIR/config.json" ]; then
    echo "Erstelle Standard-Konfiguration in $CONFIG_DIR/config.json..."
    cp "$SCRIPT_DIR/config.example.json" "$CONFIG_DIR/config.json"
else
    echo "Bestehende Konfiguration in $CONFIG_DIR/config.json bleibt unberührt."
fi

# 4. Ausführbares Programm verlinken
for TARGET_BIN in "$HOME/.local/bin" "$HOME/bin"; do
    if [ -d "$TARGET_BIN" ]; then
        ln -sf "$SCRIPT_DIR/easydateien" "$TARGET_BIN/easydateien"
        ln -sf "$SCRIPT_DIR/easydateien" "$TARGET_BIN/ed"
    fi
done

echo "=============================================================================="
echo "ERFOLG: EasyDateien wurde erfolgreich installiert!"
echo "Befehl:  easydateien (oder kurz: ed)"
echo "Menü:    Tastenkürzel 'm' oder: easydateien --config"
echo "=============================================================================="
