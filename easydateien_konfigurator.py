#!/usr/bin/env python3
"""
EasyDateien Konfigurator — Interaktive Konfigurations-Engine für EasyDateien.
Single-Source-of-Truth & optimi-Norm konform.

Alle geteilten Grundlagen (Breitenlogik, Kürzung, Tastenbelegungen,
Konfigurationsdatei) stammen aus easydateien_common; dieses Modul enthält
ausschließlich die Menüführung des Konfigurators.
"""

import os
import sys
import termios
import tty
import select
import shutil
import argparse

from easydateien_common import (
    ANSI_ESCAPE_RE,
    C_RESET,
    C_BOLD,
    C_INVERT,
    DISABLE_AUTOWRAP,
    ENABLE_AUTOWRAP,
    DEFAULT_CONFIG,
    KEY_BINDINGS,
    CHORD_ACTIONS,
    get_keybindings_from_config,
    build_keymap,
    char_width,
    str_width,
    truncate_to_width,
    pad_to_width,
    distribute_options,
    fit_hints,
    load_config,
    save_config,
)

# Kompatibilitäts-Re-Exports: Der Dateimanager und externe Aufrufe können diese
# Namen weiterhin von hier importieren.
__all__ = [
    "KEY_BINDINGS", "build_keymap", "fit_hints", "CHORD_ACTIONS",
    "load_config", "save_config", "DEFAULT_CONFIG", "run_konfigurator",
]

KEYBINDING_ITEMS = [(action, desc, f"[{disp}]") for _s, action, disp, _k, desc in KEY_BINDINGS] + [
    ("reset", "Auf Standardwerte zurücksetzen", "[standard]"),
]

