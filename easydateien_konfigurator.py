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
    "up": "Cursor nach oben",
    "down": "Cursor nach unten",
    "left": "Übergeordneter Ordner (Zurück)",
    "right": "Hineingehen / Öffnen",
    "open": "Datei oder Ordner öffnen",
    "select": "Auswahl umschalten (Markieren)",
    "select_all": "Alle markieren / abwählen",
    "cut": "Ausschneiden (x)",
    "copy": "Kopieren (c)",
    "paste": "Einfügen / Einsetzen (p)",
    "trash": "In den Papierkorb verschieben (d)",
    "toggle_hidden": "Versteckte Dateien umschalten (./z)",
    "config_menu": "Konfigurationsmenü öffnen (m)",
    "goto_downloads": "Gehe zu Downloads (g d)",
    "goto_documents": "Gehe zu Dokumente (g f)",
    "goto_home": "Gehe zu Benutzerordner (g h / ~)",
    "goto_interactive": "Pfad manuell eingeben (g i)",
    "goto_clipboard": "Gehe zu kopiertem Pfad (g p)",
    "zip": "ZIP-Archiv erstellen (c z)",
    "quit": "Beenden (q / ESC)",
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
        "divider_style": "horizontal",
        "esc_to_quit": False,
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


def get_divider(char: str = "─") -> str:
    """Gibt eine horizontale Trennlinie dynamisch angepasst an die Terminalbreite zurück."""
    try:
        width = shutil.get_terminal_size((75, 20)).columns
        return char * max(40, width)
    except Exception:
        return char * 75


def read_key(fd: int, timeout: float = 0.05) -> str:
    """Liest einen einzelnen Tastendruck ungepuffert direkt aus dem Filedeskriptor."""
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
            if len(seq) >= 5 or (len(seq) >= 2 and seq[-1:] in b"ABCDHFS~"):
                break

        if not seq:
            return "ESC"

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
) -> int | None:
    """Interaktives Auswahldialogmenü mit flüssiger Pfeiltastennavigation im SCHNELLSTART-Design."""
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

    tty.setcbreak(fd, termios.TCSADRAIN)
    sys.stdout.write(HIDE_CURSOR)
    sys.stdout.write("\033[2J\033[H")
    sys.stdout.flush()

    last_size = None
    needs_redraw = True

    try:
        while True:
            curr_size = shutil.get_terminal_size((80, 24))
            if curr_size != last_size:
                last_size = curr_size
                needs_redraw = True

            if needs_redraw:
                term_cols, term_rows = curr_size
                lines = []
                lines.append(f"\t{BOLD}{title}{RESET}")
                lines.append(f"\t{get_divider('─')}")
                if subtitle:
                    lines.append(f"\t{ITALIC}{subtitle}{RESET}")
                    lines.append("")

                fixed_lines_count = len(lines) + 2
                avail_rows = max(3, term_rows - fixed_lines_count)

                if total <= avail_rows:
                    for idx, opt in enumerate(options):
                        is_sel = (idx == selected_idx)
                        if is_sel:
                            lines.append(f"\t  {BOLD}▸ {opt}{RESET}")
                        else:
                            lines.append(f"\t    {opt}")
                else:
                    window_size = max(2, avail_rows - 2)
                    half = window_size // 2
                    start_idx = max(0, min(selected_idx - half, total - window_size))
                    end_idx = min(total, start_idx + window_size)

                    if start_idx > 0:
                        lines.append(f"\t  ▲ ... ({start_idx} weitere oben)")
                    for idx in range(start_idx, end_idx):
                        opt = options[idx]
                        is_sel = (idx == selected_idx)
                        if is_sel:
                            lines.append(f"\t  {BOLD}▸ {opt}{RESET}")
                        else:
                            lines.append(f"\t    {opt}")
                    if end_idx < total:
                        lines.append(f"\t  ▼ ... ({total - end_idx} weitere unten)")

                lines.append(f"\t{get_divider('─')}")
                lines.append(f"\t{ITALIC}[↑/↓/j/k] Navigieren  [Enter/→] Auswählen  [ESC/q] Zurück{RESET}")

                top_padding = max(0, (term_rows - len(lines)) // 2)

                sys.stdout.write("\033[H")
                for _ in range(top_padding):
                    sys.stdout.write(f"\r{CLEAR_LINE}\n")
                for line in lines:
                    sys.stdout.write(f"\r{CLEAR_LINE}{line}\n")
                sys.stdout.write("\033[J")
                sys.stdout.flush()
                needs_redraw = False

            key = read_key(fd, timeout=0.05)
            if not key:
                continue

            if key in ("UP", "k"):
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
        sys.stdout.write(SHOW_CURSOR)
        sys.stdout.flush()
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)


