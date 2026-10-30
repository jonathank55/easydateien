#!/usr/bin/env python3
"""
EasyDateien Common — Gemeinsame Basis für Dateimanager und Konfigurator.

Dieses Modul ist die Single Source of Truth für alle geteilten Grundlagen:
Terminalkonstanten, visuelle Breitenberechnung, Kürzungs- und Pad-Logik,
Tastenbelegungen (Keymap) sowie Laden und Speichern der Konfiguration.
Sowohl `easydateien` als auch `easydateien_konfigurator.py` importieren
ausschließlich von hier, damit beide Programme niemals auseinanderlaufen.
"""

import os
import json
import re
import functools
import unicodedata

CONFIG_DIR = os.path.expanduser("~/.config/easydateien")
CONFIG_FILE = os.path.join(CONFIG_DIR, "config.json")

# Dynamisches, Theme-adaptives Farbschema:
# Nutzt ausschließlich SGR-Attribute (Fett, Gedimmt, Kursiv, Invertiert) und die
# semantischen ANSI-Grundfarben (31–37) des jeweiligen Terminal-Themes — ohne
# fest verdrahtete RGB-/256-Farbwerte. Passt sich dadurch jedem hellen und
# dunklen Theme in jeder Terminalapp automatisch an (respektiert NO_COLOR).
_NO_COLOR = bool(os.environ.get("NO_COLOR")) or os.environ.get("TERM") == "dumb"

C_RESET = "" if _NO_COLOR else "\033[0m"
C_BOLD = "" if _NO_COLOR else "\033[1m"
C_DIM = "" if _NO_COLOR else "\033[2m"
C_ITALIC = "" if _NO_COLOR else "\033[3m"
C_GREEN = "" if _NO_COLOR else "\033[32m"
C_BOLD_GREEN = "" if _NO_COLOR else "\033[1;32m"
C_YELLOW = "" if _NO_COLOR else "\033[33m"
C_BOLD_YELLOW = "" if _NO_COLOR else "\033[1;33m"
C_RED = "" if _NO_COLOR else "\033[31m"
C_BOLD_RED = "" if _NO_COLOR else "\033[1;31m"
C_MAGENTA = "" if _NO_COLOR else "\033[35m"
C_GRAY = C_DIM
C_INVERT = "" if _NO_COLOR else "\033[7m"

CLEAR_LINE = "\033[2K"
HIDE_CURSOR = "\033[?25l"
SHOW_CURSOR = "\033[?25h"
DISABLE_AUTOWRAP = "\033[?7l"
ENABLE_AUTOWRAP = "\033[?7h"

ANSI_ESCAPE_RE = re.compile(r"\x1b\[[0-9;]*[a-zA-Z]")
_CONTROL_CHARS_RE = re.compile(r"[\x00-\x1f\x7f-\x9f]")

DEFAULT_CONFIG = {
    "schnellstart_eintraege": [
        {"titel": "Dateien", "befehl": "easydateien"},
        {"titel": "Textdatei", "befehl": "osascript -e 'tell application \"TextEdit\"' -e 'activate' -e 'make new document' -e 'end tell' >/dev/null 2>&1"},
        {"titel": "Safari", "befehl": "open -a Safari"},
        {"titel": "iMessage", "befehl": "open -a Messages"},
        {"titel": "WhatsApp", "befehl": "open -a WhatsApp"},
        {"titel": "VPN", "untermenu": [
            {"titel": "Verbindung → DE", "befehl": "windscribe-cli connect DE"},
            {"titel": "Verbindung → Schnellste", "befehl": "windscribe-cli connect best"},
            {"titel": "Verbindung trennen", "befehl": "windscribe-cli disconnect"}
        ]}
    ],
    "esc_to_quit": False,
    "mouse_support": False,
    "show_console": False,
    "console_always_visible": True,
    "preview_wrap": True,
    "preview_media": True,
    "text_editor": "nano %s",
    "opener": "open %s",
    "sort_by": "name",
    "sort_reverse": True,
    "sort_dir_first": True,
    "show_hidden": False,
    "keybindings": None,  # Wird mit Standardwerten gefüllt, wenn nicht vorhanden
}


# --------------------------------------------------------------- Breitenlogik

