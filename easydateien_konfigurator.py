#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
easydateien_konfigurator.py
===========================
Interaktiver Konfigurator für EasyDateien.
Ermöglicht das bequeme Verwalten aller Einstellungen, Sortierkriterien
und Tastenbelegungen mit flüssiger Pfeiltastennavigation im SCHNELLSTART-Design.
"""

import os
import sys
import json
import shutil
import select
import termios
import tty
import subprocess
import argparse
import re

CONFIG_DIR = os.path.expanduser("~/.config/easydateien")
CONFIG_FILE = os.environ.get("EASYDATEIEN_CONFIG", os.path.join(CONFIG_DIR, "config.json"))
BACKUP_ENGINE = os.path.expanduser("~/.gemini/config/scripts/file_backup_engine.py")

# Monochrome Formatierung nach Systemnorm (keine ANSI-Farben)
BOLD = "\033[1m"
ITALIC = "\033[3m"
RESET = "\033[0m"
HIDE_CURSOR = "\033[?25l"
SHOW_CURSOR = "\033[?25h"
CLEAR_LINE = "\033[2K"

ANSI_ESCAPE_RE = re.compile(r"\x1b\[[0-9;]*[a-zA-Z]")


def visible_len(text: str) -> int:
    """Berechnet die reale sichtbare Zeichenbreite ohne ANSI-Steuersequenzen."""
    return len(ANSI_ESCAPE_RE.sub("", text))


def truncate_end(text: str, max_w: int) -> str:
    """Kürzt einen Text deterministisch am Ende mit '...' ab, falls er max_w überschreitet."""
    if max_w <= 0:
        return ""
    if len(text) <= max_w:
        return text
    if max_w <= 3:
        return text[:max_w]
    return text[: max_w - 3] + "..."


def pad_visible(text: str, width: int, align: str = "left") -> str:
    """Füllt einen String unter Berücksichtigung von ANSI-Steuerzeichen passgenau auf."""
    vlen = visible_len(text)
    if vlen > width:
        plain = ANSI_ESCAPE_RE.sub("", text)
        return truncate_end(plain, width)
    pad = " " * (width - vlen)
    if align == "right":
        return pad + text
    return text + pad


DEFAULT_KEYMAP = {
    "up": ["UP", "k"],
    "down": ["DOWN", "j"],
    "left": ["LEFT", "h"],
    "right": ["RIGHT", "l"],
    "open": ["ENTER"],
    "select": ["SPACE", "v"],
    "select_all": ["V", "a"],
    "cut": ["x"],
    "copy": ["c"],
    "paste": ["p"],
    "trash": ["d"],
    "toggle_hidden": [".", "z"],
    "config_menu": ["m", "C"],
    "goto_downloads": ["gd"],
    "goto_documents": ["gf"],
    "goto_home": ["gh", "~"],
    "goto_interactive": ["gi"],
    "goto_clipboard": ["gp"],
    "zip": ["cz"],
    "quit": ["q"],
}

ACTION_NAMES = {
    "up": "Cursor nach oben bewegen",
    "down": "Cursor nach unten bewegen",
    "left": "Übergeordnetes Verzeichnis (Zurück)",
    "right": "Ordner öffnen (bei Datei: Doppel-→ für nano)",
    "open": "Systemweit öffnen (open, Finder für Ordner)",
    "select": "Element auswählen / abwählen (*)",
    "select_all": "Alle Elemente auswählen / abwählen",
    "cut": "Auswahl ausschneiden (×)",
    "copy": "Auswahl kopieren (+)",
    "paste": "Zwischenspeicher einfügen (p)",
    "trash": "In den Papierkorb verschieben (d)",
    "toggle_hidden": "Versteckte Dateien umschalten (./z)",
    "config_menu": "Konfigurationsmenü öffnen (m)",
    "goto_downloads": "Gehe zu Downloads (g d)",
    "goto_documents": "Gehe zu Dokumente (g f)",
    "goto_home": "Gehe zu Home-Verzeichnis (g h / ~)",
    "goto_interactive": "Pfad manuell eingeben (g i)",
    "goto_clipboard": "Gehe zu Pfad in Zwischenablage (g p)",
    "zip": "ZIP-Archiv erstellen (c z)",
    "quit": "EasyDateien beenden (q)",
}


def get_default_config() -> dict:
    """Gibt die Standardkonfiguration exakt nach der bestehenden Yazi-Konfiguration zurück."""
    return {
        "sort_by": "mtime",
        "sort_reverse": True,
        "sort_dir_first": True,
        "show_hidden": False,
        "preview": False,
        "columns_enabled": True,
        "divider_style": "vertikal",
        "show_controls": True,
        "esc_to_quit": False,
        "mouse_support": True,
        "text_editor": "nano %s",
        "opener": "open %s",
        "edit_opener": "open -e %s",
        "finder_opener": "open -R %s",
        "keybindings": dict(DEFAULT_KEYMAP),
    }


def safe_backup_file(filepath: str) -> str:
    """Erstellt ein atomares Vorab-Backup über file_backup_engine.py."""
    if not os.path.exists(filepath):
        return ""
    if os.path.exists(BACKUP_ENGINE):
        try:
            res = subprocess.run(
                [sys.executable, BACKUP_ENGINE, filepath],
                capture_output=True,
                text=True,
                timeout=5,
            )
            for line in res.stdout.splitlines():
                if "Backup erstellt:" in line:
                    return line.split("Backup erstellt:", 1)[1].strip()
        except Exception:
            pass
    return ""


def load_config(filepath: str = CONFIG_FILE) -> dict:
    """Lädt die Konfiguration aus config.json und füllt fehlende Felder mit Standardwerten auf."""
    defaults = get_default_config()
    if not os.path.isfile(filepath):
        return defaults
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            user_cfg = json.load(f)
        cfg = dict(defaults)
        cfg.update(user_cfg)
        kb = dict(defaults["keybindings"])
        if "keybindings" in user_cfg and isinstance(user_cfg["keybindings"], dict):
            kb.update(user_cfg["keybindings"])
        cfg["keybindings"] = kb
        return cfg
    except Exception:
        return defaults


def save_config(config: dict, filepath: str = CONFIG_FILE) -> bool:
    """Speichert die Konfiguration sicher in der JSON-Datei."""
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    safe_backup_file(filepath)
    try:
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        print(f"Fehler beim Speichern der Konfiguration: {e}", file=sys.stderr)
        return False


def get_divider(char: str = "─", width: int | None = None) -> str:
    """Gibt eine horizontale Trennlinie dynamisch angepasst an die gegebene Breite zurück."""
    if width is None:
        try:
            width = shutil.get_terminal_size((75, 20)).columns
        except Exception:
            width = 75
    return char * max(1, width)


def read_key(fd: int, timeout: float = 0.05) -> str:
    """Liest einen einzelnen Tastendruck oder ein Maus-Event ungepuffert direkt aus dem Filedeskriptor."""
    try:
        r, _, _ = select.select([fd], [], [], timeout)
        if not r:
            return ""
        raw = os.read(fd, 1)
    except Exception:
        return ""
    if not raw:
        return ""

    if raw == b"\x1b":
        seq = b""
        while True:
            r, _, _ = select.select([fd], [], [], 0.03)
            if not r:
                break
            try:
                c = os.read(fd, 1)
                seq += c
            except Exception:
                break

            # SGR-Maus-Sequenz: \x1b[<B;X;Y(M|m)
            if seq.startswith(b"[<"):
                if seq.endswith(b"M") or seq.endswith(b"m") or len(seq) >= 30:
                    break
            elif len(seq) >= 2 and seq[-1:] in b"ABCDHFS~":
                break
            elif len(seq) >= 6:
                break

        if not seq:
            return "ESC"

        # SGR-Maus-Event verarbeiten
        if seq.startswith(b"[<") and (seq.endswith(b"M") or seq.endswith(b"m")):
            try:
                state = chr(seq[-1])
                parts = seq[2:-1].decode("ascii").split(";")
                if len(parts) == 3:
                    btn = int(parts[0])
                    x = int(parts[1])
                    y = int(parts[2])
                    if btn == 64:
                        return "MOUSE_WHEEL_UP"
                    elif btn == 65:
                        return "MOUSE_WHEEL_DOWN"
                    elif btn == 0 and state == "M":
                        return f"MOUSE_CLICK:{x}:{y}"
                    elif btn == 2 and state == "M":
                        return f"MOUSE_RIGHT_CLICK:{x}:{y}"
                    else:
                        return f"MOUSE_EVENT:{btn}:{x}:{y}:{state}"
            except Exception:
                return "ESC"
            return ""

        if seq in (b"[A", b"OA"):
            return "UP"
        elif seq in (b"[B", b"OB"):
            return "DOWN"
        elif seq in (b"[C", b"OC"):
            return "RIGHT"
        elif seq in (b"[D", b"OD"):
            return "LEFT"
        elif seq in (b"[Z",):
            return "UP"
        elif seq in (b"[H", b"1~", b"7~"):
            return "HOME"
        elif seq in (b"[F", b"4~", b"8~"):
            return "END"
        elif seq in (b"[3~",):
            return "DELETE"
        elif seq in (b"[5~",):
            return "PAGE_UP"
        elif seq in (b"[6~",):
            return "PAGE_DOWN"
        return "ESC"

    elif raw in (b"\r", b"\n"):
        return "ENTER"
    elif raw == b" ":
        return "SPACE"
    elif raw == b"\t":
        return "TAB"
    elif raw in (b"\x7f", b"\x08"):
        return "BACKSPACE"
    elif raw in (b"\x03", b"\x04"):
        return "QUIT"

    if raw[0] >= 0xC0:
        needed = 2 if raw[0] < 0xE0 else (3 if raw[0] < 0xF0 else 4)
        ch_bytes = raw
        while len(ch_bytes) < needed:
            r, _, _ = select.select([fd], [], [], 0.03)
            if not r:
                break
            ch_bytes += os.read(fd, 1)
        try:
            return ch_bytes.decode("utf-8")
        except Exception:
            return ""

    try:
        ch = raw.decode("utf-8")
        return ch
    except Exception:
        return ""


def wait_for_key(prompt_text: str = "Beliebige Taste drücken, um fortzufahren..."):
    """Pausiert kurz und wartet auf einen einzelnen Tastendruck."""
    if not sys.stdin.isatty():
        return
    print(f"\n  {prompt_text}")
    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    try:
        tty.setcbreak(fd, termios.TCSADRAIN)
        read_key(fd, timeout=10.0)
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)


def edit_line_interactive(prompt: str, initial: str = "") -> str | None:
    """Interaktives einzeiliges Eingabefeld mit Pfeiltasten und Bearbeitungsmöglichkeit."""
    if not sys.stdin.isatty() or not sys.stdout.isatty():
        try:
            val = input(prompt).strip()
            return val if val else initial
        except Exception:
            return None

    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)
    tty.setcbreak(fd, termios.TCSADRAIN)
    sys.stdout.write(SHOW_CURSOR)
    sys.stdout.flush()

    buf = list(initial)
    pos = len(buf)

    def redraw():
        text = "".join(buf)
        sys.stdout.write("\r\033[2K" + prompt + text)
        shift_back = len(buf) - pos
        if shift_back > 0:
            sys.stdout.write(f"\033[{shift_back}D")
        sys.stdout.flush()

    redraw()
    try:
        while True:
            raw = os.read(fd, 1)
            if not raw:
                break
            if raw == b"\x1b":
                seq = b""
                while True:
                    r, _, _ = select.select([fd], [], [], 0.05)
                    if not r:
                        break
                    seq += os.read(fd, 1)
                    if len(seq) >= 4 or (len(seq) >= 2 and seq[-1:] in b"ABCDHFS~"):
                        break
                if not seq:
                    sys.stdout.write("\n")
                    return None
                if seq in (b"[A", b"OA"):
                    pos = 0
                    redraw()
                elif seq in (b"[B", b"OB"):
                    pos = len(buf)
                    redraw()
                elif seq in (b"[C", b"OC"):
                    if pos < len(buf):
                        pos += 1
                        redraw()
                elif seq in (b"[D", b"OD"):
                    if pos > 0:
                        pos -= 1
                        redraw()
                elif seq in (b"[H", b"1~", b"7~"):
                    pos = 0
                    redraw()
                elif seq in (b"[F", b"4~", b"8~"):
                    pos = len(buf)
                    redraw()
                elif seq in (b"[3~",):
                    if pos < len(buf):
                        buf.pop(pos)
                        redraw()
            elif raw in (b"\r", b"\n"):
                sys.stdout.write("\n")
                sys.stdout.flush()
                return "".join(buf)
            elif raw in (b"\x7f", b"\x08"):
                if pos > 0:
                    buf.pop(pos - 1)
                    pos -= 1
                    redraw()
            elif raw in (b"\x03", b"\x04"):
                sys.stdout.write("\n")
                return None
            else:
                ch_bytes = raw
                if raw[0] >= 0xC0:
                    needed = 2 if raw[0] < 0xE0 else (3 if raw[0] < 0xF0 else 4)
                    while len(ch_bytes) < needed:
                        ch_bytes += os.read(fd, 1)
                try:
                    ch = ch_bytes.decode("utf-8")
                    if ch.isprintable():
                        buf.insert(pos, ch)
                        pos += 1
                        redraw()
                except Exception:
                    pass
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)


def select_menu_interactive(
    title: str,
    options: list[str],
    default_idx: int = 0,
    subtitle: str | None = None,
    preserve_screen: bool = False,
) -> int | None:
    """Interaktives Auswahldialogmenü mit flüssiger Pfeiltasten- und Mausnavigation im Yazi-Box-Design."""
    total = len(options)
    if total == 0:
        return None

    if not sys.stdin.isatty() or not sys.stdout.isatty():
        print(f"\n{BOLD}{title}{RESET}")
        print(get_divider("─"))
        if subtitle:
            print(f"  {subtitle}\n")
        for i, opt in enumerate(options, 1):
            print(f"  {i} ▸ {opt}")
        print(get_divider("─"))
        try:
            val = input(f"▸ Auswahl (1-{total}): ").strip()
            if val.isdigit() and 1 <= int(val) <= total:
                return int(val) - 1
        except Exception:
            pass
        return None

    selected_idx = default_idx if 0 <= default_idx < total else 0
    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)

    mouse_enabled = True
    try:
        cfg = load_config()
        mouse_enabled = cfg.get("mouse_support", True)
    except Exception:
        pass

    tty.setcbreak(fd, termios.TCSADRAIN)
    if not preserve_screen:
        sys.stdout.write("\033[?1049h" + HIDE_CURSOR)
    else:
        sys.stdout.write(HIDE_CURSOR)
    if mouse_enabled:
        sys.stdout.write("\033[?1000h\033[?1006h")
    sys.stdout.write("\033[2J\033[H")
    sys.stdout.flush()

    last_size = None
    needs_redraw = True
    opt_row_map = {}

    try:
        while True:
            curr_size = shutil.get_terminal_size((80, 24))
            if curr_size != last_size:
                last_size = curr_size
                needs_redraw = True

            if needs_redraw:
                term_cols, term_rows = curr_size
                inner_w = max(10, term_cols - 2)
                opt_row_map.clear()
                lines = []

                # 1. Top border
                lines.append(f"╭{'─' * inner_w}╮")

                # 2. Titel
                t_trunc = truncate_end(title, max(4, inner_w - 4))
                title_line = pad_visible(f"  {BOLD}{t_trunc}{RESET}", inner_w)
                lines.append(f"│{title_line}│")

                # 3. Subtitel (falls vorhanden)
                if subtitle:
                    s_trunc = truncate_end(subtitle, max(4, inner_w - 4))
                    sub_line = pad_visible(f"  {ITALIC}{s_trunc}{RESET}", inner_w)
                    lines.append(f"│{sub_line}│")

                # 4. Trenner
                lines.append(f"├{'─' * inner_w}┤")

                # 5. Budget für Optionen
                fixed_bottom = 3
                avail_rows = max(1, term_rows - len(lines) - fixed_bottom)

                if total <= avail_rows:
                    start_idx = 0
                    end_idx = total
                    has_up = False
                    has_down = False
                else:
                    show_count = max(1, avail_rows - 2)
                    half = show_count // 2
                    start_idx = max(0, min(selected_idx - half, total - show_count))
                    end_idx = min(total, start_idx + show_count)
                    has_up = (start_idx > 0)
                    has_down = (end_idx < total)

                if has_up:
                    up_txt = pad_visible(f"  {ITALIC}▲ ... ({start_idx} weitere oben){RESET}", inner_w)
                    lines.append(f"│{up_txt}│")

                for idx in range(start_idx, end_idx):
                    opt = options[idx]
                    is_sel = (idx == selected_idx)
                    row_num = len(lines) + 1
                    opt_row_map[row_num] = idx

                    opt_w = max(4, inner_w - 6)
                    opt_trunc = truncate_end(opt, opt_w)
                    if is_sel:
                        line_txt = pad_visible(f"  {BOLD}▸ {opt_trunc}{RESET}", inner_w)
                    else:
                        line_txt = pad_visible(f"    {opt_trunc}", inner_w)
                    lines.append(f"│{line_txt}│")

                if has_down:
                    down_txt = pad_visible(f"  {ITALIC}▼ ... ({total - end_idx} weitere unten){RESET}", inner_w)
                    lines.append(f"│{down_txt}│")

                # 6. Auffüllen mit leeren Kasten-Zeilen
                while len(lines) + fixed_bottom < term_rows:
                    lines.append(f"│{' ' * inner_w}│")

                # 7. Unterer Trenner & Hilfstext & Abschluss
                lines.append(f"├{'─' * inner_w}┤")
                hints = "[↑/↓/j/k] Navigieren  [Enter/→] Auswählen  [ESC/q] Zurück"
                if visible_len(hints) > inner_w - 4:
                    hints = "[↑/↓] Nav  [Enter] OK  [ESC] Zurück"
                hints_trunc = truncate_end(hints, max(4, inner_w - 4))
                hints_line = pad_visible(f"  {ITALIC}{hints_trunc}{RESET}", inner_w)
                lines.append(f"│{hints_line}│")
                lines.append(f"╰{'─' * inner_w}╯")

                # Bildschirmausgabe ohne Zeilenüberlauf und ohne Scrollen
                sys.stdout.write("\033[H")
                out_lines = lines[:term_rows]
                for i, line in enumerate(out_lines):
                    if i == len(out_lines) - 1:
                        sys.stdout.write(f"\r\033[2K{line}")
                    else:
                        sys.stdout.write(f"\r\033[2K{line}\n")
                sys.stdout.flush()
                needs_redraw = False

            key = read_key(fd, timeout=0.05)
            if not key:
                continue

            if key == "MOUSE_WHEEL_UP":
                selected_idx = (selected_idx - 1) % total
                needs_redraw = True
            elif key == "MOUSE_WHEEL_DOWN":
                selected_idx = (selected_idx + 1) % total
                needs_redraw = True
            elif key.startswith("MOUSE_CLICK:"):
                parts = key.split(":")
                if len(parts) == 3:
                    try:
                        click_y = int(parts[2])
                        if click_y in opt_row_map:
                            clicked_opt = opt_row_map[click_y]
                            if clicked_opt == selected_idx:
                                return clicked_opt
                            else:
                                selected_idx = clicked_opt
                                needs_redraw = True
                    except Exception:
                        pass
                continue
            elif key.startswith("MOUSE_"):
                continue
            elif key in ("UP", "k"):
                selected_idx = (selected_idx - 1) % total
                needs_redraw = True
            elif key in ("DOWN", "j", "TAB"):
                selected_idx = (selected_idx + 1) % total
                needs_redraw = True
            elif key == "HOME":
                selected_idx = 0
                needs_redraw = True
            elif key == "END":
                selected_idx = total - 1
                needs_redraw = True
            elif key in ("ENTER", "RIGHT", "l"):
                return selected_idx
            elif key in ("ESC", "LEFT", "h", "QUIT", "q"):
                return None
            elif key.isdigit():
                val = int(key)
                if 1 <= val <= total:
                    return val - 1
    finally:
        if mouse_enabled:
            sys.stdout.write("\033[?1006l\033[?1000l")
            sys.stdout.flush()
        sys.stdout.write(SHOW_CURSOR)
        if not preserve_screen:
            sys.stdout.write("\033[?1049l")
        sys.stdout.flush()
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)


def configure_single_keybinding(cfg: dict, action_key: str):
    """Ermöglicht das interaktive Neubelegen einer Taste durch Drücken der gewünschten Taste."""
    act_name = ACTION_NAMES.get(action_key, action_key)
    current_keys = cfg["keybindings"].get(action_key, [])
    keys_str = ", ".join(current_keys)

    choice = select_menu_interactive(
        f"TASTE FÜR: {act_name}",
        [
            f"Taste ersetzen (Aktuell: {keys_str})",
            "Zusätzliche Taste hinzufügen",
            "Zurücksetzen auf Standard",
            "Abbrechen",
        ],
        subtitle="Drücken Sie Enter bei der gewünschten Option",
        preserve_screen=True,
    )

    if choice is None or choice == 3:
        return

    if choice == 2:
        def_keys = DEFAULT_KEYMAP.get(action_key, [])
        cfg["keybindings"][action_key] = list(def_keys)
        save_config(cfg)
        return

    # Taste abfangen
    sys.stdout.write("\033[2J\033[H")
    sys.stdout.flush()
    print(f"\n\t{BOLD}Tastendruck erfassen für: {act_name}{RESET}")
    print(f"\t{get_divider('─')}")
    print(f"\tDrücken Sie jetzt die gewünschte Taste (oder ESC zum Abbrechen)...")
    print(f"\t{get_divider('─')}")
    sys.stdout.flush()

    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)
    tty.setcbreak(fd, termios.TCSADRAIN)
    captured = ""
    try:
        while True:
            k = read_key(fd, timeout=0.1)
            if k:
                captured = k
                break
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)

    if not captured or captured in ("ESC", "QUIT"):
        return

    # Taste formatieren
    new_key = captured
    if choice == 0:
        cfg["keybindings"][action_key] = [new_key]
    elif choice == 1:
        if new_key not in cfg["keybindings"][action_key]:
            cfg["keybindings"][action_key].append(new_key)

    save_config(cfg)


def menu_keybindings(cfg: dict):
    """Untermenü zum Durchsehen und Bearbeiten aller Tastenbelegungen ohne Springen."""
    cur_idx = 0
    while True:
        actions = list(ACTION_NAMES.keys())
        options = []
        for act in actions:
            name = ACTION_NAMES[act]
            keys = ", ".join(cfg["keybindings"].get(act, []))
            options.append(f"{name:<45} [{keys}]")
        options.append(f"{'Alle Tastenbelegungen auf Standard zurücksetzen':<45} [Standard]")
        options.append(f"{'Zurück zum Hauptmenü':<45} [Zurück]")

        choice = select_menu_interactive(
            "TASTENBELEGUNGEN BEARBEITEN",
            options,
            default_idx=cur_idx,
            subtitle="Wählen Sie eine Aktion aus, um ihre Tastenbelegung zu ändern",
            preserve_screen=True,
        )

        if choice is None or choice == len(options) - 1:
            break
        elif choice == len(options) - 2:
            cfg["keybindings"] = dict(DEFAULT_KEYMAP)
            save_config(cfg)
            cur_idx = choice
        else:
            cur_idx = choice
            selected_action = actions[choice]
            configure_single_keybinding(cfg, selected_action)


def run_konfigurator(standalone: bool = True) -> dict:
    """Interaktiver Konfigurator für EasyDateien ohne Flackern und ohne Rumspringen."""
    cfg = load_config()

    if not sys.stdin.isatty() or not sys.stdout.isatty():
        return cfg

    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)
    tty.setcbreak(fd, termios.TCSADRAIN)

    mouse_enabled = cfg.get("mouse_support", True)
    if standalone:
        sys.stdout.write("\033[?1049h" + HIDE_CURSOR)
    else:
        sys.stdout.write(HIDE_CURSOR)

    if mouse_enabled:
        sys.stdout.write("\033[?1000h\033[?1006h")

    sys.stdout.flush()

    selected_idx = 0
    feedback_msg = "Werte direkt mit Enter / Leertaste / Pfeiltaste umschalten"
    last_size = None
    needs_redraw = True
    opt_row_map = {}

    DIVIDER_OPTIONS = ["vertikal", "horizontal", "außen", "keine"]
    SORT_OPTIONS = ["mtime", "name", "size", "ext"]

    try:
        while True:
            curr_size = shutil.get_terminal_size((80, 24))
            if curr_size != last_size:
                last_size = curr_size
                needs_redraw = True

            show_ctrls = cfg.get("show_controls", True)
            ctrls_status = "Ein" if show_ctrls else "Aus"
            cols_status = "Ein" if cfg.get("columns_enabled", True) else "Aus"
            mouse_status = "Ein" if cfg.get("mouse_support", True) else "Aus"
            div_style = cfg.get("divider_style", "vertikal").lower()
            div_display = {"vertikal": "Vertikal", "horizontal": "Horizontal", "außen": "Außen", "keine": "Keine"}.get(div_style, "Vertikal")
            esc_status = "Ein" if cfg.get("esc_to_quit", False) else "Aus"
            hidden_status = "Ein" if cfg.get("show_hidden", False) else "Aus"
            ed_cmd = cfg.get("text_editor", "nano %s")
            op_cmd = cfg.get("opener", "open %s")
            sort_by = cfg.get("sort_by", "mtime")
            sort_by_name = {
                "mtime": "Änderungsdatum",
                "name": "Dateiname",
                "size": "Dateigröße",
                "ext": "Dateiendung",
            }.get(sort_by, "Änderungsdatum")

            sort_rev = cfg.get("sort_reverse", True)
            if sort_by in ("name", "ext"):
                sort_rev_display = "Z - A (Absteigend)" if sort_rev else "A - Z (Aufsteigend)"
            elif sort_by == "size":
                sort_rev_display = "Größte zuerst" if sort_rev else "Kleinste zuerst"
            else:
                sort_rev_display = "Neueste zuerst" if sort_rev else "Älteste zuerst"

            dir_first_status = "Ein" if cfg.get("sort_dir_first", True) else "Aus"

            menu_items = [
                ("Tastenbelegungen bearbeiten:", "Ansehen & Ändern"),
                ("Steuerung in Statusleiste:", ctrls_status),
                ("Spaltendarstellung:", cols_status),
                ("Maussteuerung:", mouse_status),
                ("Trennungslinien:", div_display),
                ("Mit ESC beenden:", esc_status),
                ("Versteckte Dateien anzeigen:", hidden_status),
                ("Text- & Code-Editor:", ed_cmd),
                ("Standard-Öffner (System):", op_cmd),
                ("Sortierkriterium:", sort_by_name),
                ("Sortierrichtung:", sort_rev_display),
                ("Ordner immer zuerst anzeigen:", dir_first_status),
                ("Standardeinstellungen:", "Zurücksetzen"),
                ("Konfiguration schließen:", "Zurück zu Dateien"),
            ]
            total = len(menu_items)
            if selected_idx >= total:
                selected_idx = total - 1
            if selected_idx < 0:
                selected_idx = 0

            if needs_redraw:
                term_cols, term_rows = curr_size
                inner_w = max(10, term_cols - 2)
                opt_row_map.clear()
                lines = []

                # 1. Top border
                lines.append(f"╭{'─' * inner_w}╮")

                # 2. Titel
                t_trunc = truncate_end("EASYDATEIEN — KONFIGURATIONSMENÜ", max(4, inner_w - 4))
                title_line = pad_visible(f"  {BOLD}{t_trunc}{RESET}", inner_w)
                lines.append(f"│{title_line}│")

                # 3. Subtitel / Rückmeldung
                s_trunc = truncate_end(feedback_msg, max(4, inner_w - 4))
                sub_line = pad_visible(f"  {ITALIC}{s_trunc}{RESET}", inner_w)
                lines.append(f"│{sub_line}│")

                # 4. Trenner
                lines.append(f"├{'─' * inner_w}┤")

                # 5. Budget für Optionen
                fixed_bottom = 3
                avail_rows = max(1, term_rows - len(lines) - fixed_bottom)

                if total <= avail_rows:
                    start_idx = 0
                    end_idx = total
                    has_up = False
                    has_down = False
                else:
                    show_count = max(1, avail_rows - 2)
                    half = show_count // 2
                    start_idx = max(0, min(selected_idx - half, total - show_count))
                    end_idx = min(total, start_idx + show_count)
                    has_up = (start_idx > 0)
                    has_down = (end_idx < total)

                if has_up:
                    up_txt = pad_visible(f"  {ITALIC}▲ ... ({start_idx} weitere oben){RESET}", inner_w)
                    lines.append(f"│{up_txt}│")

                # Berechne gleichmäßige Spaltenbreiten
                content_w = max(10, inner_w - 6)
                label_col_w = min(30, max(14, content_w - 24))

                for idx in range(start_idx, end_idx):
                    lbl, val = menu_items[idx]
                    is_sel = (idx == selected_idx)
                    row_num = len(lines) + 1
                    opt_row_map[row_num] = idx

                    val_max_w = max(6, content_w - label_col_w - 2)
                    lbl_trunc = truncate_end(lbl, label_col_w)
                    val_str = f"[{truncate_end(val, val_max_w - 2)}]"

                    formatted_content = f"{lbl_trunc:<{label_col_w}}  {val_str}"
                    formatted_content = truncate_end(formatted_content, content_w)

                    if is_sel:
                        line_txt = pad_visible(f"  {BOLD}▸ {formatted_content}{RESET}", inner_w)
                    else:
                        line_txt = pad_visible(f"    {formatted_content}", inner_w)
                    lines.append(f"│{line_txt}│")

                if has_down:
                    down_txt = pad_visible(f"  {ITALIC}▼ ... ({total - end_idx} weitere unten){RESET}", inner_w)
                    lines.append(f"│{down_txt}│")

                while len(lines) + fixed_bottom < term_rows:
                    lines.append(f"│{' ' * inner_w}│")

                lines.append(f"├{'─' * inner_w}┤")
                hints = "[↑/↓] Bewegen  [Enter/Space/→] Toggeln  [ESC/q] Zurück"
                if visible_len(hints) > inner_w - 4:
                    hints = "[↑/↓] Nav  [Enter] Toggeln  [ESC] Zurück"
                hints_trunc = truncate_end(hints, max(4, inner_w - 4))
                hints_line = pad_visible(f"  {ITALIC}{hints_trunc}{RESET}", inner_w)
                lines.append(f"│{hints_line}│")
                lines.append(f"╰{'─' * inner_w}╯")

                # Bildschirmausgabe direkt überschreiben
                sys.stdout.write("\033[H")
                out_lines = lines[:term_rows]
                for i, line in enumerate(out_lines):
                    if i == len(out_lines) - 1:
                        sys.stdout.write(f"\r\033[2K{line}")
                    else:
                        sys.stdout.write(f"\r\033[2K{line}\n")
                sys.stdout.flush()
                needs_redraw = False

            def apply_action(action_idx: int) -> bool:
                """Wendet eine Aktion direkt an ohne Extramenü beim Toggeln."""
                nonlocal feedback_msg
                if action_idx == 0:
                    menu_keybindings(cfg)
                    feedback_msg = "Tastenbelegungen ansehen und anpassen"
                    return True
                elif action_idx == 1:
                    cfg["show_controls"] = not cfg.get("show_controls", True)
                    save_config(cfg)
                    feedback_msg = f"Steuerung in Statusleiste: {'[Ein]' if cfg['show_controls'] else '[Aus]'}"
                    return True
                elif action_idx == 2:
                    cfg["columns_enabled"] = not cfg.get("columns_enabled", True)
                    save_config(cfg)
                    feedback_msg = f"Spaltendarstellung: {'[Ein]' if cfg['columns_enabled'] else '[Aus]'}"
                    return True
                elif action_idx == 3:
                    cfg["mouse_support"] = not cfg.get("mouse_support", True)
                    save_config(cfg)
                    feedback_msg = f"Maussteuerung: {'[Ein]' if cfg['mouse_support'] else '[Aus]'}"
                    return True
                elif action_idx == 4:
                    cur = cfg.get("divider_style", "vertikal").lower()
                    next_div = DIVIDER_OPTIONS[(DIVIDER_OPTIONS.index(cur) + 1) % len(DIVIDER_OPTIONS)] if cur in DIVIDER_OPTIONS else "vertikal"
                    cfg["divider_style"] = next_div
                    save_config(cfg)
                    div_disp = {"vertikal": "Vertikal", "horizontal": "Horizontal", "außen": "Außen", "keine": "Keine"}.get(next_div, "Vertikal")
                    feedback_msg = f"Trennungslinien: [{div_disp}]"
                    return True
                elif action_idx == 5:
                    cfg["esc_to_quit"] = not cfg.get("esc_to_quit", False)
                    save_config(cfg)
                    feedback_msg = f"Mit ESC beenden: {'[Ein]' if cfg['esc_to_quit'] else '[Aus]'}"
                    return True
                elif action_idx == 6:
                    cfg["show_hidden"] = not cfg.get("show_hidden", False)
                    save_config(cfg)
                    feedback_msg = f"Versteckte Dateien: {'[Ein]' if cfg['show_hidden'] else '[Aus]'}"
                    return True
                elif action_idx == 7:
                    new_ed = edit_line_interactive("Editor-Befehl (%s = Pfad): ", initial=cfg.get("text_editor", "nano %s"))
                    if new_ed and new_ed.strip():
                        cfg["text_editor"] = new_ed.strip()
                        save_config(cfg)
                        feedback_msg = f"Editor gesetzt auf: [{new_ed.strip()}]"
                    return True
                elif action_idx == 8:
                    new_op = edit_line_interactive("Öffner-Befehl (%s = Pfad): ", initial=cfg.get("opener", "open %s"))
                    if new_op and new_op.strip():
                        cfg["opener"] = new_op.strip()
                        save_config(cfg)
                        feedback_msg = f"Standard-Öffner gesetzt auf: [{new_op.strip()}]"
                    return True
                elif action_idx == 9:
                    cur_s = cfg.get("sort_by", "mtime")
                    next_s = SORT_OPTIONS[(SORT_OPTIONS.index(cur_s) + 1) % len(SORT_OPTIONS)] if cur_s in SORT_OPTIONS else "mtime"
                    cfg["sort_by"] = next_s
                    save_config(cfg)
                    s_name = {"mtime": "Änderungsdatum", "name": "Dateiname", "size": "Dateigröße", "ext": "Dateiendung"}.get(next_s, "Änderungsdatum")
                    feedback_msg = f"Sortierkriterium: [{s_name}]"
                    return True
                elif action_idx == 10:
                    cfg["sort_reverse"] = not cfg.get("sort_reverse", True)
                    save_config(cfg)
                    s_by = cfg.get("sort_by", "mtime")
                    s_rev = cfg["sort_reverse"]
                    if s_by in ("name", "ext"):
                        r_name = "Z - A (Absteigend)" if s_rev else "A - Z (Aufsteigend)"
                    elif s_by == "size":
                        r_name = "Größte zuerst" if s_rev else "Kleinste zuerst"
                    else:
                        r_name = "Neueste zuerst" if s_rev else "Älteste zuerst"
                    feedback_msg = f"Sortierrichtung: [{r_name}]"
                    return True
                elif action_idx == 11:
                    cfg["sort_dir_first"] = not cfg.get("sort_dir_first", True)
                    save_config(cfg)
                    feedback_msg = f"Ordner zuerst: {'[Ein]' if cfg['sort_dir_first'] else '[Aus]'}"
                    return True
                elif action_idx == 12:
                    cfg.clear()
                    cfg.update(get_default_config())
                    save_config(cfg)
                    feedback_msg = "Standardeinstellungen erfolgreich wiederhergestellt!"
                    return True
                elif action_idx == 13:
                    return False
                return True

            key = read_key(fd, timeout=0.05)
            if not key:
                continue

            if key == "MOUSE_WHEEL_UP":
                selected_idx = (selected_idx - 1) % total
                needs_redraw = True
            elif key == "MOUSE_WHEEL_DOWN":
                selected_idx = (selected_idx + 1) % total
                needs_redraw = True
            elif key.startswith("MOUSE_CLICK:"):
                parts = key.split(":")
                if len(parts) == 3:
                    try:
                        click_y = int(parts[2])
                        if click_y in opt_row_map:
                            clicked_idx = opt_row_map[click_y]
                            selected_idx = clicked_idx
                            if not apply_action(clicked_idx):
                                break
                            needs_redraw = True
                    except Exception:
                        pass
                continue
            elif key.startswith("MOUSE_"):
                continue
            elif key in ("UP", "k"):
                selected_idx = (selected_idx - 1) % total
                needs_redraw = True
            elif key in ("DOWN", "j", "TAB"):
                selected_idx = (selected_idx + 1) % total
                needs_redraw = True
            elif key == "HOME":
                selected_idx = 0
                needs_redraw = True
            elif key == "END":
                selected_idx = total - 1
                needs_redraw = True
            elif key in ("ENTER", "SPACE", "RIGHT", "l"):
                if not apply_action(selected_idx):
                    break
                needs_redraw = True
            elif key in ("ESC", "LEFT", "h", "QUIT", "q"):
                break

    finally:
        if mouse_enabled:
            sys.stdout.write("\033[?1006l\033[?1000l")
            sys.stdout.flush()
        sys.stdout.write(SHOW_CURSOR)
        if standalone:
            sys.stdout.write("\033[?1049l")
        sys.stdout.flush()
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)

    return cfg


def main():
    parser = argparse.ArgumentParser(description="Konfigurator für EasyDateien")
    parser.add_argument("-l", "--list", action="store_true", help="Aktuelle Konfiguration ausgeben")
    parser.add_argument("--toggle-hidden", action="store_true", help="Versteckte Dateien umschalten")
    parser.add_argument("--reset", action="store_true", help="Auf Standardeinstellungen zurücksetzen")
    args = parser.parse_args()

    cfg = load_config()

    if args.list:
        print(json.dumps(cfg, indent=2, ensure_ascii=False))
        sys.exit(0)
    elif args.toggle_hidden:
        cfg["show_hidden"] = not cfg.get("show_hidden", False)
        save_config(cfg)
        print(f"Versteckte Dateien: {'Ein' if cfg['show_hidden'] else 'Aus'}")
        sys.exit(0)
    elif args.reset:
        cfg = get_default_config()
        save_config(cfg)
        print("EasyDateien erfolgreich auf Yazi-Standardwerte zurückgesetzt.")
        sys.exit(0)

    run_konfigurator()


if __name__ == "__main__":
    main()