def configure_single_keybinding(cfg: dict, action_key: str):
    """Ermöglicht das interaktive Neubelegen einer Taste durch Drücken der gewünschten Taste."""
    act_name = ACTION_NAMES.get(action_key, action_key)
    current_keys = cfg["keybindings"].get(action_key, [])
    keys_str = ", ".join(current_keys)

    sys.stdout.write("\033[2J\033[H")
    sys.stdout.flush()
    print(f"\n\t{BOLD}Tastenbelegung anpassen: {act_name}{RESET}")
    print(f"\t{get_divider('─')}")
    print(f"\tAktuell zugewiesen: {BOLD}[{keys_str}]{RESET}\n")
    print("\tOptionen:")
    print("\t  [1] Neue Taste zuweisen (Ersetzen)")
    print("\t  [2] Zusätzliche Taste ergänzen")
    print("\t  [3] Belegung auf Standard zurücksetzen")
    print("\t  [ESC] Abbrechen\n")
    print(f"\t{get_divider('─')}")

    choice = select_menu_interactive(
        f"Aktion: {act_name}",
        [
            f"Taste ersetzen (Aktuell: {keys_str})",
            "Zusätzliche Taste hinzufügen",
            "Zurücksetzen auf Standard",
            "Abbrechen",
        ],
        subtitle="Drücken Sie Enter bei der gewünschten Option",
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
    """Untermenü zum Durchsehen und Bearbeiten aller Tastenbelegungen."""
    while True:
        actions = list(ACTION_NAMES.keys())
        options = []
        for act in actions:
            name = ACTION_NAMES[act]
            keys = ", ".join(cfg["keybindings"].get(act, []))
            options.append(f"{name:<38} [{keys}]")
        options.append("Alle Tastenbelegungen auf Standard zurücksetzen")
        options.append("Zurück zum Hauptmenü")

        choice = select_menu_interactive(
            "TASTENBELEGUNGEN BEARBEITEN",
            options,
            subtitle="Wählen Sie eine Aktion aus, um ihre Tastenbelegung zu ändern",
        )

        if choice is None or choice == len(options) - 1:
            break
        elif choice == len(options) - 2:
            cfg["keybindings"] = dict(DEFAULT_KEYMAP)
            save_config(cfg)
        else:
            selected_action = actions[choice]
            configure_single_keybinding(cfg, selected_action)


def menu_sort_criteria(cfg: dict):
    """Auswahl des Sortierkriteriums."""
    criteria = [
        ("mtime", "Änderungsdatum (Neueste / Älteste Dateien)"),
        ("name", "Dateiname (Alphabetisch A-Z / Z-A)"),
        ("size", "Dateigröße (Größte / Kleinste Dateien)"),
        ("ext", "Dateiendung / Dateityp (.pdf, .txt, ...)"),
    ]
    cur = cfg.get("sort_by", "mtime")
    def_idx = 0
    options = []
    for idx, (val, desc) in enumerate(criteria):
        is_cur = (val == cur)
        mark = " (Aktiv)" if is_cur else ""
        if is_cur:
            def_idx = idx
        options.append(f"{desc}{mark}")
    options.append("Abbrechen / Zurück")

    choice = select_menu_interactive("SORTIERKRITERIUM WÄHLEN", options, default_idx=def_idx)
    if choice is not None and choice < len(criteria):
        cfg["sort_by"] = criteria[choice][0]
        save_config(cfg)


def menu_dividers(cfg: dict):
    """Auswahl des Trennlinien-Stils (horizontal / vertikal / keine)."""
    options = [
        "Horizontal (Klassische horizontale Linien oben und unten)",
        "Vertikal (Spaltentrennung mit vertikalem Trennstrich │)",
        "Keine (Puristisches, linienfreies Layout mit Leerräumen)",
        "Abbrechen / Zurück",
    ]
    cur = cfg.get("divider_style", "horizontal").lower()
    def_idx = 0 if cur == "horizontal" else (1 if cur == "vertikal" else (2 if cur == "keine" else 0))
    choice = select_menu_interactive("TRENNUNGSLINIEN WÄHLEN", options, default_idx=def_idx)
    if choice == 0:
        cfg["divider_style"] = "horizontal"
        save_config(cfg)
    elif choice == 1:
        cfg["divider_style"] = "vertikal"
        save_config(cfg)
    elif choice == 2:
        cfg["divider_style"] = "keine"
        save_config(cfg)


def run_konfigurator() -> dict:
    """Startet das interaktive Konfigurationsmenü im SCHNELLSTART-Design."""
    cfg = load_config()

    while True:
        hidden_status = "[Ein]" if cfg.get("show_hidden", False) else "[Aus]"
        dir_first_status = "[Ein]" if cfg.get("sort_dir_first", True) else "[Aus]"
        sort_rev_status = "[Neueste/Z-A zuerst]" if cfg.get("sort_reverse", True) else "[Älteste/A-Z zuerst]"
        sort_by_name = {
            "mtime": "Änderungsdatum",
            "name": "Dateiname",
            "size": "Dateigröße",
            "ext": "Dateiendung",
        }.get(cfg.get("sort_by", "mtime"), "Änderungsdatum")
        cols_enabled = cfg.get("columns_enabled", True)
        cols_status = "[Ein]" if cols_enabled else "[Aus]"
        esc_quit = cfg.get("esc_to_quit", False)
        esc_status = "[Ein]" if esc_quit else "[Aus]"
        div_style = cfg.get("divider_style", "horizontal").lower()
        div_display = {"horizontal": "Horizontal", "vertikal": "Vertikal", "keine": "Keine"}.get(div_style, "Horizontal")
        editor_cmd = cfg.get("text_editor", "nano %s")
        opener_cmd = cfg.get("opener", "open %s")

        menu_items = [
            "Tastenbelegungen ansehen & anpassen",
            f"Spaltendarstellung:                 {BOLD}{cols_status}{RESET}",
            f"Trennungslinien:                   {BOLD}[{div_display}]{RESET}",
            f"Mit ESC beenden:                   {BOLD}{esc_status}{RESET}",
            f"Versteckte Dateien anzeigen:       {BOLD}{hidden_status}{RESET}",
            f"Text- & Code-Editor festlegen:    {BOLD}[{editor_cmd}]{RESET}",
            f"Standard-Öffner (Medien etc.):    {BOLD}[{opener_cmd}]{RESET}",
            f"Sortierkriterium festlegen:        {BOLD}[{sort_by_name}]{RESET}",
            f"Sortierrichtung:                   {BOLD}{sort_rev_status}{RESET}",
            f"Ordner immer zuerst anzeigen:      {BOLD}{dir_first_status}{RESET}",
            "Auf Standardeinstellungen zurücksetzen (Yazi-Konfiguration)",
            "Zurück zu EasyDateien",
        ]

        choice = select_menu_interactive(
            "EASYDATEIEN — KONFIGURATIONSMENÜ",
            menu_items,
            subtitle="Konfiguration wird automatisch in ~/.config/easydateien/config.json gesichert",
        )

        if choice is None or choice == 11:
            break
        elif choice == 0:
            menu_keybindings(cfg)
        elif choice == 1:
            # Spaltendarstellung ein/aus
            cfg["columns_enabled"] = not cfg.get("columns_enabled", True)
            save_config(cfg)
        elif choice == 2:
            # Trennungslinien vertikal / horizontal / keine
            menu_dividers(cfg)
        elif choice == 3:
            # Mit ESC beenden ein/aus
            cfg["esc_to_quit"] = not cfg.get("esc_to_quit", False)
            save_config(cfg)
        elif choice == 4:
            # Versteckte Dateien ein/aus
            cfg["show_hidden"] = not cfg.get("show_hidden", False)
            save_config(cfg)
        elif choice == 5:
            # Text-Editor bearbeiten
            prompt = "Text-/Code-Editor-Befehl eingeben (%s = Dateipfad, z. B. nano %s): "
            new_ed = edit_line_interactive(prompt, initial=cfg.get("text_editor", "nano %s"))
            if new_ed and new_ed.strip():
                cfg["text_editor"] = new_ed.strip()
                save_config(cfg)
        elif choice == 6:
            # Standard-Öffner bearbeiten
            prompt = "Standard-Öffner-Befehl eingeben (%s = Dateipfad): "
            new_opener = edit_line_interactive(prompt, initial=cfg.get("opener", "open %s"))
            if new_opener and new_opener.strip():
                cfg["opener"] = new_opener.strip()
                save_config(cfg)
        elif choice == 7:
            menu_sort_criteria(cfg)
        elif choice == 8:
            # Sortierrichtung umkehren
            cfg["sort_reverse"] = not cfg.get("sort_reverse", True)
            save_config(cfg)
        elif choice == 9:
            # Ordner zuerst
            cfg["sort_dir_first"] = not cfg.get("sort_dir_first", True)
            save_config(cfg)
        elif choice == 10:
            # Reset auf Standardwerte
            cfg = get_default_config()
            save_config(cfg)

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
