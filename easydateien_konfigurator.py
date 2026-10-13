#!/usr/bin/env python3
"""
EasyDateien Konfigurator — Interaktive Konfigurations-Engine für EasyDateien.
Single-Source-of-Truth & optimi-Norm konform.
"""

import os
import sys
import json
import termios
import tty
import select
import shutil
import argparse
import unicodedata
import re
from functools import lru_cache

CONFIG_DIR = os.path.expanduser("~/.config/easydateien")
CONFIG_FILE = os.path.join(CONFIG_DIR, "config.json")

# Farbcodes - Farben deaktiviert, nur Formatierungen (Fett, Kursiv, Invertiert) beibehalten
C_RESET = "\033[0m"
C_BOLD = "\033[1m"
C_DIM = "\033[2m"
C_ITALIC = "\033[3m"
C_BLUE = ""
C_BOLD_BLUE = ""
C_CYAN = ""
C_BOLD_CYAN = ""
C_GREEN = ""
C_BOLD_GREEN = ""
C_YELLOW = ""
C_RED = ""
C_BOLD_RED = ""
C_MAGENTA = ""
C_GRAY = ""
C_INVERT = "\033[7m"

DISABLE_AUTOWRAP = "\033[?7l"
ENABLE_AUTOWRAP = "\033[?7h"

ANSI_ESCAPE_RE = re.compile(r"\x1b\[[0-9;]*[a-zA-Z]")

DEFAULT_CONFIG = {
    "divider_style": "alle",
    "columns_enabled": True,
    "esc_to_quit": False,
    "mouse_support": False,
    "show_console": False,
    "console_position": "unten",
    "console_always_visible": True,
    "console_dynamic_height": True,
    "preview_wrap": True,
    "text_editor": "nano %s",
    "opener": "open %s",
    "sort_by": "name",
    "sort_reverse": True,
    "sort_dir_first": True,
    "show_hidden": False,
    "keybindings": None,
}

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
    ("Dateioperationen", "trash", "Löschen", ("d",), "In den Papierkorb verschieben"),
    ("Dateioperationen", "copy", "Kopieren", ("c",), "Auswahl kopieren"),
    ("Dateioperationen", "cut", "Ausschneiden", ("x",), "Auswahl ausschneiden"),
    ("Dateioperationen", "paste", "Einfügen", ("p",), "In aktuellen Ordner einfügen"),
    ("Dateioperationen", "copy_path", "Pfad", ("c",), "Kopieren: cc Pfad · cf Name · cd Ordnerpfad"),
    ("Dateioperationen", "zip", "Zip", ("z",), "ZIP-Archiv aus Auswahl erstellen"),
    ("Dateioperationen", "extract", "Entpacken", ("e",), "ZIP-Archiv entpacken"),
    ("Dateioperationen", "edit", "Bearbeiten", ("o",), "Im Editor bearbeiten"),
    ("Dateioperationen", "undo", "Rückgängig", ("u",), "Letzte Dateiaktion rückgängig machen"),
    ("Verwaltung", "help", "Hilfe", ("h",), "Diese Hilfe anzeigen"),
    ("Verwaltung", "menu", "Menü", ("m",), "Einstellungen öffnen (u. a. Texteditor)"),
    ("Verwaltung", "cancel", "Abbrechen", ("ESC", "CTRL_C"), "Konsole schließen, Filter/Auswahl aufheben"),
    ("Verwaltung", "quit", "Beenden", ("q",), "EasyDateien beenden"),
]

CHORD_ACTIONS = {
    "copy_path": ("c", ("cc", "cf", "cd")),
}

# Cache für ANSI-Escape-Code-Entfernung
@lru_cache(maxsize=1024)
def strip_ansi(text: str) -> str:
    return ANSI_ESCAPE_RE.sub("", text)

# Cache für String-Breitenberechnung
@lru_cache(maxsize=1024)
def str_width(text: str) -> int:
    clean = strip_ansi(text)
    return sum(char_width(c) for c in clean)

