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
PROGRAMM_DATEIEN=("easydateien" "easydateien_ui.py" "easydateien_actions.py" "easydateien_view.py" "easydateien_common.py" "easydateien_preview.py" "easydateien_symlink.py" "easydateien_konfigurator.py" "config.json")

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
        OK=""
        for VERSUCH in 1 2 3; do
            if curl -fsSL --connect-timeout 10 --retry 2 "$RAW_BASE/$DATEI" -o "$SRC_DIR/$DATEI" && [ -s "$SRC_DIR/$DATEI" ]; then
                OK="ja"
                break
            fi
            echo "Hinweis: Download von '$DATEI' fehlgeschlagen (Versuch $VERSUCH von 3) — versuche erneut ..." >&2
            rm -f "$SRC_DIR/$DATEI"
            sleep 1
        done
        if [ -z "$OK" ]; then
            echo "==============================================================================" >&2
            echo "FEHLER: '$DATEI' konnte nicht geladen werden (Netzwerk instabil?)." >&2
            echo "Bitte Internet pruefen und erneut ausfuehren." >&2
            echo "==============================================================================" >&2
            exit 1
        fi
    done
    # Native macOS-Module (Clipboard & PDFKit)
    curl -fsSL --connect-timeout 10 --retry 2 "$RAW_BASE/easydateien_clip.m" -o "$SRC_DIR/easydateien_clip.m" || rm -f "$SRC_DIR/easydateien_clip.m"
    curl -fsSL --connect-timeout 10 --retry 2 "$RAW_BASE/easydateien_pdf.m" -o "$SRC_DIR/easydateien_pdf.m" || rm -f "$SRC_DIR/easydateien_pdf.m"
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
# Selbstheilung: Tote Symlinks und Altreste aus frueheren Installationen entfernen
for DATEI in easydateien easydateien_ui.py easydateien_actions.py easydateien_view.py easydateien_common.py easydateien_preview.py easydateien_symlink.py easydateien_konfigurator.py easydateien_clip.m easydateien_pdf.m config.example.json; do
    ZIEL="$CONFIG_DIR/$DATEI"
    if [ -L "$ZIEL" ] && [ ! -e "$ZIEL" ]; then
        rm -f "$ZIEL"
        echo "Entferne toten Symlink: $ZIEL"
    fi
done
if [ "$SRC_DIR" != "$CONFIG_DIR" ]; then
    ln -sf "$SRC_DIR/easydateien" "$CONFIG_DIR/easydateien"
    ln -sf "$SRC_DIR/easydateien_ui.py" "$CONFIG_DIR/easydateien_ui.py"
    ln -sf "$SRC_DIR/easydateien_actions.py" "$CONFIG_DIR/easydateien_actions.py"
    ln -sf "$SRC_DIR/easydateien_view.py" "$CONFIG_DIR/easydateien_view.py"
    ln -sf "$SRC_DIR/easydateien_common.py" "$CONFIG_DIR/easydateien_common.py"
    ln -sf "$SRC_DIR/easydateien_preview.py" "$CONFIG_DIR/easydateien_preview.py"
    ln -sf "$SRC_DIR/easydateien_symlink.py" "$CONFIG_DIR/easydateien_symlink.py"
    ln -sf "$SRC_DIR/easydateien_konfigurator.py" "$CONFIG_DIR/easydateien_konfigurator.py"
    [ -f "$SRC_DIR/easydateien_clip.m" ] && ln -sf "$SRC_DIR/easydateien_clip.m" "$CONFIG_DIR/easydateien_clip.m"
    [ -f "$SRC_DIR/easydateien_pdf.m" ] && ln -sf "$SRC_DIR/easydateien_pdf.m" "$CONFIG_DIR/easydateien_pdf.m"
fi
chmod +x "$CONFIG_DIR/easydateien" "$CONFIG_DIR/easydateien_konfigurator.py"

