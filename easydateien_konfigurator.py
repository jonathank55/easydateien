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
    format_keys,
)

# Kompatibilitäts-Re-Exports: Der Dateimanager und externe Aufrufe können diese
# Namen weiterhin von hier importieren.
__all__ = [
    "KEY_BINDINGS", "build_keymap", "fit_hints",
    "load_config", "save_config", "DEFAULT_CONFIG", "run_konfigurator",
]

KEYBINDING_ITEMS = [(action, desc, f"[{disp}]") for _s, action, disp, _k, desc in KEY_BINDINGS] + [
    ("reset", "Auf Standardwerte zurücksetzen", "[standard]"),
]

MAIN_MENU_ITEMS = [
    ("mouse", "Mausunterstützung", "ein"),
    ("hidden", "Versteckte Dateien anzeigen", "aus"),
    ("console_always_visible", "Konsole immer eingeblendet", "aus"),
    ("preview_wrap", "Vorschau-Umbruch", "ein"),
    ("sort", "Datei- und Ordneranordnung", "öffnen"),
    ("editor", "Editor", "nano"),
    ("keybindings", "Tastenbelegungen", "öffnen"),
    ("schnellstart", "Schnellstart-Einträge", "öffnen"),
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
                elif len(seq) >= 2 and seq[-1:] in b"ABCDHFS~Z":
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
                b"[1~": "HOME", b"[7~": "HOME", b"[4~": "END", b"[8~": "END",
                b"[2~": "INSERT", b"[3~": "DELETE",
                b"[5~": "PAGE_UP", b"[6~": "PAGE_DOWN", b"[Z": "SHIFT_TAB"
            }
            if seq not in mapping:
                if seq.startswith(b"[3") and seq.endswith(b"~"):
                    return "DELETE"
                if seq.startswith(b"[2") and seq.endswith(b"~"):
                    return "INSERT"
                return "UNBEKANNT"
            return mapping[seq]
        if raw in (bytes([13]), bytes([10])):
            return "ENTER"
        elif raw == b" ":
            return "SPACE"
        elif raw == b"\t":
            return "TAB"
        elif raw in (bytes([3]), bytes([4])):
            return "QUIT"
        try:
            ch = raw.decode("utf-8")
        except Exception:
            return "UNBEKANNT"
        # Steuerzeichen sind keine waehlbaren Tasten: Sie wuerden als
        # unsichtbare Token gespeichert ('[] ist bereits belegt').
        if not ch.isprintable():
            return "UNBEKANNT"
        return ch
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
    lines.append(f"│ {pad_to_width(t_styled, inner - 1)}│")
    s_styled = truncate_to_width(subtitle, inner - 4)
    lines.append(f"│ {pad_to_width(s_styled, inner - 1)}│")
    lines.append(f"├{'─' * inner}┤")

    for i, (key, label, tag) in enumerate(view_rows):
        actual_idx = start + i
        is_sel = (actual_idx == cur_idx)
        if tag in ("[Ein]", "Ein"):
            tag_colored = f"{C_BOLD}{tag}{C_RESET}"
        elif tag in ("[Aus]", "Aus"):
            tag_colored = tag
        elif tag:
            tag_colored = tag
        else:
            tag_colored = ""

        # Tag dynamisch kuerzen: Titel bekommt mindestens 2 Spalten,
        # der Tag den Rest; laengere Tags enden mit "..." statt hartem Schnitt.
        MIN_TITEL = 12
        tag_max = max(2, inner - 4 - MIN_TITEL)
        tag_visible = truncate_to_width(tag, tag_max)
        tag = tag_visible
        avail_lbl = max(MIN_TITEL, inner - str_width(tag_visible) - 3)
        lbl_trunc = truncate_to_width(label, avail_lbl)
        lbl_styled = lbl_trunc
        content_row = f"{lbl_styled}{' ' * max(1, inner - 2 - str_width(lbl_trunc) - str_width(tag_visible))}{tag_colored}"
        if is_sel:
            content_row = f"{C_BOLD}{C_INVERT} {pad_to_width(ANSI_ESCAPE_RE.sub('', content_row), inner - 2)} {C_RESET}"
            lines.append(f"│{content_row}│")
        else:
            lines.append(f"│ {pad_to_width(content_row, inner - 2)} │")

    empty_needed = avail_rows - len(view_rows)
    for _ in range(empty_needed):
        lines.append(f"│{' ' * inner}│")

    lines.append(f"├{'─' * inner}┤")
    avail_f_w = max(1, inner - 4)
    if isinstance(footer, (list, tuple)):
        f_styled = fit_hints(list(footer), avail_f_w, ellipsis=False)
    elif footer:
        f_styled = truncate_to_width(footer, avail_f_w)
    else:
        f_styled = ""
    lines.append(f"│ {pad_to_width(f_styled, inner - 1)}│")
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