@functools.lru_cache(maxsize=8192)
def char_width(c: str) -> int:
    """Ermittelt die visuelle Terminalspaltenbreite eines einzelnen Zeichens."""
    if not c or unicodedata.category(c) in ("Mn", "Me", "Cc", "Cf", "Cs"):
        return 0
    eaw = unicodedata.east_asian_width(c)
    if eaw in ("W", "F"):
        return 2
    cp = ord(c)
    if 0x1F300 <= cp <= 0x1FAFF:
        return 2
    return 1

@functools.lru_cache(maxsize=32768)
def str_width(text: str) -> int:
    """Berechnet die tatsächliche sichtbare Spaltenbreite eines Textes ohne ANSI-Codes."""
    if "\x1b" in text:
        text = ANSI_ESCAPE_RE.sub("", text)
    if text.isascii() and text.isprintable():
        return len(text)
    return sum(char_width(c) for c in text)

@functools.lru_cache(maxsize=32768)
def truncate_to_width(text: str, max_w: int, ellipsis: str = "…") -> str:
    """Kürzt Text deterministisch auf die maximale visuelle Terminalbreite unter Erhalt von ANSI-Codes."""
    if max_w <= 0:
        return ""
    if str_width(text) <= max_w:
        return text
    e_w = str_width(ellipsis)
    target_w = max(0, max_w - e_w)
    res = []
    w = 0
    i = 0
    n = len(text)
    has_ansi = False
    while i < n:
        if text[i] == "\x1b":
            m = ANSI_ESCAPE_RE.match(text, i)
            if m:
                res.append(m.group(0))
                has_ansi = True
                i = m.end()
                continue
        c = text[i]
        cw = char_width(c)
        if w + cw > target_w:
            break
        res.append(c)
        w += cw
        i += 1
    res_str = "".join(res)
    if has_ansi:
        return f"{res_str}{C_RESET}{ellipsis}"
    return f"{res_str}{ellipsis}"

def frame_cell(content: str, cell_w: int, pad: int = 1) -> str:
    """Standardisiertes Zellenrendering: exakt `pad` Leerzeichen Abstand
    zum linken und rechten Rand, Inhalt auf cell_w - 2*pad begrenzt.
    ANSI-Codes im Inhalt bleiben erhalten; die Geometrie bleibt immer exakt."""
    if cell_w <= 0:
        return ""
    inner = max(0, cell_w - 2 * pad)
    return " " * pad + pad_to_width(content, inner) + " " * pad


def cell_inner_width(cell_w: int, pad: int = 1) -> int:
    """Verfuegbare Inhaltbreite einer Zelle nach Abzug der Randabstaende."""
    return max(0, cell_w - 2 * pad)


def pad_to_width(text: str, width: int, align: str = "left") -> str:
    """Füllt formatierten Text exakt auf die gewünschte visuelle Terminalbreite auf."""
    if width <= 0:
        return ""
    w = str_width(text)
    if w > width:
        clean = ANSI_ESCAPE_RE.sub("", text)
        text = truncate_to_width(clean, width)
        w = str_width(text)
    pad = " " * max(0, width - w)
    return (pad + text) if align == "right" else (text + pad)

@functools.lru_cache(maxsize=8192)
def safe_text(text: str) -> str:
    """Ersetzt Steuerzeichen in Dateinamen, damit sie das Layout nie zerstören können."""
    return _CONTROL_CHARS_RE.sub("?", text)

def distribute_options(items, avail_w: int) -> str:
    """Verteilt Steuerungsoptionen gleichmäßig über die gegebene Breite (Space-Between / Justified)."""
    if not items or avail_w <= 0:
        return ""
    clean_items = [it.strip() for it in items if it and it.strip()]
    if not clean_items:
        return ""
    if len(clean_items) == 1:
        it = clean_items[0]
        it_w = str_width(it)
        if it_w > avail_w:
            return truncate_to_width(it, avail_w)
        return it

    total_items_w = sum(str_width(it) for it in clean_items)
    num_gaps = len(clean_items) - 1

    if total_items_w + num_gaps > avail_w:
        combined = " ".join(clean_items)
        if str_width(combined) <= avail_w:
            return combined
        return truncate_to_width(combined, avail_w)

    remaining_spaces = avail_w - total_items_w
    base_gap = remaining_spaces // num_gaps
    extra = remaining_spaces % num_gaps

    parts = []
    for i, it in enumerate(clean_items):
        parts.append(it)
        if i < num_gaps:
            gap_len = base_gap + (1 if i < extra else 0)
            parts.append(" " * gap_len)

    return "".join(parts)