# Bei einer curl-Installation wurden die Dateien in ein temporäres Verzeichnis
# geladen, das nach Abschluss gelöscht wird. Damit die Verweise in $CONFIG_DIR
# gültig bleiben, werden sie in diesem Fall fest kopiert statt nur verlinkt.
if [ -n "$CLEANUP_DIR" ]; then
    rm -f "$CONFIG_DIR/easydateien" "$CONFIG_DIR/easydateien_ui.py" "$CONFIG_DIR/easydateien_actions.py" "$CONFIG_DIR/easydateien_view.py" "$CONFIG_DIR/easydateien_common.py" "$CONFIG_DIR/easydateien_preview.py" "$CONFIG_DIR/easydateien_symlink.py" "$CONFIG_DIR/easydateien_konfigurator.py" "$CONFIG_DIR/easydateien_clip.m" "$CONFIG_DIR/easydateien_pdf.m"
    cp "$SRC_DIR/easydateien" "$CONFIG_DIR/easydateien"
    cp "$SRC_DIR/easydateien_ui.py" "$CONFIG_DIR/easydateien_ui.py"
    cp "$SRC_DIR/easydateien_actions.py" "$CONFIG_DIR/easydateien_actions.py"
    cp "$SRC_DIR/easydateien_view.py" "$CONFIG_DIR/easydateien_view.py"
    cp "$SRC_DIR/easydateien_common.py" "$CONFIG_DIR/easydateien_common.py"
    cp "$SRC_DIR/easydateien_preview.py" "$CONFIG_DIR/easydateien_preview.py"
    cp "$SRC_DIR/easydateien_symlink.py" "$CONFIG_DIR/easydateien_symlink.py"
    cp "$SRC_DIR/easydateien_konfigurator.py" "$CONFIG_DIR/easydateien_konfigurator.py"
    [ -f "$SRC_DIR/easydateien_clip.m" ] && cp "$SRC_DIR/easydateien_clip.m" "$CONFIG_DIR/easydateien_clip.m"
    [ -f "$SRC_DIR/easydateien_pdf.m" ] && cp "$SRC_DIR/easydateien_pdf.m" "$CONFIG_DIR/easydateien_pdf.m"
    chmod +x "$CONFIG_DIR/easydateien" "$CONFIG_DIR/easydateien_konfigurator.py"
    trap - EXIT
    rm -rf "$CLEANUP_DIR"
fi

if command -v clang >/dev/null 2>&1 && [ -f "$SRC_DIR/easydateien_clip.m" ]; then
    echo "Kompiliere natives macOS-Clipboard-Modul..."
    if clang -O3 -framework AppKit -framework Foundation "$SRC_DIR/easydateien_clip.m" -o "$CONFIG_DIR/easydateien_clip" 2>/dev/null; then
        chmod +x "$CONFIG_DIR/easydateien_clip"
    else
        echo "Hinweis: Clipboard-Modul nicht kompilierbar (nicht macOS?); EasyDateien nutzt den AppleScript-Fallback." >&2
        rm -f "$CONFIG_DIR/easydateien_clip"
    fi
fi

if command -v clang >/dev/null 2>&1 && [ -f "$SRC_DIR/easydateien_pdf.m" ]; then
    echo "Kompiliere natives macOS-PDF-Modul..."
    if clang -O3 -framework Foundation -framework PDFKit -framework CoreGraphics -framework ImageIO "$SRC_DIR/easydateien_pdf.m" -o "$CONFIG_DIR/easydateien_pdf" 2>/dev/null; then
        chmod +x "$CONFIG_DIR/easydateien_pdf"
    else
        echo "Hinweis: PDF-Modul nicht kompilierbar; EasyDateien nutzt pdftoppm/sips Fallback." >&2
        rm -f "$CONFIG_DIR/easydateien_pdf"
    fi
fi

# 3. Standard-Konfiguration initialisieren oder HEILEN: Eine korrupte
# config.json (z. B. halbfertig durch abgebrochene Installation) wird
# durch gueltige Standardwerte ersetzt, eine gueltige bleibt unberuehrt.
CONFIG_KAPUTT=0
if [ -f "$CONFIG_DIR/config.json" ] && command -v python3 >/dev/null 2>&1; then
    if ! python3 -c "import json; json.load(open('$CONFIG_DIR/config.json'))" 2>/dev/null; then
        CONFIG_KAPUTT=1
    fi
fi
if [ ! -f "$CONFIG_DIR/config.json" ] || [ "$CONFIG_KAPUTT" -ne 0 ]; then
    if [ "$CONFIG_KAPUTT" -ne 0 ]; then
        echo "Korrupte Konfiguration erkannt — stelle Standardwerte wieder her ..."
    else
        echo "Erstelle Standard-Konfiguration in $CONFIG_DIR/config.json..."
    fi
    if command -v python3 >/dev/null 2>&1; then
        if ! python3 -c "