def heal_bindings(bindings: list) -> list:
    """Löst Doppelbelegungen deterministisch auf und garantiert ein
    konfliktfreies Ergebnis: Verlierer-Aktionen fallen auf ihren Standard
    zurück; ist der selbst belegt, auf den nächsten freien Standard.
    Letzte Absicherung sind die garantiert konfliktfreien KEY_BINDINGS."""
    if _bindings_valid(bindings):
        return bindings
    seen = {}
    healed = []
    for row in bindings:
        section, action, disp, keys, desc = row
        clean = []
        for k in keys:
            if k in seen and seen[k] != action:
                continue
            seen[k] = action
            clean.append(k)
        if not clean:
            for dk in cur_default_keys(action):
                if dk not in seen:
                    seen[dk] = action
                    clean.append(dk)
                    break
        healed.append((section, action, disp, clean, desc))
    if not _bindings_valid(healed):
        healed = list(KEY_BINDINGS)
    return healed


def cur_default_keys(action: str) -> list:
    """Liefert die Standard-Tasten einer Aktion (Fallback, wenn eine Aktion
    durch Übernehmen ihrer letzten Taste leer würde)."""
    for _s, a, _d, keys, _desc in KEY_BINDINGS:
        if a == action:
            return list(keys)
    return []


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
        # würde sonst den Start des Dateimanagers verhindern. Sollte trotz
        # der automatischen Übernahme-Logik ein Konflikt bestehen (z. B. aus
        # einer historisch kaputten Config), wird er hier selbstheilend
        # aufgelöst: Doppel-Tasten fallen auf den Standard der Aktion zurück.
        editable_bindings[:] = heal_bindings(editable_bindings)
        json_bindings = []
        for section, action, disp, keys, desc in editable_bindings:
            json_bindings.append([section, action, disp, list(keys), desc])
        cfg["keybindings"] = json_bindings
        save_config(cfg)
        return True

    idx = 0
    status_hint = ""

    while True:
        # Menüeintraege vorbereiten: (key, label, value)
        binding_rows = []
        for section, action, disp, keys, desc in editable_bindings:
            binding_rows.append((action, f"{section}: {disp}", f"[{format_keys(keys)}]"))

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
        k = _warte_auf_taste(fd)
        if k == "resize":
            continue
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
            # ESC verlaesst das Menue IMMER. Scheitert das Speichern (was
            # durch die Selbstheilung praktisch ausgeschlossen ist), wird
            # der Standard gespeichert statt den Ausgang zu blockieren.
            save_editable_bindings()
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
                save_editable_bindings()
                break

            else:
                # Tastenbelegung für diese Aktion bearbeiten
                backup = list(editable_bindings)
                for i, (section, action, disp, keys, desc) in enumerate(editable_bindings):
                    if action == selected_action:
                        render_box(
                            f"TASTEN FÜR '{disp}' ÄNDERN",
                            "Drücken Sie die neue Taste oder Tastenkombination (ESC zum Abbrechen)",
                            [],
                            0,
                            [("Aktuell:", format_keys(keys), "")]
                        )

                        # Warten auf neue Tastenbelegung
                        new_key = ""
                        while True:
                            key_press = _warte_auf_taste(fd)
                            if key_press == "ESC":
                                break
                            elif key_press:
                                new_key = key_press
                                break

                        if new_key and new_key not in ("", "resize", "UNBEKANNT"):
                            # Belegte Taste automatisch übernehmen: Die alte
                            # Aktion verliert diese Taste (wie in modernen
                            # Editoren). Konflikte sind damit unmöglich, die
                            # Validierung kann nie mehr scheitern.
                            taken_from = []
                            for j, (sec2, act2, disp2, keys2, desc2) in enumerate(editable_bindings):
                                if j == i:
                                    continue
                                if new_key in keys2:
                                    rest = tuple(k for k in keys2 if k != new_key)
                                    taken_from.append(disp2)
                                    editable_bindings[j] = (sec2, act2, disp2, list(rest), desc2)
                            editable_bindings[i] = (section, action, disp, [new_key], desc)
                            editable_bindings[:] = heal_bindings(editable_bindings)
                            shown_key = format_keys([new_key])
                            if taken_from:
                                status_hint = f"{C_BOLD}✓ '{disp}' auf [{shown_key}] gesetzt (von {', '.join(taken_from)} übernommen){C_RESET}"
                            else:
                                status_hint = f"{C_BOLD}✓ '{disp}' auf [{shown_key}] gesetzt{C_RESET}"
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
        k = _warte_auf_taste(fd)
        if k == "resize":
            continue
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
        k = _warte_auf_taste(fd)
        if k == "resize":
            continue
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
    "preview_wrap": lambda cfg: f"[{'ein' if cfg.get('preview_wrap', True) else 'aus'}]",
    "sort": lambda cfg: "[öffnen]",
    "editor": lambda cfg: f"[{editor_command(cfg)}]",
    "keybindings": lambda cfg: f"[{len(cfg.get('schnellstart_eintraege') or cfg.get('__ss_default', []) or [])}]" if False else "[öffnen]",
    "schnellstart": lambda cfg: f"[{len(cfg.get('schnellstart_eintraege') or [])}]" if cfg.get('schnellstart_eintraege') else "[öffnen]",
    "reset": lambda cfg: "[standard]",
}

