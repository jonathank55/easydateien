#!/usr/bin/env python3
import os, sys, json, termios, tty, select, shutil

CONFIG_DIR = os.path.expanduser("~/.config/easydateien")
CONFIG_FILE = os.path.join(CONFIG_DIR, "config.json")

DEFAULT_CONFIG = {
    "divider_style": "alle", "columns_enabled": True, "show_controls": False,
    "esc_to_quit": False, "mouse_support": True, "show_console": False,
    "console_position": "unten", "text_editor": "nano %s", "opener": "open %s",
    "sort_by": "mtime", "sort_reverse": True, "sort_dir_first": True,
}

KEYBINDING_ITEMS = [
    ("up", "Cursor nach oben bewegen", "[UP, k]"),
    ("down", "Cursor nach unten bewegen", "[DOWN, j]"),
    ("left", "Übergeordnetes Verzeichnis (Zurück)", "[LEFT, h]"),
    ("right", "Ordner öffnen (Datei: Doppel-→ für nano)", "[RIGHT, l]"),
    ("open", "Systemweit öffnen (open, Finder)", "[ENTER]"),
    ("select", "Element auswählen / abwählen (*)", "[SPACE, v]"),
    ("select_all", "Alle Elemente auswählen / abwählen", "[V, a]"),
    ("cut", "Auswahl ausschneiden (×)", "[x]"),
    ("copy", "Auswahl kopieren / yank (y / c)", "[y, c]"),
    ("paste", "Zwischenspeicher einfügen (p)", "[p]"),
    ("trash", "In den Papierkorb verschieben (d)", "[d]"),
    ("toggle_hidden", "Versteckte Dateien umschalten (./z)", "[., z]"),
    ("menu", "Konfigurationsmenü öffnen (m)", "[m, C]"),
    ("goto_downloads", "Gehe zu Downloads (g d)", "[gd]"),
    ("goto_documents", "Gehe zu Dokumente (g f)", "[gf]"),
    ("goto_home", "Gehe zu Home-Verzeichnis (g h / ~)", "[gh, ~]"),
    ("goto_trash", "Gehe zum Papierkorb (g t)", "[gt]"),
    ("goto_input", "Pfad manuell eingeben (g i)", "[gi]"),
    ("goto_clipboard", "Gehe zu Pfad in Zwischenablage (g p)", "[gp]"),
    ("create_zip", "ZIP-Archiv erstellen (c z)", "[cz]"),
    ("toggle_console", "Konsole anzeigen / ausblenden (t)", "[t]"),
    ("quit", "EasyDateien beenden (q)", "[q]"),
    ("reset", "Tastenbelegungen zurücksetzen", "[Standard]"),
    ("back", "Zurück zum Hauptmenü", "[Zurück]"),
]

def load_config() -> dict:
    cfg = dict(DEFAULT_CONFIG)
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f: cfg.update(json.load(f))
        except Exception: pass
    return cfg

def save_config(cfg: dict):
    os.makedirs(CONFIG_DIR, exist_ok=True)
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2, ensure_ascii=False)

def read_key():
    fd = sys.stdin.fileno()
    r, _, _ = select.select([fd], [], [], 0.05)
    if not r: return ""
    ch = os.read(fd, 1)
    if ch == b"\x1b":
        seq = b""
        while True:
            r2, _, _ = select.select([fd], [], [], 0.03)
            if not r2: break
            seq += os.read(fd, 1)
        if not seq: return "ESC"
        if seq == b"[A": return "UP"
        if seq == b"[B": return "DOWN"
        if seq == b"[C": return "RIGHT"
        if seq == b"[D": return "LEFT"
        return "ESC"
    if ch in (b"\r", b"\n"): return "ENTER"
    try: return ch.decode("utf-8")
    except Exception: return ""

