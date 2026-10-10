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

# Farbcodes nach optimi-Farbnorm
C_RESET = "\033[0m"
C_BOLD = "\033[1m"
C_DIM = "\033[2m"
C_ITALIC = "\033[3m"
C_BLUE = "\033[0;34m"
C_BOLD_BLUE = "\033[1;34m"
C_CYAN = "\033[0;36m"
C_BOLD_CYAN = "\033[1;36m"
C_GREEN = "\033[0;32m"
C_BOLD_GREEN = "\033[1;32m"
C_YELLOW = "\033[1;33m"
C_RED = "\033[0;31m"
C_BOLD_RED = "\033[1;31m"
C_MAGENTA = "\033[0;35m"
C_GRAY = "\033[90m"
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

KEYBINDING_ITEMS = [
    ("up", "Cursor nach oben bewegen", "[↑]"),
    ("down", "Cursor nach unten bewegen", "[↓]"),
    ("left", "Übergeordnetes Verzeichnis öffnen", "[←]"),
    ("right", "Ordner betreten", "[→]"),
    ("page_up", "Seite nach oben blättern", "[Bild↑]"),
    ("page_down", "Seite nach unten blättern", "[Bild↓]"),
    ("open", "Systemweit mit Standardprogramm öffnen", "[Eingabe]"),
    ("nano", "In Nano bearbeiten", "[e]"),
    ("vim", "In Vim bearbeiten", "[o]"),
    ("new", "Neue Datei oder neuen Ordner anlegen", "[n]"),
    ("search", "Such- und Schnellfilter aktivieren", "[/]"),
    ("sort", "Sortierkriterium umschalten", "[s]"),
    ("select", "Auswahl des Elements umschalten", "[Leertaste]"),
    ("select_all", "Alle sichtbaren Elemente auswählen", "[a]"),
    ("rename", "Element umbenennen", "[r]"),
    ("undo", "Letzte Dateiaktion rückgängig machen", "[u]"),
    ("zip", "ZIP-Archiv aus Auswahl erstellen", "[z]"),
    ("cut", "Auswahl zum Ausschneiden vormerken", "[x]"),
    ("copy", "Auswahl in macOS-Zwischenablage kopieren", "[y]"),
    ("paste", "Zwischenablage im Ordner einfügen", "[p]"),
    ("copy_path", "Dateipfad in Zwischenablage kopieren", "[c]"),
    ("trash", "In den Papierkorb verschieben", "[d]"),
    ("toggle_hidden", "Versteckte Dateien ein- oder ausblenden", "[.]"),
    ("menu", "Konfigurationsmenü öffnen", "[m]"),
    ("goto", "Gehe-zu-Menü öffnen", "[g]"),
    ("home", "Direkt zum Benutzerordner wechseln", "[~]"),
    ("toggle_console", "Integrierte Konsole umschalten", "[t]"),
    ("quit", "EasyDateien beenden", "[q]"),
    ("reset", "Auf Standardwerte zurücksetzen", "[Standard]"),
]

MAIN_MENU_ITEMS = [
    ("divider", "Trennungslinien-Stil", "alle"),
    ("columns", "3-Spalten-Layout", "Ein"),
    ("mouse", "Mausunterstützung", "Ein"),
    ("console", "Terminal-Konsole", "Aus"),
    ("hidden", "Versteckte Dateien anzeigen", "Aus"),
    ("keybindings", "Tastenbelegungen ansehen", "Öffnen"),
    ("reset", "Auf Standardwerte zurücksetzen", "Standard"),
]


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
    if max_w <= 0:
        return ""
    if str_width(text) <= max_w:
        return text
    e_w = str_width(ellipsis)
    if max_w <= e_w:
        res = ""
        w = 0
        for c in text:
            cw = char_width(c)
            if w + cw > max_w:
                break
            res += c
            w += cw
        return res
    target_w = max_w - e_w
    res = ""
    w = 0
    for c in text:
        cw = char_width(c)
        if w + cw > target_w:
            break
        res += c
        w += cw
    return res + ellipsis