# Umschalt- und Rotationsaktionen des Hauptmenüs (datengetrieben)


def _cycle_option(cfg: dict, key: str, options: list, step: int) -> None:
    cur = cfg.get(key, options[0])
    cur_i = options.index(cur) if cur in options else 0
    cfg[key] = options[(cur_i + step) % len(options)]


def _toggle_option(cfg: dict, key: str, default: bool) -> None:
    cfg[key] = not cfg.get(key, default)


def _schnellstart_default_eintraege():
    from easydateien_common import DEFAULT_CONFIG
    return DEFAULT_CONFIG.get("schnellstart_eintraege", [])


def _lies_text(fd: int, prompt: str, vorgabe: str = "") -> str:
    """Liest eine Textzeile im Konfigurator-Stil (einfaches cbreak-Lesen)."""
    render_box("EINGABE", prompt, [], 0, [f"[ESC] Abbrechen"])
    row = vorgabe
    # Erste Eingabe ersetzt die Vorgabe ( intuitive Bearbeitung: einfach
    # los-tippen ueberschreibt; nur ENTER ohne Eingabe uebernimmt die Vorgabe).
    ersetzt = not vorgabe
    while True:
        k = _warte_auf_taste(fd)
        if k == "resize":
            render_box("EINGABE", f"{prompt}: {row}", [], 0, ["[Eingabe] Bestätigen", "[ESC] Abbrechen"])
            continue
        if k == "ENTER":
            return row
        if k in ("ESC", "q"):
            return None
        elif k == "BACKSPACE":
            row = row[:-1]
            ersetzt = True
        elif k in ("DELETE",):
            row = ""
            ersetzt = True
        elif k == "SPACE":
            if not ersetzt:
                row = ""
                ersetzt = True
            row += " "
        elif k and len(k) == 1 and k.isprintable():
            if not ersetzt:
                row = ""
                ersetzt = True
            row += k
        render_box("EINGABE", f"{prompt}: {row}", [], 0, ["[Eingabe] Bestätigen", "[ESC] Abbrechen"])