def fit_hints(items, avail_w: int, ellipsis: bool = True) -> str:
    """Passt Hilfeeinträge maximal dynamisch in die Breite.

    items: Liste aus str oder (voll, kurz, mini)-Tupeln in Prioritätsreihenfolge.
    Reihenfolge der Strategien: alle Einträge in Volltext → kurz → mini; reicht der Platz
    nicht, fallen die letzten Einträge weg und ein „…“ signalisiert die Auslassung.
    """
    if avail_w <= 0 or not items:
        return ""
    norm = []
    for it in items:
        if isinstance(it, (tuple, list)):
            variants = [v for v in it if v]
            while len(variants) < 3:
                variants.append(variants[-1])
            norm.append(tuple(variants[:3]))
        else:
            norm.append((it, it, it))
    for n in range(len(norm), 0, -1):
        for v in range(3):
            cand = [norm[i][v] for i in range(n)]
            if n < len(norm) and ellipsis:
                cand.append("…")
            gap = 2 if v < 2 else 1
            if sum(str_width(c) for c in cand) + gap * (len(cand) - 1) <= avail_w:
                return distribute_options(cand, avail_w)
    return truncate_to_width(norm[0][2], avail_w)


# ------------------------------------------------------------ Tastenbelegungen

# Zentrale Tastenbelegung (Single Source of Truth): Jede Zeile besteht aus
# (Abschnitt, Aktions-ID, Anzeige, Tasten-Tokens, Beschreibung).
# Der Dateimanager leitet daraus seinen Dispatch ab (Doppelbelegungen werden beim
# Start abgelehnt); Hilfemenü (h) und Konfigurator zeigen exakt dieselbe Tabelle.
KEY_BINDINGS = [
    ("Navigation & Ansicht", "up", "Nach oben", ("UP",), "Cursor nach oben bewegen"),
    ("Navigation & Ansicht", "down", "Nach unten", ("DOWN",), "Cursor nach unten bewegen"),
    ("Navigation & Ansicht", "left", "Zurück", ("LEFT",), "Übergeordneten Ordner öffnen"),
    ("Navigation & Ansicht", "right", "Öffnen", ("RIGHT",), "Ordner betreten"),
    ("Navigation & Ansicht", "page_up", "Seite hoch", ("PAGE_UP",), "10 Einträge nach oben blättern"),
    ("Navigation & Ansicht", "page_down", "Seite runter", ("PAGE_DOWN",), "10 Einträge nach unten blättern"),
    ("Navigation & Ansicht", "top", "Anfang", ("j",), "Zum Anfang der Liste springen"),
    ("Navigation & Ansicht", "bottom", "Ende", ("k",), "Zum Ende der Liste springen"),
    ("Navigation & Ansicht", "open", "Auswählen", ("ENTER",), "Mit Standardprogramm öffnen"),
    ("Navigation & Ansicht", "goto", "Gehe zu", ("g",), "Gehe zu (Schnellzugriff auf Ordner)"),
    ("Navigation & Ansicht", "mark_dir", "Merken", ("-",), "Aktuellen Ordner merken (g- springt zurück)"),
    ("Navigation & Ansicht", "schnellstart", "Schnellstart", ("i",), "Schnellstartmenü öffnen"),
    ("Navigation & Ansicht", "home", "Start", ("~",), "Zum Benutzerordner springen"),
    ("Navigation & Ansicht", "search", "Suchen", ("/",), "Dateien nach Suchbegriff filtern"),
    ("Navigation & Ansicht", "hidden", "Versteckt", (".",), "Versteckte Dateien ein-/ausblenden"),
    ("Navigation & Ansicht", "sort", "Sortieren", ("s",), "Sortierung wechseln"),
    ("Navigation & Ansicht", "console", "Konsole", ("t",), "Integrierte Konsole öffnen/schließen"),
    ("Navigation & Ansicht", "console_focus", "Fokus", ("TAB",), "Fokus auf die Konsole setzen"),
    ("Dateioperationen", "select", "Markieren", ("SPACE",), "Element markieren/Markierung aufheben"),
    ("Dateioperationen", "select_all", "Alle", ("a",), "Alle sichtbaren Elemente markieren"),
    ("Dateioperationen", "new", "Neu", ("n",), "Neue Datei oder Ordner (mit / am Ende)"),
    ("Dateioperationen", "rename", "Umbenennen", ("r",), "Element umbenennen"),
    ("Dateioperationen", "trash", "Löschen", ("DELETE", "BACKSPACE"), "In den Papierkorb verschieben"),
    ("Dateioperationen", "copy", "Kopieren", ("c",), "Kopiermenü öffnen (Auswahl, Pfad, Name, Ordnerpfad)"),
    ("Dateioperationen", "symlink", "Verknüpfung", ("v",), "Verknüpfung auf Auswahl/Eintrag erstellen"),
    ("Dateioperationen", "cut", "Ausschneiden", ("x",), "Auswahl ausschneiden"),
    ("Dateioperationen", "paste", "Einfügen", ("p",), "In aktuellen Ordner einfügen"),
    ("Dateioperationen", "zip", "Zip", ("z",), "ZIP-Archiv aus Auswahl erstellen"),
    ("Dateioperationen", "extract", "Entpacken", ("e",), "ZIP-Archiv entpacken"),
    ("Dateioperationen", "edit", "Bearbeiten", ("o",), "Im Editor bearbeiten"),
    ("Dateioperationen", "undo", "Rückgängig", ("u",), "Letzte Dateiaktion rückgängig machen"),
    ("Verwaltung", "help", "Hilfe", ("h",), "Diese Hilfe anzeigen"),
    ("Verwaltung", "menu", "Menü", ("m",), "Einstellungen öffnen (u. a. Texteditor)"),
    ("Verwaltung", "cancel", "Abbrechen", ("ESC",), "Konsole schließen, Filter aufheben, Auswahl leeren"),
    ("Verwaltung", "cancel_cmd", "Abbrechen (Eingabe)", ("CTRL_C",), "Konsoleneingabe leeren, interaktive Befehle beenden"),
    ("Verwaltung", "quit", "Beenden", ("q",), "EasyDateien beenden"),
]

