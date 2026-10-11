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
    "mouse_support": True,
    "show_console": False,
    "console_position": "unten",
    "text_editor": "nano %s",
    "opener": "open %s",
    "sort_by": "mtime",
    "sort_reverse": True,
    "sort_dir_first": True,
    "show_hidden": False,
}

# Zentrale Tastenbelegung (Single Source of Truth): Jede Zeile besteht aus
# (Abschnitt, Aktions-ID, Anzeige, Tasten-Tokens, Beschreibung).
# Der Dateimanager leitet daraus seinen Dispatch ab (Doppelbelegungen werden beim
# Start abgelehnt); Hilfemenü (h) und Konfigurator zeigen exakt dieselbe Tabelle.
KEY_BINDINGS = [
    ("Navigation & Ansicht", "up", "↑ k", ("UP", "k"), "Cursor nach oben bewegen"),
    ("Navigation & Ansicht", "down", "↓ j", ("DOWN", "j"), "Cursor nach unten bewegen"),
    ("Navigation & Ansicht", "left", "←", ("LEFT",), "Übergeordneten Ordner öffnen"),
    ("Navigation & Ansicht", "right", "→ l", ("RIGHT", "l"), "Ordner betreten"),
    ("Navigation & Ansicht", "page_up", "Bild↑", ("PAGE_UP",), "10 Einträge nach oben blättern"),
    ("Navigation & Ansicht", "page_down", "Bild↓", ("PAGE_DOWN",), "10 Einträge nach unten blättern"),
    ("Navigation & Ansicht", "top", "Pos1", ("HOME",), "Zum Anfang der Liste springen"),
    ("Navigation & Ansicht", "bottom", "Ende G", ("END", "G"), "Zum Ende der Liste springen"),
    ("Navigation & Ansicht", "open", "Eingabe", ("ENTER",), "Mit Standardprogramm öffnen"),
    ("Navigation & Ansicht", "goto", "g", ("g",), "Gehe zu (Schnellzugriff auf Ordner)"),
    ("Navigation & Ansicht", "home", "~", ("~",), "Zum Benutzerordner springen"),
    ("Navigation & Ansicht", "search", "/", ("/",), "Dateien nach Suchbegriff filtern"),
    ("Navigation & Ansicht", "hidden", ".", (".",), "Versteckte Dateien ein-/ausblenden"),
    ("Navigation & Ansicht", "sort", "s", ("s",), "Sortierung wechseln"),
    ("Navigation & Ansicht", "console", "t", ("t",), "Integrierte Konsole öffnen/schließen"),
    ("Navigation & Ansicht", "console_focus", "Tab", ("TAB", "SHIFT_TAB"), "Fokus auf die Konsole setzen"),
    ("Navigation & Ansicht", "shell", "!", ("!", "$"), "Interaktive Shell im Ordner öffnen"),
    ("Dateioperationen", "select", "Leertaste v", ("SPACE", " ", "v"), "Element markieren/Markierung aufheben"),
    ("Dateioperationen", "select_all", "a", ("a",), "Alle sichtbaren Elemente markieren"),
    ("Dateioperationen", "new", "n", ("n",), "Neue Datei oder Ordner (mit / am Ende)"),
    ("Dateioperationen", "rename", "r", ("r",), "Element umbenennen"),
    ("Dateioperationen", "trash", "d Entf", ("d", "DELETE"), "In den Papierkorb verschieben"),
    ("Dateioperationen", "copy", "y", ("y",), "Auswahl kopieren"),
    ("Dateioperationen", "cut", "x", ("x",), "Auswahl ausschneiden"),
    ("Dateioperationen", "paste", "p", ("p",), "In aktuellen Ordner einfügen"),
    ("Dateioperationen", "clear_clipboard", "X Y", ("X", "Y"), "Zwischenspeicher leeren"),
    ("Dateioperationen", "copy_path", "c", ("c",), "Kopieren: cc Pfad · cf Name · cd Ordnerpfad"),
    ("Dateioperationen", "zip", "z", ("z",), "ZIP-Archiv aus Auswahl erstellen"),
    ("Dateioperationen", "extract", "e", ("e",), "ZIP-Archiv entpacken"),
    ("Dateioperationen", "edit", "o", ("o",), "Im Editor bearbeiten"),
    ("Dateioperationen", "undo", "u Strg+Z", ("u", "UNDO"), "Letzte Dateiaktion rückgängig machen"),
    ("Verwaltung", "help", "h ?", ("h", "?"), "Diese Hilfe anzeigen"),
    ("Verwaltung", "menu", "m", ("m",), "Einstellungen öffnen (u. a. Texteditor)"),
    ("Verwaltung", "cancel", "ESC Strg+C", ("ESC", "CTRL_C"), "Konsole schließen, Filter/Auswahl aufheben"),
    ("Verwaltung", "quit", "q", ("q",), "EasyDateien beenden"),
]