def render_box(title: str, subtitle: str, rows: list, cur_idx: int, footer: str):
    term_cols, term_rows = shutil.get_terminal_size((80, 24))
    box_w = max(40, min(term_cols, 80))
    inner = box_w - 2
    out = ["\033[H"]
    out.append("╭" + "─" * inner + "╮")
    out.append("│  " + title[:inner - 4].ljust(inner - 2) + "│")
    out.append("│  " + subtitle[:inner - 4].ljust(inner - 2) + "│")
    out.append("├" + "─" * inner + "┤")
    # Scrollbarer Inhaltsbereich bei kleiner Terminalhöhe
    avail_h = max(5, term_rows - 8)
    if len(rows) > avail_h:
        start = max(0, min(cur_idx - avail_h // 2, len(rows) - avail_h))
        view_rows = rows[start : start + avail_h]
    else:
        start = 0
        view_rows = rows
    for i, (key, label, tag) in enumerate(view_rows):
        actual_idx = start + i
        is_sel = (actual_idx == cur_idx)
        pfx = "  ▸ " if is_sel else "    "
        tag_str = f" {tag}"
        avail_lbl = max(4, inner - len(pfx) - len(tag_str) - 2)
        lbl_trunc = label if len(label) <= avail_lbl else label[:avail_lbl-2] + ".."
        pad = " " * max(1, inner - len(pfx) - len(lbl_trunc) - len(tag_str))
        content = f"{pfx}{lbl_trunc}{pad}{tag_str}"
        line_txt = content.ljust(inner)
        if is_sel: line_txt = "\033[1m" + line_txt + "\033[0m"
        out.append("│" + line_txt + "│")
    out.append("├" + "─" * inner + "┤")
    out.append("│  " + footer[:inner - 4].ljust(inner - 2) + "│")
    out.append("╰" + "─" * inner + "╯")
    for l in out[:term_rows]:
        sys.stdout.write(f"\r\033[2K{l}\n")
    sys.stdout.flush()

def keybindings_menu():
    idx = 0
    while True:
        render_box(
            "TASTENBELEGUNGEN BEARBEITEN",
            "Übersicht der aktiven Tastenkürzel",
            KEYBINDING_ITEMS,
            idx,
            "[↑/↓/j/k] Navigieren  [Enter/→] Auswählen  [ESC/q] Zurück"
        )
        k = read_key()
        if not k: continue
        if k in ("UP", "k"): idx = max(0, idx - 1)
        elif k in ("DOWN", "j"): idx = min(len(KEYBINDING_ITEMS) - 1, idx + 1)
        elif k in ("ESC", "q"): break
        elif k in ("ENTER", "RIGHT"):
            act = KEYBINDING_ITEMS[idx][0]
            if act in ("back", "reset"):
                if act == "reset": save_config(dict(DEFAULT_CONFIG))
                break

MAIN_MENU_ITEMS = [
    ("divider", "Trennungslinien-Stil", "alle"),
    ("columns", "3-Spalten-Layout", "Ein"),
    ("controls", "Steuerungshilfe unten", "Aus"),
    ("mouse", "Mausunterstützung", "Ein"),
    ("console", "Terminal-Konsole", "Aus"),
    ("keybindings", "Tastenbelegungen ansehen...", "Öffnen"),
    ("reset", "Auf Standardwerte zurücksetzen", "Standard"),
    ("quit", "Konfigurator beenden", "Beenden"),
]

def main_menu():
    cfg = load_config()
    idx = 0
    while True:
        rows = []
        for key, lbl, _ in MAIN_MENU_ITEMS:
            if key == "divider": val = f"[{cfg.get('divider_style', 'alle')}]"
            elif key == "columns": val = f"[{'Ein' if cfg.get('columns_enabled', True) else 'Aus'}]"
            elif key == "controls": val = f"[{'Ein' if cfg.get('show_controls', False) else 'Aus'}]"
            elif key == "mouse": val = f"[{'Ein' if cfg.get('mouse_support', True) else 'Aus'}]"
            elif key == "console": val = f"[{'Ein' if cfg.get('show_console', False) else 'Aus'}]"
            elif key == "keybindings": val = "[Öffnen]"
            elif key == "reset": val = "[Standard]"
            elif key == "quit": val = "[Beenden]"
            else: val = ""
            rows.append((key, lbl, val))

        render_box(
            "EASYDATEIEN KONFIGURATION",
            "Einstellungen verwalten und anpassen",
            rows,
            idx,
            "[↑/↓/j/k] Navigieren  [Enter/Leertaste] Umschalten  [ESC/q] Beenden"
        )
        k = read_key()
        if not k: continue
        if k in ("UP", "k"): idx = max(0, idx - 1)
        elif k in ("DOWN", "j"): idx = min(len(rows) - 1, idx + 1)
        elif k in ("ESC", "q"): break
        elif k in ("ENTER", " ", "RIGHT"):
            act = rows[idx][0]
            if act == "divider":
                opts = ["alle", "vertikal", "horizontal", "außen", "keine"]
                cur = cfg.get("divider_style", "alle")
                cfg["divider_style"] = opts[(opts.index(cur) + 1) % len(opts)] if cur in opts else "alle"
                save_config(cfg)
            elif act == "columns":
                cfg["columns_enabled"] = not cfg.get("columns_enabled", True); save_config(cfg)
            elif act == "controls":
                cfg["show_controls"] = not cfg.get("show_controls", False); save_config(cfg)
            elif act == "mouse":
                cfg["mouse_support"] = not cfg.get("mouse_support", True); save_config(cfg)
            elif act == "console":
                cfg["show_console"] = not cfg.get("show_console", False); save_config(cfg)
            elif act == "keybindings":
                keybindings_menu()
                cfg = load_config()
            elif act == "reset":
                cfg = dict(DEFAULT_CONFIG); save_config(cfg)
            elif act == "quit": break
    return cfg

def run_konfigurator(standalone: bool = True):
    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    tty.setcbreak(fd, termios.TCSADRAIN)
    sys.stdout.write("\033[?1049h\033[?25l\033[2J\033[H")
    sys.stdout.flush()
    try:
        cfg = main_menu()
        return cfg
    finally:
        sys.stdout.write("\033[?25h\033[?1049l")
        sys.stdout.flush()
        termios.tcsetattr(fd, termios.TCSADRAIN, old)

if __name__ == "__main__":
    run_konfigurator(standalone=True)