def _bearbeite_liste(fd, titel: str, liste: list, allow_untermenu: bool = True) -> "tuple[bool, list] | None":
    """Intuitiver Editor fuer eine Eintragsliste (Haupt- oder Untermenü).

    Gibt zurück: (veraendert, liste) oder None bei ESC/Abbruch.
    Enter auf Eintrag: bearbeiten (Untermenü-Eintrag öffnet dessen Liste).
    'add' legt neue Einträge an; 'addmenu' (nur Hauptebene) ein Untermenü."""
    idx = 0
    veraendert = False
    while True:
        rows = []
        for nr, e in enumerate(liste, 1):
            sub = e.get("untermenu")
            if sub:
                rows.append((str(nr), e.get("titel", ""), f"[{len(sub)} Untermenü]"))
            else:
                rows.append((str(nr), e.get("titel", ""), e.get("befehl", "")))
        rows.append(("add", "Neuen Eintrag hinzufügen", "[neu]"))
        if allow_untermenu:
            rows.append(("addmenu", "Neues Untermenü hinzufügen", "[menü]"))
        rows.append(("del", "Eintrag löschen", "[löschen]"))
        start, count = render_box(
            titel,
            "Titel und Befehl je Zeile; [Eingabe] bearbeitet",
            rows, idx,
            [("[↑↓] Navigieren", "[↑↓] Nav", "[↑↓]"),
             ("[Eingabe] Aktion", "[Eingabe]", "[Ent]"),
             ("[ESC] Zurück", "[ESC]", "[ESC]")]
        )
        k = ""
        while not k:
            k = _warte_auf_taste(fd)
        if k == "resize":
            continue
        if k in ("ESC", "q"):
            return (veraendert, liste) if veraendert else None
        if k in ("UP", "WHEEL_UP"):
            idx = max(0, idx - 1)
        elif k in ("DOWN", "WHEEL_DOWN"):
            idx = min(len(rows) - 1, idx + 1)
        elif k == "PAGE_UP":
            idx = max(0, idx - 8)
        elif k == "PAGE_DOWN":
            idx = min(len(rows) - 1, idx + 8)
        elif k in ("ENTER", "SPACE", "RIGHT"):
            aktion = rows[idx][0]
            if aktion.isdigit() and 1 <= int(aktion) <= len(liste):
                pos = int(aktion) - 1
                alt = liste[pos]
                sub = alt.get("untermenu")
                if sub:
                    erg = _bearbeite_liste(fd, f"UNTTERMENÜ: {alt.get('titel', '')}", sub, allow_untermenu=True)
                    if erg is not None:
                        _, alt["untermenu"] = erg[0], erg[1]
                        veraendert = True
                    continue
                neuer_titel = _lies_text(fd, "Bezeichnung eingeben", alt.get("titel", ""))
                if neuer_titel is None:
                    continue
                if neuer_titel.strip():
                    alt["titel"] = neuer_titel.strip()
                    veraendert = True
                neuer_befehl = _lies_text(fd, "Befehl eingeben", alt.get("befehl", ""))
                if neuer_befehl is None:
                    continue
                if neuer_befehl.strip():
                    alt["befehl"] = neuer_befehl.strip()
                    veraendert = True
                continue
            if aktion == "add":
                titel_neu = _lies_text(fd, "Bezeichnung eingeben")
                if not titel_neu or not titel_neu.strip():
                    continue
                befehl_neu = _lies_text(fd, "Befehl eingeben")
                if befehl_neu is None:
                    continue
                liste.append({"titel": titel_neu.strip(), "befehl": befehl_neu.strip() if befehl_neu else ""})
                veraendert = True
            elif aktion == "addmenu":
                titel_neu = _lies_text(fd, "Untermenü-Bezeichnung eingeben")
                if not titel_neu or not titel_neu.strip():
                    continue
                liste.append({"titel": titel_neu.strip(), "untermenu": []})
                veraendert = True
                # Direkt ins neue Untermenü springen:
                neu = liste[-1]
                erg = _bearbeite_liste(fd, f"UNTTERMENÜ: {neu['titel']}", neu["untermenu"], allow_untermenu=True)
                if erg is not None:
                    neu["untermenu"] = erg[1]
            elif aktion == "del" and liste:
                del_rows = [(str(nr), e.get("titel", ""), "") for nr, e in enumerate(liste, 1)]
                del_rows.append(("abort", "Abbrechen", ""))
                d_idx = 0
                while True:
                    start, count = render_box("EINTRAG LÖSCHEN", "Welchen Eintrag löschen?", del_rows, d_idx,
                                              [("[Eingabe] Löschen", "[Ent] Löschen", "[Ent]"),
                                               ("[ESC] Abbrechen", "[ESC]", "[ESC]")])
                    dk = ""
                    while not dk:
                        dk = _warte_auf_taste(fd)
                    if dk == "resize":
                        continue
                    if dk in ("ESC", "q"):
                        break
                    if dk in ("UP", "WHEEL_UP"):
                        d_idx = max(0, d_idx - 1)
                    elif dk in ("DOWN", "WHEEL_DOWN"):
                        d_idx = min(len(del_rows) - 1, d_idx + 1)
                    elif dk in ("ENTER", "SPACE"):
                        wahl = del_rows[d_idx][0]
                        if wahl == "abort":
                            break
                        if wahl.isdigit() and 1 <= int(wahl) <= len(liste):
                            del liste[int(wahl) - 1]
                            veraendert = True
                            if idx >= len(liste) + (3 if allow_untermenu else 2):
                                idx = max(0, len(liste) + (2 if allow_untermenu else 1))
                        break