def pad_to_width(text: str, width: int, align: str = "left") -> str:
    w = str_width(text)
    if w > width:
        clean = ANSI_ESCAPE_RE.sub("", text)
        return truncate_to_width(clean, width)
    pad = " " * (width - w)
    return (pad + text) if align == "right" else (text + pad)


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

    b_c = C_BLUE
    lines = []
    lines.append(f"{b_c}╭{'─' * inner}╮{C_RESET}")
    t_styled = f"{C_BOLD_BLUE}{truncate_to_width(title, inner - 4)}{C_RESET}"
    lines.append(f"{b_c}│{C_RESET}  {pad_to_width(t_styled, inner - 2)}{b_c}│{C_RESET}")
    s_styled = f"{C_GRAY}{truncate_to_width(subtitle, inner - 4)}{C_RESET}"
    lines.append(f"{b_c}│{C_RESET}  {pad_to_width(s_styled, inner - 2)}{b_c}│{C_RESET}")
    lines.append(f"{b_c}├{'─' * inner}┤{C_RESET}")

    for i, (key, label, tag) in enumerate(view_rows):
        actual_idx = start + i
        is_sel = (actual_idx == cur_idx)
        pfx = f"{C_BOLD_BLUE}▸{C_RESET} " if is_sel else "  "

        if tag in ("[Ein]", "Ein"):
            tag_colored = f"{C_BOLD_GREEN}{tag}{C_RESET}"
        elif tag in ("[Aus]", "Aus"):
            tag_colored = f"{C_GRAY}{tag}{C_RESET}"
        elif tag:
            tag_colored = f"{C_BOLD_CYAN}{tag}{C_RESET}"
        else:
            tag_colored = ""

        avail_lbl = max(2, inner - 4 - str_width(tag) - 2)
        lbl_trunc = truncate_to_width(label, avail_lbl)
        lbl_styled = f"{C_BOLD}{lbl_trunc}{C_RESET}" if is_sel else lbl_trunc
        pad_len = max(1, inner - 2 - str_width(pfx) - str_width(lbl_trunc) - str_width(tag))
        content_row = f" {pfx}{lbl_styled}{' ' * pad_len}{tag_colored} "
        lines.append(f"{b_c}│{C_RESET}{pad_to_width(content_row, inner)}{b_c}│{C_RESET}")

    empty_needed = avail_rows - len(view_rows)
    for _ in range(empty_needed):
        lines.append(f"{b_c}│{C_RESET}{' ' * inner}{b_c}│{C_RESET}")

    lines.append(f"{b_c}├{'─' * inner}┤{C_RESET}")
    f_styled = f"{C_GRAY}{truncate_to_width(footer, inner - 4)}{C_RESET}"
    lines.append(f"{b_c}│{C_RESET}  {pad_to_width(f_styled, inner - 2)}{b_c}│{C_RESET}")
    lines.append(f"{b_c}╰{'─' * inner}╯{C_RESET}")

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
            "[←↑↓→] Navigieren  [ESC / q] Schließen"
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
            elif key == "console":
                val = f"[{'Ein' if cfg.get('show_console', False) else 'Aus'}]"
            elif key == "hidden":
                val = f"[{'Ein' if cfg.get('show_hidden', False) else 'Aus'}]"
            elif key == "keybindings":
                val = "[Öffnen]"
            elif key == "reset":
                val = "[Standard]"
            else:
                val = ""
            rows.append((key, lbl, val))

        footer_text = status_hint if status_hint else "[←↑↓→] Navigieren  [Eingabe] Ändern  [ESC / q] Beenden"
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

        if k in ("ENTER", "SPACE", "RIGHT"):
            act = rows[idx][0]
            if act == "divider":
                opts = ["alle", "vertikal", "horizontal", "außen", "keine"]
                cur = cfg.get("divider_style", "alle")
                cfg["divider_style"] = opts[(opts.index(cur) + 1) % len(opts)] if cur in opts else "alle"
                save_config(cfg)
            elif act == "columns":
                cfg["columns_enabled"] = not cfg.get("columns_enabled", True)
                save_config(cfg)
            elif act == "mouse":
                cfg["mouse_support"] = not cfg.get("mouse_support", True)
                save_config(cfg)
            elif act == "console":
                cfg["show_console"] = not cfg.get("show_console", False)
                save_config(cfg)
            elif act == "hidden":
                cfg["show_hidden"] = not cfg.get("show_hidden", False)
                save_config(cfg)
            elif act == "keybindings":
                keybindings_menu(fd)
                cfg = load_config()
            elif act == "reset":
                cfg = dict(DEFAULT_CONFIG)
                save_config(cfg)
                status_hint = f"{C_BOLD_GREEN}✓ Auf Standardwerte zurückgesetzt{C_RESET}"
    return cfg


def run_konfigurator(standalone: bool = True):
    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    tty.setcbreak(fd, termios.TCSADRAIN)
    if standalone:
        sys.stdout.write("\033[?1049h\033[?25l" + DISABLE_AUTOWRAP + "\033[?1000h\033[?1006h\033[2J\033[H")
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
        else:
            sys.stdout.write(ENABLE_AUTOWRAP)
            sys.stdout.flush()
        termios.tcsetattr(fd, termios.TCSADRAIN, old)


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