def char_width(c: str) -> int:
    if not c or unicodedata.category(c) in ("Mn", "Me", "Cc", "Cf", "Cs"):
        return 0
    eaw = unicodedata.east_asian_width(c)
    if eaw in ("W", "F"):
        return 2
    cp = ord(c)
    if (0x1F300 <= cp <= 0x1FAFF) or (0x2600 <= cp <= 0x27BF) or (0xFE00 <= cp <= 0xFE0F):
        return 2
    return 1

def truncate_to_width(text: str, max_w: int, ellipsis: str = "…") -> str:
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

def pad_to_width(text: str, width: int, align: str = "left") -> str:
    w = str_width(text)
    if w > width:
        clean = strip_ansi(text)
        return truncate_to_width(clean, width)
    pad = " " * (width - w)
    return (pad + text) if align == "right" else (text + pad)

# Cache für distribute_options
@lru_cache(maxsize=64)
def distribute_options_cached(items: tuple, avail_w: int) -> str:
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

def distribute_options(items: list, avail_w: int) -> str:
    return distribute_options_cached(tuple(items), avail_w)

def fit_hints(items: list, avail_w: int) -> str:
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
            if n < len(norm):
                cand.append("…")
            gap = 2 if v < 2 else 1
            if sum(str_width(c) for c in cand) + gap * (len(cand) - 1) <= avail_w:
                return distribute_options(cand, avail_w)
    return truncate_to_width(norm[0][2], avail_w)

def get_keybindings_from_config(cfg: dict) -> list:
    """Lädt die Tastenbelegungen aus der Konfiguration oder verwendet Standardwerte."""
    custom_bindings = cfg.get("keybindings")
    if custom_bindings is None:
        return KEY_BINDINGS
    result = []
    for item in custom_bindings:
        if isinstance(item, list):
            section, action, disp, keys, desc = item
            result.append((section, action, disp, tuple(keys) if isinstance(keys, list) else keys, desc))
        else:
            result.append(item)
    return result

def build_keymap(cfg: dict = None) -> dict:
    """Erzeugt die Zuordnung Taste → Aktions-ID und lehnt Doppelbelegungen strikt ab."""
    bindings = get_keybindings_from_config(cfg) if cfg else KEY_BINDINGS
    keymap = {}
    for _section, action, _disp, keys, _desc in bindings:
        chord = CHORD_ACTIONS.get(action)
        if chord and chord[0] in keys:
            eff_keys = tuple(k for k in keys if k != chord[0]) + chord[1]
        else:
            eff_keys = keys
        for k in eff_keys:
            if k in keymap:
                raise ValueError(f"Tastenkonflikt: '{k}' ist doppelt belegt ({keymap[k]} / {action})")
            keymap[k] = action
    return keymap

KEYBINDING_ITEMS = [(action, desc, f"[{disp}]") for _s, action, disp, _k, desc in KEY_BINDINGS] + [
    ("reset", "Auf Standardwerte zurücksetzen", "[standard]"),
]

MAIN_MENU_ITEMS = [
    ("divider", "Trennungslinien", "alle"),
    ("columns", "Spalten-Layout", "ein"),
    ("mouse", "Mausunterstützung", "ein"),
    ("hidden", "Versteckte Dateien anzeigen", "aus"),
    ("console_always_visible", "Konsole immer eingeblendet", "aus"),
    ("console_dynamic_height", "Dynamische Konsolenhöhe", "ein"),
    ("console_position", "Konsolenposition", "unten"),
    ("preview_wrap", "Vorschau-Umbruch", "ein"),
    ("sort", "Datei- und Ordneranordnung", "öffnen"),
    ("editor", "Editor", "nano"),
    ("keybindings", "Tastenbelegungen", "öffnen"),
    ("reset", "Auf Standardwerte zurücksetzen", "standard"),
]

EDITOR_CHOICES = ["nano", "vim", "nvim", "micro", "hx", "emacs -nw"]