MAIN_MENU_ITEMS = [
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

def read_key(fd: int, timeout: float = 0.05) -> str:
    """Liest Tastatur- und Maus-Events (vereinfachter Zeichensatz des Konfigurators)."""
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

def clicked_row(k: str, start: int, count: int) -> "int | None":
    """Liefert bei einem Mausklick den Index der geklickten Menüzeile, sonst None.

    Der Menüinhalt beginnt in Zeile 6 des Terminalfensters (Rahmen und
    Kopfzeile belegen die Zeilen 1 bis 5), daher Offset 5.
    """
    if not k.startswith("CLICK:"):
        return None
    try:
        _, _cx_s, cy_s = k.split(":")
        row_i = int(cy_s) - 5
    except Exception:
        return None
    if 0 <= row_i < count:
        return start + row_i
    return None

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
    lines.append(f"│ {pad_to_width(t_styled, inner - 2)}│")
    s_styled = truncate_to_width(subtitle, inner - 4)
    lines.append(f"│ {pad_to_width(s_styled, inner - 2)}│")
    lines.append(f"├{'─' * inner}┤")

    for i, (key, label, tag) in enumerate(view_rows):
        actual_idx = start + i
        is_sel = (actual_idx == cur_idx)
        pfx = " "

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
        lbl_styled = lbl_trunc
        pad_len = max(1, inner - 2 - str_width(pfx) - str_width(lbl_trunc) - str_width(tag))
        content_row = f"{pfx}{lbl_styled}{' ' * pad_len}{tag_colored} "
        if is_sel:
            content_row = f"{C_BOLD}{C_INVERT}{pad_to_width(ANSI_ESCAPE_RE.sub('', content_row), inner)}{C_RESET}"
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
    lines.append(f"│ {pad_to_width(f_styled, inner - 2)}│")
    lines.append(f"╰{'─' * inner}╯")

    out = []
    for r_i, l in enumerate(lines[:term_rows]):
        out.append(f"\033[{r_i+1};1H\033[2K{l}")
    sys.stdout.write("".join(out))
    sys.stdout.flush()
    return start, len(view_rows)

def _bindings_valid(bindings: list) -> bool:
    """Prüft eine Belegungsliste auf Doppelbelegungen, ohne die Konfiguration zu ändern."""
    try:
        build_keymap({"keybindings": [
            [section, action, disp, list(keys), desc]
            for section, action, disp, keys, desc in bindings
        ]})
        return True
    except ValueError:
        return False

def edit_keybindings_menu(fd: int):
    """Interaktives Menü zum Anpassen der Tastenbelegungen."""
    cfg = load_config()

    # Aktuelle Tastenbelegungen laden oder Standard verwenden
    current_bindings = get_keybindings_from_config(cfg)

    # Umwandeln in eine bearbeitbare Struktur
    # Jede Aktion: (Abschnitt, Aktions-ID, Anzeige, Tasten-Tokens, Beschreibung)
    editable_bindings = list(current_bindings)

    def save_editable_bindings() -> bool:
        # Speichert nur, wenn die Belegungen konfliktfrei sind; ein Konflikt
        # würde sonst den Start des Dateimanagers verhindern.
        if not _bindings_valid(editable_bindings):
            return False
        json_bindings = []
        for section, action, disp, keys, desc in editable_bindings:
            json_bindings.append([section, action, disp, list(keys), desc])
        cfg["keybindings"] = json_bindings
        save_config(cfg)
        return True

    idx = 0
    status_hint = ""

    while True:
        # Menüeinträge vorbereiten: (key, label, value)
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
            if not save_editable_bindings():
                status_hint = f"{C_BOLD}✗ Nicht gespeichert: Doppelte Taste wäre unbrauchbar{C_RESET}"
                continue
            break
        else:
            click = clicked_row(k, start, count)
            if click is not None:
                idx = click
                continue

        if k in ("ENTER", "SPACE", "RIGHT"):
            selected_action = binding_rows[idx][0]

            if selected_action == "reset":
                # Zurück auf Standard
                editable_bindings = list(KEY_BINDINGS)
                status_hint = f"{C_BOLD}✓ Tastenbelegungen zurückgesetzt{C_RESET}"

            elif selected_action == "back":
                if not save_editable_bindings():
                    status_hint = f"{C_BOLD}✗ Nicht gespeichert: Doppelte Taste wäre unbrauchbar{C_RESET}"
                break

            else:
                # Tastenbelegung für diese Aktion bearbeiten
                for i, (section, action, disp, keys, desc) in enumerate(editable_bindings):
                    if action == selected_action:
                        render_box(
                            f"TASTEN FÜR '{disp}' ÄNDERN",
                            "Drücken Sie die neue Taste oder Tastenkombination (ESC zum Abbrechen)",
                            [],
                            0,
                            [("Aktuell:", ", ".join(keys), "")]
                        )

                        # Warten auf neue Tastenbelegung
                        new_key = ""
                        while True:
                            key_press = read_key(fd)
                            if key_press == "ESC":
                                break
                            elif key_press:
                                new_key = key_press
                                break

                        if new_key:
                            trial = list(editable_bindings)
                            trial[i] = (section, action, disp, [new_key], desc)
                            if _bindings_valid(trial):
                                editable_bindings = trial
                                status_hint = f"{C_BOLD}✓ '{disp}' auf [{new_key}] gesetzt{C_RESET}"
                            else:
                                status_hint = f"{C_BOLD}✗ [{new_key}] ist bereits belegt{C_RESET}"
                        break


def sort_menu(fd: int):
    cfg = load_config()
    idx = 0
    status_hint = ""

    # Verfügbare Sortieroptionen
    sort_options = [
        ("name", "Name (alphabetisch)", "Nach Dateinamen sortieren"),
        ("mtime", "Änderungsdatum", "Nach Modifikationszeit sortieren"),
        ("atime", "Zugangsdatum", "Nach Zugriffszeit sortieren"),
        ("size", "Größe", "Nach Dateigröße sortieren"),
        ("ext", "Endung", "Nach Dateiendung sortieren"),
    ]

    while True:
        # Aktuelle Einstellungen anzeigen
        current_sort = cfg.get("sort_by", "mtime")
        reverse_state = "normal" if cfg.get("sort_reverse", False) else "umgekehrt"
        dir_first_state = "ordner zuerst" if cfg.get("sort_dir_first", True) else "gemischt"

        sort_rows = []
        for key, lbl, _ in sort_options:
            marker = "* " if key == current_sort else "  "
            sort_rows.append((key, f"{marker}{lbl}", ""))

        # Zusätzliche Optionen für Sortierverhalten
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
        else:
            click = clicked_row(k, start, count)
            if click is not None:
                idx = click
                continue

        if k in ("ENTER", "SPACE", "RIGHT"):
            selected_key = sort_rows[idx][0]
            if selected_key in [s[0] for s in sort_options]:
                # Sortierkriterium ändern
                cfg["sort_by"] = selected_key
                save_config(cfg)
                status_hint = f"{C_BOLD}✓ Sortierung nach {sort_rows[idx][1].split('] ')[-1]}{C_RESET}"
            elif selected_key == "reverse":
                # Sortierreihenfolge umschalten
                cfg["sort_reverse"] = not cfg.get("sort_reverse", True)
                save_config(cfg)
            elif selected_key == "dir_first":
                # Ordner-zuerst-Einstellung umschalten
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
        else:
            click = clicked_row(k, start, count)
            if click is not None:
                idx = click
                continue
        if k in ("ENTER", "SPACE"):
            act = KEYBINDING_ITEMS[idx][0]
            if act == "reset":
                save_config(dict(DEFAULT_CONFIG))
                break


# Datengesteuerte Wertanzeige des Hauptmenüs: Jede Option bestimmt ihren
# angezeigten Wert über eine Funktion; neue Optionen erfordern genau eine Zeile.
MENU_VALUE_RENDERERS = {
    "mouse": lambda cfg: f"[{'ein' if cfg.get('mouse_support', True) else 'aus'}]",
    "hidden": lambda cfg: f"[{'ein' if cfg.get('show_hidden', False) else 'aus'}]",
    "console_always_visible": lambda cfg: f"[{'ein' if cfg.get('console_always_visible', False) else 'aus'}]",
    "console_dynamic_height": lambda cfg: f"[{'ein' if cfg.get('console_dynamic_height', True) else 'aus'}]",
    "console_position": lambda cfg: f"[{cfg.get('console_position', 'unten')}]",
    "preview_wrap": lambda cfg: f"[{'ein' if cfg.get('preview_wrap', True) else 'aus'}]",
    "sort": lambda cfg: "[öffnen]",
    "editor": lambda cfg: f"[{editor_command(cfg)}]",
    "keybindings": lambda cfg: "[öffnen]",
    "reset": lambda cfg: "[standard]",
}

# Umschalt- und Rotationsaktionen des Hauptmenüs (datengetrieben)
_CONSOLE_POSITIONS = ["unten", "rechts", "links"]


def _cycle_option(cfg: dict, key: str, options: list, step: int) -> None:
    cur = cfg.get(key, options[0])
    cur_i = options.index(cur) if cur in options else 0
    cfg[key] = options[(cur_i + step) % len(options)]


def _toggle_option(cfg: dict, key: str, default: bool) -> None:
    cfg[key] = not cfg.get(key, default)


def main_menu(fd: int):
    cfg = load_config()
    idx = 0
    status_hint = ""
    while True:
        rows = []
        for key, lbl, _ in MAIN_MENU_ITEMS:
            rows.append((key, lbl, MENU_VALUE_RENDERERS[key](cfg)))

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
        else:
            click = clicked_row(k, start, count)
            if click is not None:
                idx = click
                continue

        if k in ("ENTER", "SPACE", "RIGHT", "LEFT"):
            act = rows[idx][0]
            if act == "mouse":
                _toggle_option(cfg, "mouse_support", True)
                save_config(cfg)
            elif act == "hidden":
                _toggle_option(cfg, "show_hidden", False)
                save_config(cfg)
            elif act == "console_always_visible":
                _toggle_option(cfg, "console_always_visible", False)
                save_config(cfg)
            elif act == "console_dynamic_height":
                _toggle_option(cfg, "console_dynamic_height", True)
                save_config(cfg)
            elif act == "console_position":
                _cycle_option(cfg, "console_position", _CONSOLE_POSITIONS, -1 if k == "LEFT" else 1)
                save_config(cfg)
            elif act == "preview_wrap":
                _toggle_option(cfg, "preview_wrap", True)
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