def build_keymap() -> dict:
    """Erzeugt die Zuordnung Taste → Aktions-ID und lehnt Doppelbelegungen strikt ab."""
    keymap = {}
    for _section, action, _disp, keys, _desc in KEY_BINDINGS:
        for k in keys:
            if k in keymap:
                raise ValueError(f"Tastenkonflikt: '{k}' ist doppelt belegt ({keymap[k]} / {action})")
            keymap[k] = action
    return keymap


KEYBINDING_ITEMS = [(action, desc, f"[{disp}]") for _s, action, disp, _k, desc in KEY_BINDINGS] + [
    ("reset", "Auf Standardwerte zurücksetzen", "[Standard]"),
]

MAIN_MENU_ITEMS = [
    ("divider", "Trennungslinien-Stil", "alle"),
    ("columns", "Spalten-Layout", "Ein"),
    ("mouse", "Mausunterstützung", "Ein"),
    ("hidden", "Versteckte Dateien anzeigen", "Aus"),
    ("editor", "Texteditor", "nano"),
    ("keybindings", "Tastenbelegungen ansehen", "Öffnen"),
    ("reset", "Auf Standardwerte zurücksetzen", "Standard"),
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

def str_width(text: str) -> int:
    clean = ANSI_ESCAPE_RE.sub("", text)
    return sum(char_width(c) for c in clean)

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

def pad_to_width(text: str, width: int, align: str = "left") -> str:
    w = str_width(text)
    if w > width:
        clean = ANSI_ESCAPE_RE.sub("", text)
        return truncate_to_width(clean, width)
    pad = " " * (width - w)
    return (pad + text) if align == "right" else (text + pad)

def distribute_options(items: list, avail_w: int) -> str:
    """Verteilt Optionen gleichmäßig über die gegebene Spaltenbreite."""
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

def fit_hints(items: list, avail_w: int) -> str:
    """Passt Hilfe-Einträge maximal dynamisch in die Breite.

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
            if n < len(norm):
                cand.append("…")
            gap = 2 if v < 2 else 1
            if sum(str_width(c) for c in cand) + gap * (len(cand) - 1) <= avail_w:
                return distribute_options(cand, avail_w)
    return truncate_to_width(norm[0][2], avail_w)

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

def render_box(title: str, subtitle: str, rows: list, cur_idx: int, footer: str):
    term_cols, term_rows = shutil.get_terminal_size((80, 24))
    inner = max(4, term_cols - 2)
    fixed_h = 7
    avail_rows = max(1, term_rows - fixed_h)

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
        actual_idx = start + i
        is_sel = (actual_idx == cur_idx)
        pfx = f"{C_BOLD}▸{C_RESET} " if is_sel else "  "

        if tag in ("[Ein]", "Ein"):
            tag_colored = f"{C_BOLD}{tag}{C_RESET}"
        elif tag in ("[Aus]", "Aus"):
            tag_colored = tag
        elif tag:
            tag_colored = tag
        else:
            tag_colored = ""

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
    return start, len(view_rows)

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
                val = f"[{'Ein' if cfg.get('columns_enabled', True) else 'Aus'}]"
            elif key == "mouse":
                val = f"[{'Ein' if cfg.get('mouse_support', True) else 'Aus'}]"
            elif key == "hidden":
                val = f"[{'Ein' if cfg.get('show_hidden', False) else 'Aus'}]"
            elif key == "editor":
                val = f"[{editor_command(cfg)}]"
            elif key == "keybindings":
                val = "[Öffnen]"
            elif key == "reset":
                val = "[Standard]"
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
        if k in ("UP", "k", "WHEEL_UP"):
            idx = max(0, idx - 1)
        elif k in ("DOWN", "j", "WHEEL_DOWN"):
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
            elif act == "editor":
                cycle_editor(cfg, -1 if k == "LEFT" else 1)
                save_config(cfg)
            elif act == "keybindings":
                if k == "LEFT":
                    break
                else:
                    keybindings_menu(fd)
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