def editor_command(cfg: dict) -> str:
    """Liefert den konfigurierten Editor ohne %s-Platzhalter (z. B. 'nano')."""
    tmpl = str(cfg.get("text_editor", "nano %s") or "nano %s")
    cmd = tmpl.replace("%s", "").strip()
    return cmd or "nano"

def cycle_editor(cfg: dict, step: int = 1) -> str:
    """Schaltet den Texteditor in der Konfiguration um und liefert den neuen Befehl."""
    cur = editor_command(cfg)
    choices = list(EDITOR_CHOICES)
    if cur not in choices:
        choices.insert(0, cur)
    nxt = choices[(choices.index(cur) + step) % len(choices)]
    cfg["text_editor"] = f"{nxt} %s"
    return nxt

def load_config() -> dict:
    cfg = dict(DEFAULT_CONFIG)
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                cfg.update(json.load(f))
        except Exception:
            pass
    return cfg

def save_config(cfg: dict):
    os.makedirs(CONFIG_DIR, exist_ok=True)
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2, ensure_ascii=False)
        f.write("\n")

def read_key(fd: int, timeout: float = 0.05) -> str:
    try:
        r, _, _ = select.select([fd], [], [], timeout)
        if not r:
            return ""
        raw = os.read(fd, 1)
        if not raw:
            return ""
        if raw == b"\x1b":
            seq = b""
            while True:
                r2, _, _ = select.select([fd], [], [], 0.05)
                if not r2:
                    break
                c = os.read(fd, 1)
                if not c:
                    break
                seq += c
                if seq.startswith(b"[<"):
                    if seq.endswith(b"M") or seq.endswith(b"m") or len(seq) >= 30:
                        break
                elif len(seq) >= 2 and seq[-1:] in b"ABCDHFS~":
                    break
                elif len(seq) >= 6:
                    break
            if not seq:
                return "ESC"
            if seq.startswith(b"[<") and (seq.endswith(b"M") or seq.endswith(b"m")):
                try:
                    is_rel = seq.endswith(b"m")
                    b_s, x_s, y_s = seq[2:-1].decode("ascii").split(";")
                    b_c = int(b_s)
                    if b_c == 64:
                        return "WHEEL_UP"
                    elif b_c == 65:
                        return "WHEEL_DOWN"
                    elif not is_rel and b_c == 0:
                        return f"CLICK:{int(x_s)}:{int(y_s)}"
                except Exception:
                    pass
                return "MOUSE"
            mapping = {
                b"[A": "UP", b"[B": "DOWN", b"[C": "RIGHT", b"[D": "LEFT",
                b"OA": "UP", b"OB": "DOWN", b"OC": "RIGHT", b"OD": "LEFT",
                b"[H": "HOME", b"[F": "END", b"OH": "HOME", b"OF": "END",
                b"[5~": "PAGE_UP", b"[6~": "PAGE_DOWN"
            }
            return mapping.get(seq, "")
        if raw in (bytes([13]), bytes([10])):
            return "ENTER"
        elif raw == b" ":
            return "SPACE"
        elif raw == b"\t":
            return "TAB"
        elif raw in (bytes([3]), bytes([4])):
            return "QUIT"
        try:
            return raw.decode("utf-8")
        except Exception:
            return ""
    except Exception:
        return ""

# Globale Variable für partielles Rendering
_last_render_state = {
    "start": 0,
    "count": 0,
    "rows": [],
    "cur_idx": 0,
    "term_cols": 0,
    "term_rows": 0
}