# Anzeigenamen für Tasten-Tokens im Hilfemenü
KEY_LABELS = {
    "UP": "\u2191",
    "DOWN": "\u2193",
    "LEFT": "\u2190",
    "RIGHT": "\u2192",
    "ENTER": "Eingabe",
    "SPACE": "Leertaste",
    "TAB": "Tab",
    "ESC": "ESC",
    "CTRL_C": "Strg C",
    "PAGE_UP": "Bild\u2191",
    "PAGE_DOWN": "Bild\u2193",
    "DELETE": "Entfernen",
    "INSERT": "Einfg",
    "SHIFT_TAB": "Umschalt Tab",
}


def format_keys(tokens) -> str:
    """Formatiert Tasten-Tokens f\u00fcr die Anzeige im Hilfemen\u00fc."""
    parts = []
    for t in tokens:
        if t in KEY_LABELS:
            parts.append(KEY_LABELS[t])
        else:
            parts.append(t)
    return " / ".join(parts)


def key_display(cfg_or_keymap, action: str, default: str = "") -> str:
    """Liefert das Anzeigelabel der Taste einer Aktion aus der keymap
    (Single Source of Truth des Konfigurators) — mit deutschem Label.
    cfg kann eine Config (dict) oder eine fertige keymap sein; Aktionen mit
    mehreren Tasten zeigen die erste."""
    if isinstance(cfg_or_keymap, dict):
        keymap = cfg_or_keymap if cfg_or_keymap and all(
            isinstance(v, str) for v in cfg_or_keymap.values()
        ) and any(a in cfg_or_keymap.values() for a in (action,)) else None
        if keymap is None:
            try:
                keymap = build_keymap(cfg_or_keymap)
            except Exception:
                keymap = {}
    else:
        keymap = {}
    token = None
    for k, a in keymap.items():
        if a == action:
            token = k
            break
    if token is None:
        return default
    return KEY_LABELS.get(token, token)


def build_help_items(bindings) -> list:
    """Erzeugt die Hilfemen\u00fc-Zeilen dynamisch aus den aktuellen Tastenbelegungen."""
    items = []
    current_section = None
    rows = []
    for section, action, disp, keys, desc in bindings:
        if section != current_section:
            if current_section is not None:
                rows.append(None)
            rows.append((section, None))
            current_section = section
        rows.append((format_keys(keys), desc))
    key_w = max((str_width(k) for k, d in (r for r in rows if r is not None) if d is not None), default=0)
    for row in rows:
        if row is None:
            items.append("")
        else:
            k, d = row
            if d is None:
                items.append(k)
            else:
                pad = " " * (key_w - str_width(k) + 1)
                items.append(f"  [{k}]{pad}{d}")
    return items