import sys, json
sys.path.insert(0, '$CONFIG_DIR')
import easydateien_common
with open('$CONFIG_DIR/config.json', 'w') as f:
    json.dump(easydateien_common.DEFAULT_CONFIG, f, indent=2, ensure_ascii=False)
    f.write('
')
" 2>/dev/null; then
            echo "Hinweis: Konfiguration wird mit dokumentierten Standardwerten erstellt." >&2
            cat > "$CONFIG_DIR/config.json" <<'STANDARD_CONFIG'
{
  "esc_to_quit": false,
  "mouse_support": false,
  "show_console": false,
  "console_always_visible": true,
  "preview_wrap": true,
  "text_editor": "nano %s",
  "opener": "open %s",
  "sort_by": "name",
  "sort_reverse": true,
  "sort_dir_first": true,
  "show_hidden": false
}
STANDARD_CONFIG
        fi
    else
        echo "FEHLER: python3 wird benoetigt, um EasyDateien zu installieren." >&2
        exit 1
    fi
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

# 5. Shell-Integration für automatischen Verzeichniswechsel beim Beenden
INTEGRATION_MARKER="# EasyDateien Shell-Integration"
INTEGRATION_CODE='
# EasyDateien Shell-Integration (automatischer Verzeichniswechsel beim Beenden)
easydateien() {
    local cwd_file
    cwd_file="$(mktemp -t "easydateien-cwd.XXXXXX" 2>/dev/null || mktemp "${TMPDIR:-/tmp}/easydateien-cwd.XXXXXX")"
    command easydateien --cwd-file="$cwd_file" "$@"
    local ret=$?
    if [ -f "$cwd_file" ]; then
        local new_dir
        new_dir="$(cat "$cwd_file" 2>/dev/null)"
        rm -f "$cwd_file"
        if [ -n "$new_dir" ] && [ -d "$new_dir" ] && [ "$new_dir" != "$PWD" ]; then
            builtin cd -- "$new_dir"
        fi
    fi
    return $ret
}
alias ed="easydateien"
'

for RC_FILE in "$HOME/.zshrc" "$HOME/.bashrc"; do
    if [ -f "$RC_FILE" ]; then
        if ! grep -q "$INTEGRATION_MARKER" "$RC_FILE"; then
            echo "$INTEGRATION_CODE" >> "$RC_FILE"
            echo "Shell-Integration zu $RC_FILE hinzugefügt."
        fi
    fi
done

# ---------------------------------------------------------------- Selbst-Verifikation
# Prueft, dass die Installation vollstaendig und lauffaehig ist. Schlaegt etwas
# fehl, bricht das Skript LAUT ab, statt einen halbfertigen Zustand zu melden.
VERIFY_FILES=("easydateien" "easydateien_ui.py" "easydateien_actions.py" "easydateien_view.py" "easydateien_common.py" "easydateien_symlink.py" "easydateien_konfigurator.py")
VERIFY_FAILED=0
for DATEI in "${VERIFY_FILES[@]}"; do
    ZIEL="$CONFIG_DIR/$DATEI"
    if [ ! -f "$ZIEL" ] || [ -L "$ZIEL" ] && [ ! -e "$ZIEL" ]; then
        echo "FEHLER: $ZIEL fehlt oder ist ein toter Symlink" >&2
        VERIFY_FAILED=1
    fi
done
if command -v python3 >/dev/null 2>&1; then
    if ! python3 -m py_compile "$CONFIG_DIR/easydateien" 2>/dev/null; then
        echo "FEHLER: Hauptprogramm hat keine gueltige Python-Syntax" >&2
        VERIFY_FAILED=1
    fi
    if ! python3 -c "import sys; sys.path.insert(0, '$CONFIG_DIR'); import easydateien_ui, easydateien_actions, easydateien_view, easydateien_common, easydateien_symlink" 2>/dev/null; then
        echo "FEHLER: Programmmodule konnten nicht geladen werden (Import-Test)" >&2
        VERIFY_FAILED=1
    fi
fi
if [ ! -s "$CONFIG_DIR/config.json" ] || ! python3 -c "import json; json.load(open('$CONFIG_DIR/config.json'))" 2>/dev/null; then
    echo "FEHLER: config.json fehlt oder ist ungueltig." >&2
    VERIFY_FAILED=1
fi
if [ "$VERIFY_FAILED" -ne 0 ]; then
    echo "==============================================================================" >&2
    echo "FEHLER: Die Installation ist unvollstaendig. NICHT als erfolgreich melden." >&2
    echo "Bitte erneut ausfuehren und die Meldungen oben pruefen." >&2
    exit 1
fi

echo "=============================================================================="
echo "ERFOLG: EasyDateien wurde erfolgreich installiert!"
echo "Befehl:  easydateien (oder kurz: ed)"
echo "Menü:    Tastenkürzel 'm' oder: easydateien --config"
echo "=============================================================================="