def render_box(title: str, subtitle: str, rows: list, cur_idx: int, footer: str):
    term_cols, term_rows = shutil.get_terminal_size((80, 24))
    inner = max(4, term_cols - 2)
    fixed_h = 7
    avail_rows = max(1, term_rows - fixed_h)

    # Prüfe, ob sich nur die Auswahl geändert hat (partielles Rendering)
    if (_last_render_state["rows"] == rows and
        _last_render_state["cur_idx"] != cur_idx and
        _last_render_state["term_cols"] == term_cols and
        _last_render_state["term_rows"] == term_rows):

        # Nur die alte und neue Auswahl neu zeichnen
        old_idx = _last_render_state["cur_idx"]
        start = _last_render_state["start"]
        count = _last_render_state["count"]

        # Alte Auswahl zurücksetzen
        if 0 <= old_idx - start < count:
            i = old_idx - start
            key, label, tag = rows[old_idx]
            pfx = "  "
            avail_lbl = max(2, inner - 4 - str_width(tag) - 2)
            lbl_trunc = truncate_to_width(label, avail_lbl)
            pad_len = max(1, inner - 2 - str_width(pfx) - str_width(lbl_trunc) - str_width(tag))
            content_row = f" {pfx}{lbl_trunc}{' ' * pad_len}{tag} "
            sys.stdout.write(f"\033[{5 + i};1H\033[2K│{pad_to_width(content_row, inner)}│")

        # Neue Auswahl zeichnen
        if 0 <= cur_idx - start < count:
            i = cur_idx - start
            key, label, tag = rows[cur_idx]
            pfx = f"{C_BOLD}▸{C_RESET} "
            if tag in ("[Ein]", "Ein"):
                tag_colored = f"{C_BOLD}{tag}{C_RESET}"
            elif tag in ("[Aus]", "Aus"):
                tag_colored = tag
            else:
                tag_colored = tag
            avail_lbl = max(2, inner - 4 - str_width(tag) - 2)
            lbl_trunc = truncate_to_width(label, avail_lbl)
            lbl_styled = f"{C_BOLD}{lbl_trunc}{C_RESET}"
            pad_len = max(1, inner - 2 - str_width(pfx) - str_width(lbl_trunc) - str_width(tag))
            content_row = f" {pfx}{lbl_styled}{' ' * pad_len}{tag_colored} "
            sys.stdout.write(f"\033[{5 + i};1H\033[2K│{pad_to_width(content_row, inner)}│")
            sys.stdout.flush()

        _last_render_state.update({
            "cur_idx": cur_idx,
            "rows": rows,
            "term_cols": term_cols,
            "term_rows": term_rows
        })
        return start, count

    # Vollständiges Rendering (falls sich Layout oder Inhalt geändert hat)
    if len(rows) > avail_rows:
        start = max(0, min(cur_idx - avail_rows // 2, len(rows) - avail_rows))
        view_rows = rows[start: start + avail_rows]
    else:
        start = 0
        view_rows = rows

    lines = []
    lines.append(f"╭{'─' * inner}╮")
    t_styled = f"{C_BOLD}{truncate_to_width(title, inner - 4)}{C_RESET}"
    lines.append(f"│  {pad_to_width(t_styled, inner - 2)}│")
    s_styled = truncate_to_width(subtitle, inner - 4)
    lines.append(f"│  {pad_to_width(s_styled, inner - 2)}│")
    lines.append(f"├{'─' * inner}┤")

    for i, (key, label, tag) in enumerate(view_rows):
        is_sel = (start + i == cur_idx)
        pfx = f"{C_BOLD}▸{C_RESET} " if is_sel else "  "

        if tag in ("[Ein]", "Ein"):
            tag_colored = f"{C_BOLD}{tag}{C_RESET}"
        elif tag in ("[Aus]", "Aus"):
            tag_colored = tag
        else:
            tag_colored = tag

        avail_lbl = max(2, inner - 4 - str_width(tag) - 2)
        lbl_trunc = truncate_to_width(label, avail_lbl)
        lbl_styled = f"{C_BOLD}{lbl_trunc}{C_RESET}" if is_sel else lbl_trunc
        pad_len = max(1, inner - 2 - str_width(pfx) - str_width(lbl_trunc) - str_width(tag))
        content_row = f" {pfx}{lbl_styled}{' ' * pad_len}{tag_colored} "
        lines.append(f"│{pad_to_width(content_row, inner)}│")

    empty_needed = avail_rows - len(view_rows)
    for _ in range(empty_needed):
        lines.append(f"│{' ' * inner}│")

    lines.append(f"├{'─' * inner}┤")
    avail_f_w = max(1, inner - 4)
    if isinstance(footer, (list, tuple)):
        f_styled = fit_hints(list(footer), avail_f_w)
    elif footer:
        f_styled = truncate_to_width(footer, avail_f_w)
    else:
        f_styled = ""
    lines.append(f"│  {pad_to_width(f_styled, inner - 2)}│")
    lines.append(f"╰{'─' * inner}╯")

    out = []
    for r_i, l in enumerate(lines[:term_rows]):
        out.append(f"\033[{r_i+1};1H\033[2K{l}")
    sys.stdout.write("".join(out))
    sys.stdout.flush()

    _last_render_state.update({
        "start": start,
        "count": len(view_rows),
        "rows": rows,
        "cur_idx": cur_idx,
        "term_cols": term_cols,
        "term_rows": term_rows
    })
    return start, len(view_rows)

def edit_keybindings_menu(fd: int):
    """Interaktives Menü zum Anpassen der Tastenbelegungen."""
    cfg = load_config()

    current_bindings = get_keybindings_from_config(cfg)
    editable_bindings = list(current_bindings)

    def save_editable_bindings():
        json_bindings = []
        for section, action, disp, keys, desc in editable_bindings:
            json_bindings.append([section, action, disp, list(keys), desc])
        cfg["keybindings"] = json_bindings
        save_config(cfg)

    idx = 0
    status_hint = ""

    while True:
        binding_rows = []
        for section, action, disp, keys, desc in editable_bindings:
            keys_str = ", ".join(keys)
            binding_rows.append((action, f"{section}: {disp}", f"[{keys_str}]"))

        binding_rows.append(("reset", "Auf Standard zurücksetzen", "[Zurücksetzen]"))
        binding_rows.append(("back", "Zurück", "[ESC]"))

        footer_text = status_hint if status_hint else [
            ("[↑↓] Navigieren", "[↑↓] Nav", "[↑↓]"),
            ("[Eingabe] Bearbeiten", "[Eingabe] Ändern", "[Eingabe]"),
            ("[ESC] Zurück", "[ESC] Zurück", "[ESC]")
        ]

        start, count = render_box(
            "TASTENBELEGUNGEN ANPASSEN",
            "Tastenbelegungen für jede Aktion ändern",
            binding_rows,
            idx,
            footer_text
        )

        status_hint = ""
        k = read_key(fd)
        if not k:
            continue

        if k in ("UP", "WHEEL_UP"):
            idx = max(0, idx - 1)
        elif k in ("DOWN", "WHEEL_DOWN"):
            idx = min(len(binding_rows) - 1, idx + 1)
        elif k in ("PAGE_UP",):
            idx = max(0, idx - 8)
        elif k in ("PAGE_DOWN",):
            idx = min(len(binding_rows) - 1, idx + 8)
        elif k in ("ESC", "q"):
            save_editable_bindings()
            break
        elif k.startswith("CLICK:"):
            try:
                _, cx_s, cy_s = k.split(":")
                row_i = int(cy_s) - 5
                if 0 <= row_i < count:
                    idx = start + row_i
            except Exception:
                pass
            continue

        if k in ("ENTER", "SPACE", "RIGHT"):
            selected_action = binding_rows[idx][0]

            if selected_action == "reset":
                editable_bindings = list(KEY_BINDINGS)
                status_hint = f"{C_BOLD}✓ Tastenbelegungen zurückgesetzt{C_RESET}"

            elif selected_action == "back":
                save_editable_bindings()
                break

            else:
                for i, (section, action, disp, keys, desc) in enumerate(editable_bindings):
                    if action == selected_action:
                        render_box(
                            f"TASTEN FÜR '{disp}' ÄNDERN",
                            "Drücken Sie die neue Taste oder Tastenkombination (ESC zum Abbrechen)",
                            [],
                            0,
                            [("Aktuell:", ", ".join(keys), "")]
                        )

                        new_key = ""
                        while True:
                            key_press = read_key(fd)
                            if key_press == "ESC":
                                break
                            elif key_press:
                                new_key = key_press
                                break

                        if new_key:
                            editable_bindings[i] = (section, action, disp, [new_key], desc)
                            status_hint = f"{C_BOLD}✓ '{disp}' auf [{new_key}] gesetzt{C_RESET}"
                        break

def sort_menu(fd: int):
    cfg = load_config()
    idx = 0
    status_hint = ""

    sort_options = [
        ("name", "Name (alphabetisch)", "Nach Dateinamen sortieren"),
        ("mtime", "Änderungsdatum", "Nach Modifikationszeit sortieren"),
        ("atime", "Zugiffsdatum", "Nach Zugiffszeit sortieren"),
        ("size", "Größe", "Nach Dateigröße sortieren"),
        ("ext", "Endung", "Nach Dateiendung sortieren"),
    ]

    while True:
        current_sort = cfg.get("sort_by", "mtime")
        reverse_state = "normal" if cfg.get("sort_reverse", False) else "umgekehrt"
        dir_first_state = "ordner zuerst" if cfg.get("sort_dir_first", True) else "gemischt"

        sort_rows = []
        for key, lbl, _ in sort_options:
            marker = "* " if key == current_sort else "  "
            sort_rows.append((key, f"{marker}{lbl}", ""))

        sort_rows.append(("reverse", f"  Sortierreihenfolge: [{reverse_state}]", ""))
        sort_rows.append(("dir_first", f"  Ordnerposition: [{dir_first_state}]", ""))

        footer_text = status_hint if status_hint else [
            ("[↑↓] Navigieren", "[↑↓] Nav", "[↑↓]"),
            ("[Eingabe] Auswählen", "[Eingabe] Ändern", "[Eingabe]"),
            ("[ESC] Zurück", "[ESC] Zurück", "[ESC]")
        ]

        start, count = render_box(
            "DATEI- UND ORDNERANORDNUNG",
            "Sortierung und Anzeigereihenfolge festlegen",
            [(r[0], r[1], r[2]) for r in sort_rows],
            idx,
            footer_text
        )

        status_hint = ""
        k = read_key(fd)
        if not k:
            continue

        if k in ("UP", "WHEEL_UP"):
            idx = max(0, idx - 1)
        elif k in ("DOWN", "WHEEL_DOWN"):
            idx = min(len(sort_rows) - 1, idx + 1)
        elif k in ("PAGE_UP",):
            idx = max(0, idx - 8)
        elif k in ("PAGE_DOWN",):
            idx = min(len(sort_rows) - 1, idx + 8)
        elif k in ("ESC", "q", "LEFT"):
            break
        elif k.startswith("CLICK:"):
            try:
                _, cx_s, cy_s = k.split(":")
                row_i = int(cy_s) - 5
                if 0 <= row_i < count:
                    idx = start + row_i
            except Exception:
                pass
            continue

        if k in ("ENTER", "SPACE", "RIGHT"):
            selected_key = sort_rows[idx][0]
            if selected_key in [s[0] for s in sort_options]:
                cfg["sort_by"] = selected_key
                save_config(cfg)
                status_hint = f"{C_BOLD}✓ Sortierung nach {sort_rows[idx][1].split('] ')[-1]}{C_RESET}"
            elif selected_key == "reverse":
                cfg["sort_reverse"] = not cfg.get("sort_reverse", True)
                save_config(cfg)
            elif selected_key == "dir_first":
                cfg["sort_dir_first"] = not cfg.get("sort_dir_first", True)
                save_config(cfg)

def keybindings_menu(fd: int):
    idx = 0
    while True:
        start, count = render_box(
            "TASTENBELEGUNGEN",
            "Übersicht aller Tastenkombinationen und Befehle",
            KEYBINDING_ITEMS,
            idx,
            [("[↑↓] Navigieren", "[↑↓] Nav", "[↑↓]"), ("[ESC / q] Zurück", "[ESC] Zurück", "[ESC]")]
        )
        k = read_key(fd)
        if not k:
            continue
        if k in ("UP", "k", "WHEEL_UP"):
            idx = max(0, idx - 1)
        elif k in ("DOWN", "j", "WHEEL_DOWN"):
            idx = min(len(KEYBINDING_ITEMS) - 1, idx + 1)
        elif k in ("PAGE_UP",):
            idx = max(0, idx - 8)
        elif k in ("PAGE_DOWN",):
            idx = min(len(KEYBINDING_ITEMS) - 1, idx + 8)
        elif k in ("ESC", "q", "LEFT"):
            break
        elif k.startswith("CLICK:"):
            try:
                _, cx_s, cy_s = k.split(":")
                row_i = int(cy_s) - 5
                if 0 <= row_i < count:
                    idx = start + row_i
            except Exception:
                pass
            continue
        if k in ("ENTER", "SPACE"):
            act = KEYBINDING_ITEMS[idx][0]
            if act == "reset":
                save_config(dict(DEFAULT_CONFIG))
                break

def main_menu(fd: int):
    cfg = load_config()
    idx = 0
    status_hint = ""
    while True:
        rows = []
        for key, lbl, _ in MAIN_MENU_ITEMS:
            if key == "divider":
                val = f"[{cfg.get('divider_style', 'alle')}]"
            elif key == "columns":
                val = f"[{'ein' if cfg.get('columns_enabled', True) else 'aus'}]"
            elif key == "mouse":
                val = f"[{'ein' if cfg.get('mouse_support', True) else 'aus'}]"
            elif key == "hidden":
                val = f"[{'ein' if cfg.get('show_hidden', False) else 'aus'}]"
            elif key == "console_always_visible":
                val = f"[{'ein' if cfg.get('console_always_visible', False) else 'aus'}]"
            elif key == "console_dynamic_height":
                val = f"[{'ein' if cfg.get('console_dynamic_height', True) else 'aus'}]"
            elif key == "console_position":
                val = f"[{cfg.get('console_position', 'unten')}]"
            elif key == "preview_wrap":
                val = f"[{'ein' if cfg.get('preview_wrap', True) else 'aus'}]"
            elif key == "sort":
                val = "[öffnen]"
            elif key == "editor":
                val = f"[{editor_command(cfg)}]"
            elif key == "keybindings":
                val = "[öffnen]"
            elif key == "reset":
                val = "[standard]"
            else:
                val = ""
            rows.append((key, lbl, val))

        footer_text = status_hint if status_hint else [
            ("[↑↓] Navigieren", "[↑↓] Nav", "[↑↓]"),
            ("[Eingabe / ←→] Ändern", "[Eingabe] Ändern", "[Eingabe]"),
            ("[ESC] Zurück", "[ESC]", "[ESC]"),
            ("[q] Beenden", "[q]", "[q]"),
        ]
        start, count = render_box(
            "EASYDATEIEN KONFIGURATION",
            "Einstellungen verwalten und anpassen",
            rows,
            idx,
            footer_text
        )
        status_hint = ""
        k = read_key(fd)
        if not k:
            continue
        if k in ("UP", "WHEEL_UP"):
            idx = max(0, idx - 1)
        elif k in ("DOWN", "WHEEL_DOWN"):
            idx = min(len(rows) - 1, idx + 1)
        elif k in ("ESC", "q"):
            break
        elif k.startswith("CLICK:"):
            try:
                _, cx_s, cy_s = k.split(":")
                row_i = int(cy_s) - 5
                if 0 <= row_i < count:
                    idx = start + row_i
            except Exception:
                pass
            continue

        if k in ("ENTER", "SPACE", "RIGHT", "LEFT"):
            act = rows[idx][0]
            if act == "divider":
                opts = ["alle", "vertikal", "horizontal", "außen", "keine"]
                cur = cfg.get("divider_style", "alle")
                cur_i = opts.index(cur) if cur in opts else 0
                step = -1 if k == "LEFT" else 1
                cfg["divider_style"] = opts[(cur_i + step) % len(opts)]
                save_config(cfg)
            elif act == "columns":
                cfg["columns_enabled"] = not cfg.get("columns_enabled", True)
                save_config(cfg)
            elif act == "mouse":
                cfg["mouse_support"] = not cfg.get("mouse_support", True)
                save_config(cfg)
            elif act == "hidden":
                cfg["show_hidden"] = not cfg.get("show_hidden", False)
                save_config(cfg)
            elif act == "console_always_visible":
                cfg["console_always_visible"] = not cfg.get("console_always_visible", False)
                save_config(cfg)
            elif act == "console_dynamic_height":
                cfg["console_dynamic_height"] = not cfg.get("console_dynamic_height", True)
                save_config(cfg)
            elif act == "console_position":
                opts = ["unten", "rechts", "links"]
                cur = cfg.get("console_position", "unten")
                cur_i = opts.index(cur) if cur in opts else 0
                step = -1 if k == "LEFT" else 1
                cfg["console_position"] = opts[(cur_i + step) % len(opts)]
                save_config(cfg)
            elif act == "preview_wrap":
                cfg["preview_wrap"] = not cfg.get("preview_wrap", True)
                save_config(cfg)
            elif act == "editor":
                cycle_editor(cfg, -1 if k == "LEFT" else 1)
                save_config(cfg)
            elif act == "sort":
                if k == "LEFT":
                    break
                else:
                    sort_menu(fd)
                    cfg = load_config()
            elif act == "keybindings":
                if k == "LEFT":
                    break
                else:
                    edit_keybindings_menu(fd)
                    cfg = load_config()
            elif act == "reset":
                if k != "LEFT":
                    render_box(
                        "ZURÜCKSETZEN BESTÄTIGEN",
                        "Möchten Sie wirklich alle Einstellungen auf Standard zurücksetzen?",
                        [],
                        0,
                        [("[y] Ja, zurücksetzen", "[y] Ja", "[y]"), ("[n] Nein, abbrechen", "[n] Nein", "[n]")]
                    )
                    k2 = ""
                    while not k2:
                        k2 = read_key(fd)
                    if k2 in ("y", "Y"):
                        cfg = dict(DEFAULT_CONFIG)
                        save_config(cfg)
                        status_hint = f"{C_BOLD}✓ Auf Standardwerte zurückgesetzt{C_RESET}"
                    else:
                        status_hint = "Zurücksetzen abgebrochen"
    return cfg

def run_konfigurator(standalone: bool = True):
    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    tty.setcbreak(fd, termios.TCSADRAIN)
    if standalone:
        sys.stdout.write("\033[?1049h\033[?25l" + DISABLE_AUTOWRAP + "\033[?1000h\033[?1006h\033[2J\033[3J\033[H")
        sys.stdout.flush()
    else:
        sys.stdout.write(DISABLE_AUTOWRAP)
        sys.stdout.flush()
    try:
        cfg = main_menu(fd)
        return cfg
    finally:
        if standalone:
            sys.stdout.write("\033[?1006l\033[?1000l\033[?25h" + ENABLE_AUTOWRAP + "\033[?1049l")
            sys.stdout.flush()
            termios.tcsetattr(fd, termios.TCSADRAIN, old)
        else:
            sys.stdout.write(ENABLE_AUTOWRAP)
            sys.stdout.flush()

class SingleLineHelpFormatter(argparse.HelpFormatter):
    def _split_lines(self, text, width):
        return [text]

def main():
    parser = argparse.ArgumentParser(
        prog="easydateien-config",
        formatter_class=lambda prog: SingleLineHelpFormatter(prog, max_help_position=16, width=220),
        description="Interaktives Konfigurationsmenü für EasyDateien.",
        add_help=False
    )
    parser.add_argument("-h", action="help", help="Hilfe anzeigen")
    parser.parse_args()
    run_konfigurator(standalone=True)

if __name__ == "__main__":
    main()