def get_keybindings_from_config(cfg: dict) -> list:
    """Lädt die Tastenbelegungen aus der Konfiguration oder verwendet Standardwerte."""
    custom_bindings = cfg.get("keybindings")
    if custom_bindings is None:
        return KEY_BINDINGS
    # Gespeicherte Belegungen: Tasten bleiben individuell, aber Abschnitt,
    # Anzeigename und Beschreibung werden stets vom aktuellen Codestand
    # aufgefrischt (sonst würden alte Beschreibungstexte im Hilfemenü
    # eingefroren). Nicht mehr existierende Aktionen fallen weg.
    defaults_by_action = {b[1]: b for b in KEY_BINDINGS}
    # Drei Schutzschichten gegen Tastenkonflikte, automatisch bei jedem Laden:
    # 1. Unbekannte Aktionen fallen weg (nur im Code existierende sind gueltig).
    # 2. Tasten, die im aktuellen Standard einer ANDEREN Aktion gehoeren,
    #    gibt die gespeicherte Belegung ab.
    # 3. Verbleibende individuelle Tasten bleiben; Doppelbelegungen sind
    #    danach ausgeschlossen.
    reserved = {}
    for b in KEY_BINDINGS:
        for k in b[3]:
            reserved.setdefault(k, b[1])
    result = []
    for item in custom_bindings:
        if isinstance(item, list):
            section, action, disp, keys, desc = item
            keys = tuple(keys) if isinstance(keys, list) else keys
        else:
            section, action, disp, keys, desc = item
        cur = defaults_by_action.get(action)
        if cur is None:
            continue
        # Ungueltige Token (leer, Nicht-Strings, Whitespace) entfernen:
        # Sie entstanden durch fruehere Fehler beim Tastenerkennen und
        # wuerden sonst jede Validierung sperren.
        keys = tuple(k.strip() for k in keys
                     if isinstance(k, str) and k.strip()
                     and k.strip() not in ("UNBEKANNT", "resize")
                     and all(c.isprintable() for c in k))
        cleaned = tuple(k for k in keys if reserved.get(k, action) == action)
        result.append((cur[0], action, cur[2], cleaned or cur[3], cur[4]))
    # Aktionen, die nur im aktuellen Code existieren, ergänzen. Sie werden
    # an der Position ihres Abschnitts einsortiert, damit jeder Abschnitt im
    # Hilfemenü genau einmal erscheint (sonst entstünde bei einer älteren
    # gespeicherten Konfiguration ein zweiter Abschnitt gleichen Namens am Ende).
    known = {b[1] for b in result}
    for b in KEY_BINDINGS:
        if b[1] in known:
            continue
        # Position des Abschnitts: nach dem letzten bekannten Eintrag desselben
        # Abschnitts, sonst ans Ende.
        insert_at = len(result)
        for i in range(len(result) - 1, -1, -1):
            if result[i][0] == b[0]:
                insert_at = i + 1
                break
        result.insert(insert_at, b)
    return result

def build_keymap(cfg: dict = None) -> dict:
    """Erzeugt die Zuordnung Taste → Aktions-ID und lehnt Doppelbelegungen strikt ab."""
    bindings = get_keybindings_from_config(cfg) if cfg else KEY_BINDINGS
    keymap = {}
    for _section, action, _disp, keys, _desc in bindings:
        for k in keys:
            if k in keymap:
                raise ValueError(f"Tastenkonflikt: '{k}' ist doppelt belegt ({keymap[k]} / {action})")
            keymap[k] = action
    return keymap


# ------------------------------------------------------------------ Konfiguration

def load_config() -> dict:
    """Lädt die Konfiguration und ergänzt fehlende Schlüssel mit Standardwerten."""
    cfg = dict(DEFAULT_CONFIG)
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                cfg.update(json.load(f))
        except Exception:
            pass
    return cfg

def save_config(cfg: dict):
    """Speichert die Konfiguration deterministisch und lesbar."""
    os.makedirs(CONFIG_DIR, exist_ok=True)
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2, ensure_ascii=False)
        f.write("\n")
