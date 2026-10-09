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

def read_key(fd: int, timeout: float = 0.05) -> str:
    try:
        r, _, _ = select.select([fd], [], [], timeout)
        if not r: return ""
        raw = os.read(fd, 1)
        if not raw: return ""
        if raw == b"\x1b":
            seq = b""
            while True:
                r2, _, _ = select.select([fd], [], [], 0.03)
                if not r2: break
                c = os.read(fd, 1)
                if not c: break
                seq += c
                if seq.startswith(b"[<"):
                    if seq.endswith(b"M") or seq.endswith(b"m") or len(seq) >= 30: break
                elif len(seq) >= 2 and seq[-1:] in b"ABCDHFS~": break
                elif len(seq) >= 6: break
            if not seq: return "ESC"
            if seq.startswith(b"[<") and (seq.endswith(b"M") or seq.endswith(b"m")):
                try:
                    is_rel = seq.endswith(b"m")
                    b_s, x_s, y_s = seq[2:-1].decode("ascii").split(";")
                    b_c = int(b_s)
                    if b_c == 64: return "WHEEL_UP"
                    elif b_c == 65: return "WHEEL_DOWN"
                    elif not is_rel and b_c == 0: return f"CLICK:{int(x_s)}:{int(y_s)}"
                except Exception: pass
                return "MOUSE"
            mapping = {b"[A":"UP", b"[B":"DOWN", b"[C":"RIGHT", b"[D":"LEFT", b"[H":"HOME", b"[F":"END", b"[5~":"PAGE_UP", b"[6~":"PAGE_DOWN"}
            return mapping.get(seq, "")
        if raw in (bytes([13]), bytes([10])): return "ENTER"
        elif raw == b" ": return "SPACE"
        elif raw == b"\t": return "TAB"
        elif raw in (bytes([3]), bytes([4])): return "QUIT"
        try: return raw.decode("utf-8")
        except Exception: return ""
    except Exception: return ""