def edit_schnellstart_menu(fd: int):
    """Einfacher, intuitiver Editor für die Schnellstart-Einträge:
    Ansehen, Hinzufügen (Titel + Befehl), Löschen, Auf Standard setzen.
    Untermenüs werden mit [Eingabe] direkt bearbeitet (rekursiv)."""
    cfg = load_config()
    idx = 0
    while True:
        eintraege = cfg.get("schnellstart_eintraege") or _schnellstart_default_eintraege()
        rows = []
        for nr, e in enumerate(eintraege, 1):
            sub = e.get("untermenu")
            if sub:
                rows.append((str(nr), e.get("titel", ""), f"[{len(sub)} Untermenü]"))
            else:
                rows.append((str(nr), e.get("titel", ""), e.get("befehl", "")))
        rows.append(("add", "Neuen Eintrag hinzufügen", "[neu]"))
        rows.append(("addmenu", "Neues Untermenü hinzufügen", "[menü]"))
        rows.append(("del", "Eintrag löschen", "[löschen]"))
        rows.append(("reset", "Auf Standard-Einträge zurücksetzen", "[standard]"))
        start, count = render_box(
            "SCHNELLSTART-EINTRÄGE",
            "Titel und Befehl je Zeile; Untermenüs mit [Eingabe] bearbeiten",
            rows, idx,
            [("[↑↓] Navigieren", "[↑↓] Nav", "[↑↓]"),
             ("[Eingabe] Aktion", "[Eingabe]", "[Ent]"),
             ("[ESC] Zurück", "[ESC]", "[ESC]")]
        )
        k = ""
        while not k:
            k = _warte_auf_taste(fd)
        if k == "resize":
            continue
        if k in ("ESC", "q"):
            return
        elif k in ("UP", "WHEEL_UP"):
            idx = max(0, idx - 1)
        elif k in ("DOWN", "WHEEL_DOWN"):
            idx = min(len(rows) - 1, idx + 1)
        elif k == "PAGE_UP":
            idx = max(0, idx - 8)
        elif k == "PAGE_DOWN":
            idx = min(len(rows) - 1, idx + 8)
        elif k in ("ENTER", "SPACE", "RIGHT"):
            aktion = rows[idx][0]
            if aktion.isdigit() and 1 <= int(aktion) <= len(eintraege):
                pos = int(aktion) - 1
                alt = eintraege[pos]
                if alt.get("untermenu") is not None:
                    # Untermenü-Eintrag: rekursiv bearbeiten (Einträge darin
                    # hinzufügen/bearbeiten/löschen), Titel bleibt hier über
                    # die normale Bezeichnungs-Eingabe änderbar.
                    neuer_titel = _lies_text(fd, "Bezeichnung eingeben", alt.get("titel", ""))
                    if neuer_titel is not None and neuer_titel.strip():
                        alt["titel"] = neuer_titel.strip()
                        cfg["schnellstart_eintraege"] = eintraege
                        save_config(cfg)
                    erg = _bearbeite_liste(fd, f"UNTTERMENÜ: {alt.get('titel', '')}", alt["untermenu"], allow_untermenu=True)
                    if erg is not None and erg[0]:
                        alt["untermenu"] = erg[1]
                        cfg["schnellstart_eintraege"] = eintraege
                        save_config(cfg)
                    continue
                # Bestehenden Eintrag bearbeiten: Bezeichnung, dann Befehl;
                # leere Eingabe uebernimmt den vorhandenen Wert (unveraendert).
                neuer_titel = _lies_text(fd, "Bezeichnung eingeben", alt.get("titel", ""))
                if neuer_titel is None:
                    continue
                if neuer_titel.strip():
                    alt["titel"] = neuer_titel.strip()
                if "untermenu" not in alt:
                    neuer_befehl = _lies_text(fd, "Befehl eingeben", alt.get("befehl", ""))
                    if neuer_befehl is None:
                        continue
                    if neuer_befehl.strip():
                        alt["befehl"] = neuer_befehl.strip()
                cfg["schnellstart_eintraege"] = eintraege
                save_config(cfg)
                continue
            if aktion == "add":
                titel = _lies_text(fd, "Titel des neuen Eintrags")
                if not titel:
                    continue
                befehl = _lies_text(fd, "Befehl (z. B. open -a Safari)")
                if befehl is None:
                    continue
                eintraege.append({"titel": titel, "befehl": befehl.strip() if befehl else ""})
                cfg["schnellstart_eintraege"] = eintraege
                save_config(cfg)
            elif aktion == "addmenu":
                titel = _lies_text(fd, "Untermenü-Bezeichnung eingeben")
                if not titel:
                    continue
                neu = {"titel": titel, "untermenu": []}
                eintraege.append(neu)
                cfg["schnellstart_eintraege"] = eintraege
                save_config(cfg)
                erg = _bearbeite_liste(fd, f"UNTTERMENÜ: {titel}", neu["untermenu"], allow_untermenu=True)
                if erg is not None and erg[0]:
                    neu["untermenu"] = erg[1]
                    cfg["schnellstart_eintraege"] = eintraege
                    save_config(cfg)
            elif aktion == "del" and eintraege:
                del_rows = [(str(nr), e.get("titel", ""), "") for nr, e in enumerate(eintraege, 1)]
                del_rows.append(("abort", "Abbrechen", ""))
                d_idx = 0
                gewählt = None
                while gewählt is None:
                    start, count = render_box("EINTRAG LÖSCHEN", "Welchen Eintrag löschen?", del_rows, d_idx,
                                              [("[Eingabe] Löschen", "[Ent] Löschen", "[Ent]"), ("[ESC] Abbrechen", "[ESC]", "[ESC]")])
                    dk = ""
                    while not dk:
                        dk = _warte_auf_taste(fd)
                    if dk == "resize":
                        continue
                    if dk in ("ESC", "q"):
                        break
                    elif dk in ("UP", "WHEEL_UP"):
                        d_idx = max(0, d_idx - 1)
                    elif dk in ("DOWN", "WHEEL_DOWN"):
                        d_idx = min(len(del_rows) - 1, d_idx + 1)
                    elif dk in ("ENTER", "SPACE"):
                        wahl = del_rows[d_idx][0]
                        if wahl != "abort" and wahl.isdigit() and 1 <= int(wahl) <= len(eintraege):
                            gewählt = int(wahl) - 1
                        else:
                            break
                if gewählt is not None:
                    del eintraege[gewählt]
                    cfg["schnellstart_eintraege"] = eintraege
                    save_config(cfg)
                    if idx >= len(eintraege) + 3:
                        idx = max(0, len(eintraege) + 2)
            elif aktion == "reset":
                cfg["schnellstart_eintraege"] = _schnellstart_default_eintraege()
                save_config(cfg)
                idx = 0


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
        k = _warte_auf_taste(fd)
        if k == "resize":
            continue
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
            elif act == "schnellstart":
                if k == "LEFT":
                    break
                else:
                    edit_schnellstart_menu(fd)
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
                        k2 = _warte_auf_taste(fd)
                    if k2 in ("y", "Y"):
                        cfg = dict(DEFAULT_CONFIG)
                        save_config(cfg)
                        status_hint = f"{C_BOLD}✓ Auf Standardwerte zurückgesetzt{C_RESET}"
                    else:
                        status_hint = "Zurücksetzen abgebrochen"
    return cfg