def render_box(title: str, subtitle: str, rows: list, cur_idx: int, footer: str):
    term_cols, term_rows = shutil.get_terminal_size((80, 24))
    # Exakte Box-Breite: Niemals größer als das Terminal (verhindert Zeilenumbruch)
    box_w = max(24, min(term_cols, 74))
    inner = max(4, box_w - 2)
    fixed_h = 7
    avail_items = max(3, term_rows - fixed_h)
    if len(rows) > avail_items:
        start = max(0, min(cur_idx - avail_items // 2, len(rows) - avail_items))
        view_rows = rows[start : start + avail_items]
    else:
        start = 0
        view_rows = rows

    lines = []
    lines.append("╭" + "─" * inner + "╮")
    t_disp = title if len(title) <= inner - 4 else title[:inner - 6] + ".."
    lines.append("│  " + t_disp + " " * (inner - 2 - len(t_disp)) + "│")
    s_disp = subtitle if len(subtitle) <= inner - 4 else subtitle[:inner - 6] + ".."
    lines.append("│  " + s_disp + " " * (inner - 2 - len(s_disp)) + "│")
    lines.append("├" + "─" * inner + "┤")
    for i, (key, label, tag) in enumerate(view_rows):
        actual_idx = start + i
        is_sel = (actual_idx == cur_idx)
        pfx = "  ▸ " if is_sel else "    "
        tag_str = f" {tag}" if tag else ""
        avail_lbl = max(2, inner - len(pfx) - len(tag_str))
        lbl_trunc = label if len(label) <= avail_lbl else label[:avail_lbl - 2] + ".."
        pad = " " * max(0, avail_lbl - len(lbl_trunc))
        content = f"{pfx}{lbl_trunc}{pad}{tag_str}"
        if len(content) > inner: content = content[:inner]
        elif len(content) < inner: content += " " * (inner - len(content))
        if is_sel: lines.append(f"│\033[1m{content}\033[0m│")
        else: lines.append(f"│{content}│")
    lines.append("├" + "─" * inner + "┤")
    f_disp = footer if len(footer) <= inner - 4 else footer[:inner - 6] + ".."
    lines.append("│  " + f_disp + " " * (inner - 2 - len(f_disp)) + "│")
    lines.append("╰" + "─" * inner + "╯")

    # Atomar ohne Scrollen zeichnen: \033[J tilgt alle Geisterlinien unter der Box!
    out = ["\033[H"]
    for i, l in enumerate(lines[:term_rows]):
        if i > 0: out.append("\n")
        out.append(f"\r\033[2K{l}")
    out.append("\033[J")
    sys.stdout.write("".join(out))
    sys.stdout.flush()
    return start, len(view_rows)

def keybindings_menu(fd: int):
    idx = 0
    while True:
        start, count = render_box(
            "TASTENBELEGUNGEN BEARBEITEN",
            "Übersicht der aktiven Tastenkürzel",
            KEYBINDING_ITEMS,
            idx,
            "[↑/↓/j/k] Navigieren  [Enter/→] Auswählen  [ESC/q] Zurück"
        )
        k = read_key(fd)
        if not k: continue
        if k in ("UP", "k", "WHEEL_UP"): idx = max(0, idx - 1)
        elif k in ("DOWN", "j", "WHEEL_DOWN"): idx = min(len(KEYBINDING_ITEMS) - 1, idx + 1)
        elif k in ("ESC", "q"): break
        elif k.startswith("CLICK:"):
            try:
                _, cx_s, cy_s = k.split(":")
                cy = int(cy_s)
                row_i = cy - 1 - 4
                if 0 <= row_i < count:
                    target = start + row_i
                    if target == idx: k = "ENTER"
                    else: idx = target
            except Exception: pass
        if k in ("ENTER", "SPACE", "RIGHT"):
            act = KEYBINDING_ITEMS[idx][0]
            if act in ("back", "reset"):
                if act == "reset": save_config(dict(DEFAULT_CONFIG))
                break

def main_menu(fd: int):
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
        start, count = render_box(
            "EASYDATEIEN KONFIGURATION",
            "Einstellungen verwalten und anpassen",
            rows,
            idx,
            "[↑/↓/j/k] Navigieren  [Enter/Leertaste] Umschalten  [ESC/q] Beenden"
        )
        k = read_key(fd)
        if not k: continue
        if k in ("UP", "k", "WHEEL_UP"): idx = max(0, idx - 1)
        elif k in ("DOWN", "j", "WHEEL_DOWN"): idx = min(len(rows) - 1, idx + 1)
        elif k in ("ESC", "q"): break
        elif k.startswith("CLICK:"):
            try:
                _, cx_s, cy_s = k.split(":")
                cy = int(cy_s)
                row_i = cy - 1 - 4
                if 0 <= row_i < count:
                    target = start + row_i
                    if target == idx: k = "ENTER"
                    else: idx = target
            except Exception: pass
        if k in ("ENTER", "SPACE", "RIGHT"):
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
                keybindings_menu(fd)
                cfg = load_config()
            elif act == "reset":
                cfg = dict(DEFAULT_CONFIG); save_config(cfg)
            elif act == "quit": break
    return cfg

def run_konfigurator(standalone: bool = True):
    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    tty.setcbreak(fd, termios.TCSADRAIN)
    sys.stdout.write("\033[?1049h\033[?25l\033[?1000h\033[?1006h\033[2J\033[H")
    sys.stdout.flush()
    try:
        cfg = main_menu(fd)
        return cfg
    finally:
        sys.stdout.write("\033[?1006l\033[?1000l\033[?25h\033[?1049l")
        sys.stdout.flush()
        termios.tcsetattr(fd, termios.TCSADRAIN, old)

if __name__ == "__main__":
    run_konfigurator(standalone=True)