# Self-Pipe-Muster: Das Signal schreibt sofort ein Byte in eine Pipe, auf
# der select() mitwacht. Dadurch reagiert das Warten ohne Poll-Takt und ohne
# Verzoegerung auf Resize (PEP 475 wuerde sonst den Timeout trotz Signal
# abwarten -> traege Darstellung beim Fensterziehen).
_RESIZE_PIPE = os.pipe()


def _bei_resize(signum, frame):
    """Terminalgroesse geaendert: sofortiges Aufwecken des Wartens."""
    try:
        os.write(_RESIZE_PIPE[1], b"r")
    except OSError:
        pass


def _warte_auf_taste(fd: int) -> str:
    """Wartet auf eine Taste ODER einen Fenster-Resize und meldet beides.

    select() wacht gleichzeitig auf Tastatur und Resize-Pipe; ein Resize
    weckt sofort (kein Poll-Takt, keine Verzoegerung). Gibt 'resize'
    zurueck, wenn sich die Terminalgroesse geaendert hat."""
    try:
        while True:
            r, _, _ = select.select([fd, _RESIZE_PIPE[0]], [], [])
            if _RESIZE_PIPE[0] in r:
                try:
                    os.read(_RESIZE_PIPE[0], 64)
                except OSError:
                    pass
                return "resize"
            if fd in r:
                k = read_key(fd, timeout=0.05)
                if k:
                    return k
    except InterruptedError:
        return "resize"


def run_konfigurator(standalone: bool = True):
    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    tty.setcbreak(fd, termios.TCSADRAIN)
    try:
        import signal as _signal
        _signal.signal(_signal.SIGWINCH, _bei_resize)
    except Exception:
        pass
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
