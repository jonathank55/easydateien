#!/usr/bin/env python3
"""EasyDateien — UI-Basis: Konstanten, Tastatur-/Terminal-Helfer und reine Rendering-Funktionen.

Entstanden durch mechanischen Modul-Split aus easydateien; die Logik ist unveraendert.
"""


import os
import sys
import time
import datetime
import shutil
import subprocess
import termios
import tty
import select
import signal
import zipfile
import re
import argparse
import stat
import shlex
from typing import List, Dict, Set, Optional, Tuple

from easydateien_common import (
    build_keymap,
    key_display,
    build_help_items,
    get_keybindings_from_config,
    frame_cell,
    cell_inner_width,
    load_config,
    ANSI_ESCAPE_RE,
    C_RESET,
    C_BOLD,
    C_DIM,
    C_ITALIC,
    C_INVERT,
    C_BLUE,
    C_BOLD_BLUE,
    C_CYAN,
    C_BOLD_CYAN,
    C_GREEN,
    C_BOLD_GREEN,
    C_YELLOW,
    C_BOLD_YELLOW,
    C_RED,
    C_BOLD_RED,
    C_GRAY,
    HIDE_CURSOR,
    SHOW_CURSOR,
    DISABLE_AUTOWRAP,
    ENABLE_AUTOWRAP,
    char_width,
    str_width,
    truncate_to_width,
    pad_to_width,
    safe_text,
    distribute_options,
    KEY_BINDINGS,
    KEY_LABELS,
    DEFAULT_CONFIG,
    format_keys,
    CONFIG_FILE,
)

#!/usr/bin/env python3
"""
EasyDateien — Minimalistischer, hocheffizienter Terminal-Dateimanager für macOS.
Single-Source-of-Truth & optimi-Norm konform.
"""

HOME_DIR = os.path.expanduser("~")
CONFIG_DIR = os.path.expanduser("~/.config/easydateien")
CLIP_HELPER_PATH = os.path.join(CONFIG_DIR, "easydateien_clip")

class UndoAction:
    """Repräsentiert eine umkehrbare Dateiaktion im Undo-Stack."""
    __slots__ = ("action_type", "description", "data")

    def __init__(self, action_type: str, description: str, data: dict):
        self.action_type = action_type
        self.description = description
        self.data = data

class FileEntry:
    __slots__ = ("name", "path", "is_dir", "is_symlink", "is_exec", "size", "mtime", "atime", "ext", "mode_str", "symlink_target", "is_broken")

    def __init__(self, path: str, name: str, dir_entry: Optional["os.DirEntry"] = None):
        self.path = path
        self.name = name
        self.is_dir = False
        self.is_symlink = False
        self.is_broken = False
        self.is_exec = False
        self.size = 0
        self.mtime = 0.0
        self.atime = 0.0
        self.mode_str = "----------"
        self.symlink_target = ""
        _, self.ext = os.path.splitext(name)
        try:
            if dir_entry is not None:
                self.is_symlink = dir_entry.is_symlink()
                st = dir_entry.stat(follow_symlinks=False)
            else:
                self.is_symlink = os.path.islink(path)
                st = os.stat(path, follow_symlinks=False)
            self.mtime = st.st_mtime
            self.atime = st.st_atime
            self.mode_str = stat.filemode(st.st_mode)
            self.size = st.st_size
            if self.is_symlink:
                try:
                    self.symlink_target = os.readlink(path)
                except OSError:
                    pass
                try:
                    tst = os.stat(path)  # folgt dem Link: Ziel-Typ und -Größe
                    self.is_dir = stat.S_ISDIR(tst.st_mode)
                    self.size = tst.st_size
                    self.is_exec = bool(tst.st_mode & (stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)) and not self.is_dir
                except OSError:
                    self.is_broken = True
            else:
                self.is_dir = stat.S_ISDIR(st.st_mode)
                self.is_exec = bool(st.st_mode & (stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)) and not self.is_dir
        except OSError:
            pass

_NATURAL_RE = re.compile(r"(\d+)")




def take_width(text: str, max_w: int) -> str:
    """Liefert das längste Präfix von text, das höchstens max_w Spalten belegt."""
    out = []
    w = 0
    for c in text:
        cw = char_width(c)
        if w + cw > max_w:
            break
        out.append(c)
        w += cw
    return "".join(out)

def truncate_left(text: str, max_w: int) -> str:
    """Kürzt am Anfang mit „…“ und behält das Ende (z. B. Pfade: der letzte Teil ist am wichtigsten)."""
    if max_w <= 0:
        return ""
    if str_width(text) <= max_w:
        return text
    if max_w == 1:
        return "…"
    out = []
    w = 0
    for c in reversed(text):
        cw = char_width(c)
        if w + cw > max_w - 1:
            break
        out.append(c)
        w += cw
    return "…" + "".join(reversed(out))

def split_name_ext(name: str, is_dir: bool) -> Tuple[str, str]:
    """Trennt einen Namen in (Stamm, Endung). Ordner haben „/“, Dateien ihre Endung (.tar.gz inklusive)."""
    if is_dir:
        return name, "/"
    stem, ext = os.path.splitext(name)
    if stem.lower().endswith(".tar") and ext:
        stem, ext = stem[:-4], ".tar" + ext
    if not stem or not ext or len(ext) > 16 or " " in ext:
        return name, ""
    return stem, ext

def truncate_name(name: str, is_dir: bool, max_w: int) -> str:
    """Kürzt einen Datei-/Ordnernamen mit „…“ so, dass die Endung (.txt) bzw. das „/“ nach dem „…“ erhalten bleibt."""
    if max_w <= 0:
        return ""
    name = safe_text(name)
    full = name + ("/" if is_dir else "")
    if str_width(full) <= max_w:
        return full
    stem, suffix = split_name_ext(name, is_dir)
    keep = max_w - str_width(suffix) - 1
    if suffix and keep >= 1:
        head = take_width(stem, keep)
        if head:
            return f"{head}…{suffix}"
    # Falls keep < 1, versuche trotzdem das Suffix zu behalten
    if suffix and is_dir:
        # Für Ordner: immer versuchen, mindestens ein Zeichen + "…/" oder ".../" zu zeigen
        # wenn max_w zu klein ist, zeige mindestens ".../" oder kürzer
        if max_w >= 2:
            # Versuche, mindestens ein Zeichen vom Namen zu behalten
            first_char = take_width(name, 1)
            if first_char and max_w >= 3:
                return f"{first_char}…{suffix}"
            elif max_w >= 2:
                return f"…{suffix}"
        elif max_w == 1:
            return suffix
    return truncate_to_width(full, max_w)

def render_input_field(text: str, cursor: int, width: int) -> str:
    """Zeichnet ein Eingabefeld mit invertiertem Cursor; zu lange Eingaben werden mit „…“ um den Cursor herum gekürzt."""
    if width <= 0:
        return ""
    cursor = max(0, min(cursor, len(text)))
    cur_raw = text[cursor] if cursor < len(text) else " "
    cur_ch = safe_text(cur_raw)
    cur_w = max(1, char_width(cur_ch))
    before = safe_text(text[:cursor])
    after = safe_text(text[cursor + 1:])
    bw, aw = str_width(before), str_width(after)
    if bw + cur_w + aw > width:
        a_budget = min(aw, max(0, (width - cur_w) // 3))
        b_budget = max(0, width - cur_w - a_budget)
        before = truncate_left(before, b_budget)
        after = truncate_to_width(after, max(0, width - cur_w - str_width(before)))
    return f"{before}{C_INVERT}{cur_ch}{C_RESET}{after}"

def wrap_line_to_width(text: str, max_w: int) -> List[str]:
    """Bricht eine Textzeile unter Beachtung von Wortgrenzen, visuellen Zeichenbreiten und ANSI-Sequenzen deterministisch auf max_w um."""
    if max_w <= 0:
        return [""]
    if not text:
        return [""]
    if str_width(text) <= max_w:
        return [text]

    lines = []
    cur_line = []
    cur_w = 0
    active_ansi = []

    tokens = re.split(r"(\s+)", text)
    for token in tokens:
        if not token:
            continue
        tw = str_width(token)
        if cur_w + tw <= max_w:
            cur_line.append(token)
            cur_w += tw
            for m in ANSI_ESCAPE_RE.finditer(token):
                esc = m.group(0)
                if esc in ("\033[0m", "\033[m"):
                    active_ansi.clear()
                else:
                    active_ansi.append(esc)
        else:
            if token.isspace():
                line_str = "".join(cur_line)
                lines.append(line_str)
                cur_line = list(active_ansi)
                cur_w = sum(char_width(x) for x in ANSI_ESCAPE_RE.sub("", "".join(cur_line)))
                continue

            if cur_line:
                line_str = "".join(cur_line)
                lines.append(line_str)
                cur_line = list(active_ansi)
                cur_w = sum(char_width(x) for x in ANSI_ESCAPE_RE.sub("", "".join(cur_line)))

            if tw <= max_w:
                cur_line.append(token)
                cur_w += tw
                for m in ANSI_ESCAPE_RE.finditer(token):
                    esc = m.group(0)
                    if esc in ("\033[0m", "\033[m"):
                        active_ansi.clear()
                    else:
                        active_ansi.append(esc)
            else:
                i = 0
                n = len(token)
                while i < n:
                    if token[i] == "\x1b":
                        m = ANSI_ESCAPE_RE.match(token, i)
                        if m:
                            esc = m.group(0)
                            cur_line.append(esc)
                            if esc in ("\033[0m", "\033[m"):
                                active_ansi.clear()
                            else:
                                active_ansi.append(esc)
                            i = m.end()
                            continue
                    c = token[i]
                    cw = char_width(c)
                    if cur_w + cw > max_w and cur_line:
                        line_str = "".join(cur_line)
                        lines.append(line_str)
                        cur_line = list(active_ansi)
                        cur_w = sum(char_width(x) for x in ANSI_ESCAPE_RE.sub("", "".join(cur_line)))
                    cur_line.append(c)
                    cur_w += cw
                    i += 1

    if cur_line:
        lines.append("".join(cur_line))
    res = [l for l in lines if l]
    return res if res else [""]

def get_shell_environment() -> Tuple[str, Dict[str, str]]:
    """Ermittelt die Benutzer-Shell und stellt einen vollständigen macOS-Umgebungs- und PATH-Satz bereit."""
    user_shell = os.environ.get("SHELL", "/bin/zsh")
    if not os.path.exists(user_shell):
        user_shell = "/bin/zsh" if os.path.exists("/bin/zsh") else "/bin/bash"

    env = os.environ.copy()
    env["SHELL_SESSIONS_DISABLE"] = "1"

    # Standard- und Homebrew-Pfade sicherstellen
    current_path = env.get("PATH", "")
    standard_paths = [
        os.path.expanduser("~/.local/bin"),
        os.path.expanduser("~/.antigravity-ide/antigravity-ide/bin"),
        "/opt/homebrew/bin",
        "/opt/homebrew/sbin",
        "/usr/local/bin",
        "/usr/bin",
        "/bin",
        "/usr/sbin",
        "/sbin",
    ]
    path_parts = [p for p in current_path.split(":") if p]
    for sp in standard_paths:
        if sp not in path_parts and os.path.exists(sp):
            path_parts.append(sp)
    env["PATH"] = ":".join(path_parts)
    # Geerbte Terminalgroessen-Variablen entfernen: shutil.get_terminal_size()
    # wertet COLUMNS/LINES vor dem ioctl aus; vererbte Werte vom aeusseren
    # Terminal wuerden die Panelbreite ueberschreiben (kuenstliche Mindest-
    # breite, falscher Umbruch). Ohne diese Variablen liest jedes Programm die
    # exakte, per TIOCSWINSZ gesetzte PTY-Breite.
    env.pop("COLUMNS", None)
    env.pop("LINES", None)
    return user_shell, env

def replace_ansi_range(base_line: str, start_col: int, replacement: str, repl_width: int, total_width: int) -> str:
    """Ersetzt in base_line den sichtbaren Spaltenbereich [start_col, start_col + repl_width] durch replacement."""
    clean_base = ANSI_ESCAPE_RE.sub("", base_line)
    base_w = str_width(clean_base)
    if base_w < total_width:
        base_line = pad_to_width(base_line, total_width)

    left_chars = []
    right_chars = []
    active_right = []
    cur_w = 0
    end_col = start_col + repl_width

    i = 0
    n = len(base_line)
    while i < n:
        if base_line[i] == "\x1b":
            m = ANSI_ESCAPE_RE.match(base_line, i)
            if m:
                esc = m.group(0)
                if cur_w < start_col:
                    left_chars.append(esc)
                if cur_w < end_col:
                    if esc in ("\033[0m", "\033[m"):
                        active_right.clear()
                    else:
                        active_right.append(esc)
                else:
                    right_chars.append(esc)
                i = m.end()
                continue
        c = base_line[i]
        cw = char_width(c)
        if cur_w + cw <= start_col:
            left_chars.append(c)
        elif cur_w >= end_col:
            right_chars.append(c)
        elif cur_w < start_col and cur_w + cw > start_col:
            left_chars.append(" " * (start_col - cur_w))
        cur_w += cw
        i += 1

    left_str = "".join(left_chars)
    right_raw = "".join(right_chars)
    right_str = ("".join(active_right) + right_raw) if right_raw else ""
    if ANSI_ESCAPE_RE.search(left_str) and not left_str.endswith(C_RESET):
        left_str += C_RESET

    left_pad = pad_to_width(left_str, start_col)
    right_w = max(0, total_width - end_col)
    right_pad = pad_to_width(right_str, right_w, align="right") if right_str else (" " * right_w)

    return f"{left_pad}{replacement}{right_pad}"

def build_modal_box(title: str, content_lines: List[str], target_w: int) -> Tuple[List[str], int]:
    """Baut ein standardisiertes Vordergrund-Modal im Yazi-Stil mit blauem Rahmen."""
    inner_w = max(20, target_w - 4)
    box_w = inner_w + 4
    t_clean = ANSI_ESCAPE_RE.sub("", title)
    t_w = str_width(t_clean)
    avail_d = max(2, box_w - 2 - t_w - 2)
    left_d = 2
    right_d = avail_d - left_d
    dash_l = "─" * left_d
    dash_r = "─" * right_d
    dash_b = "─" * (box_w - 2)
    res = [f"╭{dash_l} {t_clean} {dash_r}╮"]
    for l in content_lines:
        padded = pad_to_width(ANSI_ESCAPE_RE.sub("", l), inner_w)
        res.append(f"│ {padded} │")
    res.append(f"╰{dash_b}╯")
    res = [f"{C_BOLD}{C_INVERT}{pad_to_width(ANSI_ESCAPE_RE.sub('', line), box_w)}{C_RESET}" for line in res]
    return res, box_w

def format_size(size_bytes: int) -> str:
    """Formatiert Byte-Größen nach standardisierten Einheiten."""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    val = float(size_bytes)
    for unit in ["KB", "MB", "GB", "TB", "PB"]:
        val /= 1024.0
        if val < 1024.0 or unit == "PB":
            return f"{val:.1f} {unit}"
    return f"{val:.1f} PB"

def format_mtime(mtime: float, max_w: int = 17) -> str:
    """Formatiert Änderungszeitpunkte lesbar; bei engem Platz
    stufig auf Datum (ohne Uhrzeit) bzw. Jahr gekürzt — nie mitten im Wert."""
    try:
        dt = datetime.datetime.fromtimestamp(mtime)
        full = dt.strftime("%d.%m.%Y %H:%M")
        if str_width(full) <= max_w:
            return full
        date_only = dt.strftime("%d.%m.%Y")
        if str_width(date_only) <= max_w:
            return date_only
        year = dt.strftime("%Y")
        if str_width(year) <= max_w:
            return year
        return truncate_to_width(date_only, max_w)
    except Exception:
        return "---"

def ensure_clip_helper() -> Optional[str]:
    """Stellt sicher, dass das native macOS Clipboard-Helper-Tool kompiliert und bereit ist."""
    if os.path.exists(CLIP_HELPER_PATH) and os.access(CLIP_HELPER_PATH, os.X_OK):
        return CLIP_HELPER_PATH
    os.makedirs(os.path.dirname(CLIP_HELPER_PATH), exist_ok=True)
    c_code = """#import <AppKit/AppKit.h>
#import <Foundation/Foundation.h>
#import <ImageIO/ImageIO.h>

static const NSInteger kMaxClipboardPixelSize = 2048;

static BOOL easeIsImagePath(NSString *path) {
    NSString *ext = [[path pathExtension] lowercaseString];
    if ([ext isEqualToString:@"png"] || [ext isEqualToString:@"jpg"] ||
        [ext isEqualToString:@"jpeg"] || [ext isEqualToString:@"gif"] ||
        [ext isEqualToString:@"tiff"] || [ext isEqualToString:@"tif"] ||
        [ext isEqualToString:@"webp"] || [ext isEqualToString:@"heic"] ||
        [ext isEqualToString:@"heif"] || [ext isEqualToString:@"bmp"] ||
        [ext isEqualToString:@"avif"] || [ext isEqualToString:@"raw"]) {
        return YES;
    }
    return NO;
}

static CGImageRef easeScaledImageForPath(NSString *path) {
    if (!path || ![[NSFileManager defaultManager] fileExistsAtPath:path]) {
        return NULL;
    }
    NSURL *url = [NSURL fileURLWithPath:path];
    CGImageSourceRef source = CGImageSourceCreateWithURL((__bridge CFURLRef)url, NULL);
    if (!source) {
        return NULL;
    }
    NSDictionary *options = @{
        (id)kCGImageSourceCreateThumbnailFromImageAlways : @YES,
        (id)kCGImageSourceCreateThumbnailWithTransform : @YES,
        (id)kCGImageSourceThumbnailMaxPixelSize : @(kMaxClipboardPixelSize),
    };
    CGImageRef image = CGImageSourceCreateThumbnailAtIndex(source, 0, (__bridge CFDictionaryRef)options);
    CFRelease(source);
    return image;
}

int main(int argc, const char * argv[]) {
    @autoreleasepool {
        if (argc < 2) return 1;
        NSString *action = [NSString stringWithUTF8String:argv[1]];
        NSPasteboard *pb = [NSPasteboard generalPasteboard];

        if ([action isEqualToString:@"set"] && argc > 2) {
            [pb clearContents];
            NSMutableArray<NSString *> *paths = [NSMutableArray array];
            for (int i = 2; i < argc; i++) {
                NSString *p = [NSString stringWithUTF8String:argv[i]];
                [paths addObject:p];
            }

            NSMutableArray<NSPasteboardType> *types = [NSMutableArray arrayWithObjects:
                (NSPasteboardType)@"NSFilenamesPboardType",
                NSPasteboardTypeFileURL,
                NSPasteboardTypeString,
                nil
            ];

            NSData *pngData = nil;
            NSData *tiffData = nil;
            if ([paths count] == 1 && easeIsImagePath(paths[0])) {
                CGImageRef cgRef = easeScaledImageForPath(paths[0]);
                if (cgRef) {
                    NSBitmapImageRep *rep = [[NSBitmapImageRep alloc] initWithCGImage:cgRef];
                    pngData = [rep representationUsingType:NSBitmapImageFileTypePNG properties:@{}];
                    tiffData = [rep representationUsingType:NSBitmapImageFileTypeTIFF properties:@{}];
                    if (pngData) [types addObject:NSPasteboardTypePNG];
                    if (tiffData) [types addObject:NSPasteboardTypeTIFF];
                    CGImageRelease(cgRef);
                }
            }

            [pb declareTypes:types owner:nil];
            [pb setPropertyList:paths forType:(NSPasteboardType)@"NSFilenamesPboardType"];

            if ([paths count] > 0) {
                NSURL *firstUrl = [NSURL fileURLWithPath:paths[0]];
                if (firstUrl) {
                    [pb setString:[firstUrl absoluteString] forType:NSPasteboardTypeFileURL];
                }
            }

            if ([paths count] > 0) {
                NSString *allPaths = [paths componentsJoinedByString:@"\\n"];
                [pb setString:allPaths forType:NSPasteboardTypeString];
            }

            if (pngData) {
                [pb setData:pngData forType:NSPasteboardTypePNG];
            }
            if (tiffData) {
                [pb setData:tiffData forType:NSPasteboardTypeTIFF];
            }
            return 0;
        } else if ([action isEqualToString:@"get"]) {
            id filenames = [pb propertyListForType:(NSPasteboardType)@"NSFilenamesPboardType"];
            if ([filenames isKindOfClass:[NSArray class]] && [filenames count] > 0) {
                for (NSString *p in filenames) {
                    if ([p length] > 0) printf("%s\\n", [p UTF8String]);
                }
                return 0;
            }
            NSArray *classes = @[[NSURL class]];
            NSDictionary *options = @{NSPasteboardURLReadingFileURLsOnlyKey: @YES};
            NSArray *urls = [pb readObjectsForClasses:classes options:options];
            if (urls && [urls count] > 0) {
                for (NSURL *url in urls) {
                    printf("%s\\n", [[url path] UTF8String]);
                }
                return 0;
            }
            NSString *str = [pb stringForType:NSPasteboardTypeString];
            if (str && [str length] > 0) {
                printf("%s\\n", [str UTF8String]);
            }
            return 0;
        }
    }
    return 0;
}
"""
    tmp_m = "/tmp/easydateien_clip_src.m"
    try:
        with open(tmp_m, "w", encoding="utf-8") as f:
            f.write(c_code)
        res = subprocess.run(["clang", "-O3", "-framework", "AppKit", "-framework", "Foundation", "-framework", "ImageIO", tmp_m, "-o", CLIP_HELPER_PATH], capture_output=True)
        if res.returncode == 0:
            return CLIP_HELPER_PATH
    except Exception:
        pass
    return None

def sync_to_macos_clipboard(paths: List[str]):
    """Synchronisiert Dateipfade nativ in die macOS-Zwischenablage für Finder (Cmd+V) und Texteditoren."""
    if not paths:
        return
    abs_paths = [os.path.abspath(p) for p in paths if os.path.exists(p)]
    if not abs_paths:
        return
    helper = ensure_clip_helper()
    if helper:
        try:
            res = subprocess.run([helper, "set"] + abs_paths, capture_output=True, timeout=4.0)
            if res.returncode == 0:
                return
        except Exception:
            pass
    # AppleScript-Fallback
    try:
        items = ", ".join([f'(POSIX file "{p.replace(chr(34), chr(92)+chr(34))}" as alias)' for p in abs_paths])
        as_code = f'set the clipboard to {{{items}}}'
        subprocess.run(["osascript", "-e", as_code], capture_output=True, timeout=2.0)
    except Exception:
        pass

def get_macos_clipboard_files() -> List[str]:
    """Liest echte Dateiobjekte und Pfade aus dem macOS-Pasteboard."""
    helper = ensure_clip_helper()
    if helper:
        try:
            out = subprocess.check_output([helper, "get"], text=True, timeout=4.0)
            lines = [l.strip() for l in out.splitlines() if l.strip() and os.path.exists(l.strip())]
            if lines:
                return lines
        except Exception:
            pass
    try:
        out = subprocess.check_output(["pbpaste"], text=True, timeout=1.0)
        lines = [l.strip() for l in out.splitlines() if l.strip() and os.path.exists(l.strip())]
        if lines:
            return lines
    except Exception:
        pass
    return []

def copy_text_to_clipboard(text: str):
    """Kopiert reinen Text in das macOS-Clipboard."""
    try:
        p = subprocess.Popen(["pbcopy"], stdin=subprocess.PIPE)
        p.communicate(input=text.encode("utf-8"))
    except Exception:
        pass

def get_file_type_desc(item: FileEntry) -> str:
    """Liefert eine präzise deutsche Typbezeichnung."""
    if item.is_symlink:
        if item.is_broken:
            return "Defekter Link"
        return "Link auf Ordner" if item.is_dir else "Symbolischer Link"
    if item.is_dir:
        return "Verzeichnis"
    ext = item.ext.lower()
    m = {
        ".txt": "Textdokument", ".md": "Markdown-Datei", ".py": "Python-Skript",
        ".sh": "Shell-Skript", ".zsh": "Zsh-Skript", ".bash": "Bash-Skript",
        ".json": "JSON-Dokument", ".toml": "TOML-Konfiguration", ".yaml": "YAML-Datei",
        ".yml": "YAML-Datei", ".pdf": "PDF-Dokument", ".zip": "ZIP-Archiv",
        ".tar": "TAR-Archiv", ".gz": "GZIP-Archiv", ".dmg": "Apple Disk Image",
        ".png": "PNG-Bild", ".jpg": "JPEG-Bild", ".jpeg": "JPEG-Bild",
        ".svg": "SVG-Vektorgrafik", ".gif": "GIF-Animation", ".webp": "WebP-Bild",
        ".html": "HTML-Dokument", ".css": "CSS-Stylesheet", ".js": "JavaScript",
        ".ts": "TypeScript", ".typ": "Typst-Dokument", ".rtf": "Rich-Text-Format",
        ".mp3": "MP3-Audiodatei", ".wav": "WAV-Audiodatei", ".mp4": "MP4-Videodatei",
        ".mov": "QuickTime-Video", ".csv": "CSV-Tabelle",
    }
    if ext in m:
        return m[ext]
    if item.is_exec:
        return "Ausführbare Datei"
    return f"Datei ({ext})" if ext else "Binärdatei"

def natural_key(text: str) -> list:
    """Natürlicher Sortierschlüssel (datei2 < datei10), unabhängig von Groß-/Kleinschreibung."""
    return [int(p) if p.isdigit() else p for p in _NATURAL_RE.split(text.lower())]

def scan_raw(path: str) -> List[FileEntry]:
    """Liest alle Einträge eines Verzeichnisses ungefiltert und unsortiert ein."""
    entries = []
    try:
        with os.scandir(path) as it:
            for entry in it:
                entries.append(FileEntry(entry.path, entry.name, entry))
    except OSError:
        return []
    return entries

def arrange_entries(
    raw: List[FileEntry],
    show_hidden: bool = False,
    sort_by: str = "mtime",
    sort_reverse: bool = True,
    sort_dir_first: bool = True,
    filter_query: str = ""
) -> List[FileEntry]:
    """Filtert und sortiert eingelesene Einträge deterministisch."""
    q = filter_query.lower()
    entries = [
        e for e in raw
        if (show_hidden or not e.name.startswith(".")) and (not q or q in e.name.lower())
    ]

    # Datum und Größe: neueste/größte zuerst (sort_reverse); Name und Typ: stets aufsteigend A–Z
    if sort_by == "name":
        entries.sort(key=lambda e: natural_key(e.name))
    elif sort_by == "size":
        entries.sort(key=lambda e: (e.size, natural_key(e.name)), reverse=sort_reverse)
    elif sort_by == "ext":
        entries.sort(key=lambda e: (e.ext.lower(), natural_key(e.name)))
    elif sort_by == "atime":
        entries.sort(key=lambda e: (e.atime, natural_key(e.name)), reverse=sort_reverse)
    else:
        entries.sort(key=lambda e: (e.mtime, natural_key(e.name)), reverse=sort_reverse)
    if sort_dir_first:
        entries.sort(key=lambda e: not e.is_dir)
    return entries

def scan_directory(
    path: str,
    show_hidden: bool = False,
    sort_by: str = "mtime",
    sort_reverse: bool = True,
    sort_dir_first: bool = True,
    filter_query: str = ""
) -> List[FileEntry]:
    """Liest ein Verzeichnis ein, filtert und sortiert deterministisch."""
    return arrange_entries(scan_raw(path), show_hidden, sort_by, sort_reverse, sort_dir_first, filter_query)

def listing_signature(entries: List[FileEntry]) -> Tuple:
    """Schneller Fingerabdruck eines Verzeichnisinhalts (Name, Größe, Änderungszeit) zur Änderungserkennung."""
    return tuple(sorted((e.name, e.size, e.mtime, e.symlink_target) for e in entries))

def format_entry_name(it: FileEntry, width: int, bold: bool = False) -> str:
    """Rendert Name (und bei Links „ → Ziel“ kursiv) exakt auf `width` Spalten.

    Der Name hat Vorrang: Ist er zu lang, wird er mit „…“ gekürzt, die Endung bzw. „/“ bleibt dahinter
    erhalten. Der Linkzielpfad wird nur am Ende gekürzt (nie am Anfang).
    """
    if width <= 0:
        return ""
    if it.is_broken:
        st_on = C_BOLD_RED if bold else C_RED
    elif it.is_symlink:
        st_on = C_BOLD_CYAN if bold else C_CYAN
    elif it.is_dir:
        st_on = C_BOLD_BLUE
    elif it.name.startswith("."):
        st_on = C_BOLD if bold else C_DIM
    else:
        st_on = C_BOLD if bold else ""
    full_name = safe_text(it.name) + ("/" if it.is_dir else "")
    name_w = str_width(full_name)

    def styled(txt: str) -> str:
        if not txt:
            return ""
        return f"{st_on}{txt}{C_RESET}" if st_on else txt

    if it.is_symlink:
        target = safe_text(it.symlink_target)
        if target and name_w + 3 + 4 <= width:
            tgt = truncate_to_width(target, max(3, width - name_w - 3))
            body = f"{styled(full_name)} {C_DIM}→ {C_ITALIC}{tgt}{C_RESET}"
        elif name_w + 2 <= width:
            body = f"{styled(full_name)} {C_DIM}→{C_RESET}"
        elif width >= 6:
            body = f"{styled(truncate_name(it.name, it.is_dir, width - 2))} {C_DIM}→{C_RESET}"
        else:
            body = styled(truncate_name(it.name, it.is_dir, width))
    else:
        body = styled(truncate_name(it.name, it.is_dir, width))
    return pad_to_width(body, width)

# Self-Pipe: SIGWINCH schreibt sofort ein Byte; read_key kann darauf warten,
# damit ein Fensternresize das Warten sofort beendet (statt den vollen
# Timeout abzuwarten) und die Hauptschleife sofort neu zeichnet.
RESIZE_PIPE = os.pipe()
WAKE_PIPE = os.pipe()


def notify_ui_wakeup():
    """Weckt die TUI-Hauptschleife ohne Verzögerung (0ms Latenz) aus read_key auf."""
    try:
        os.write(WAKE_PIPE[1], b"w")
    except OSError:
        pass


def _verwerfe_wake_events():
    try:
        while select.select([WAKE_PIPE[0]], [], [], 0)[0]:
            os.read(WAKE_PIPE[0], 64)
    except OSError:
        pass


def _bei_sigwinch(signum, frame):
    try:
        os.write(RESIZE_PIPE[1], b"r")
    except OSError:
        pass


def _install_resize_handler():
    import signal
    try:
        signal.signal(signal.SIGWINCH, _bei_sigwinch)
    except Exception:
        pass


def _verwerfe_resize_events():
    try:
        while select.select([RESIZE_PIPE[0]], [], [], 0)[0]:
            os.read(RESIZE_PIPE[0], 64)
    except OSError:
        pass


def read_key(fd: int, timeout: float = 0.05) -> str:
    """Liest Tastatur- und Maus-Events zuverlässig über SGR und ANSI-Sequenzen."""
    try:
        r, _, _ = select.select([fd, RESIZE_PIPE[0], WAKE_PIPE[0]], [], [], timeout)
        if RESIZE_PIPE[0] in r:
            _verwerfe_resize_events()
            # Resize ist kein Tastaturzeichen: sofort zurück (leer), die
            # Hauptschleife prüft daraufhin die Terminalgröße neu.
            if fd not in r:
                return ""
        if WAKE_PIPE[0] in r:
            _verwerfe_wake_events()
            if fd not in r:
                return ""
        if fd not in r:
            return ""
        raw = os.read(fd, 1)
        if not raw:
            return ""
        if raw == b"\x1b":
            seq = b""
            while True:
                r2, _, _ = select.select([fd], [], [], 0.05 if not seq else 0.02)
                if not r2:
                    break
                c = os.read(fd, 1)
                if not c:
                    break
                seq += c
                body = seq[1:] if seq.startswith(b"\x1b") else seq
                if body.startswith(b"[<"):
                    if body.endswith(b"M") or body.endswith(b"m") or len(seq) >= 32:
                        break
                elif body.startswith(b"["):
                    if len(body) >= 2 and 0x40 <= body[-1] <= 0x7E:
                        break
                    if len(seq) >= 16:
                        break
                elif body.startswith(b"O"):
                    if len(body) >= 2:
                        break
                elif seq != b"\x1b":
                    break
            if not seq or seq == b"\x1b":
                return "ESC"
            body = seq[1:] if seq.startswith(b"\x1b") else seq
            has_esc_prefix = seq.startswith(b"\x1b")
            if body.startswith(b"[<") and (body.endswith(b"M") or body.endswith(b"m")):
                try:
                    is_rel = body.endswith(b"m")
                    b_s, x_s, y_s = body[2:-1].decode("ascii").split(";")
                    b_c = int(b_s)
                    if (b_c & 64) and (b_c & 3) == 0:
                        return f"MOUSE_WHEEL_UP:{int(x_s)}:{int(y_s)}"
                    elif (b_c & 64) and (b_c & 3) == 1:
                        return f"MOUSE_WHEEL_DOWN:{int(x_s)}:{int(y_s)}"
                    elif not is_rel and b_c == 0:
                        return f"MOUSE_CLICK:{int(x_s)}:{int(y_s)}"
                    elif not is_rel and b_c == 2:
                        return f"MOUSE_RIGHT_CLICK:{int(x_s)}:{int(y_s)}"
                except Exception:
                    pass
                return "MOUSE_EVENT"

            if body in (b"[5~", b"[5z", b"[I") or (body.startswith(b"[5;") and body.endswith(b"~")):
                return "PAGE_UP"
            if body in (b"[6~", b"[6z", b"[G") or (body.startswith(b"[6;") and body.endswith(b"~")):
                return "PAGE_DOWN"
            if has_esc_prefix and body in (b"[A", b"OA"):
                return "ALT_UP"
            if has_esc_prefix and body in (b"[B", b"OB"):
                return "ALT_DOWN"

            mapping = {
                b"[A": "UP", b"[B": "DOWN", b"[C": "RIGHT", b"[D": "LEFT",
                b"OA": "UP", b"OB": "DOWN", b"OC": "RIGHT", b"OD": "LEFT",
                b"[1;2A": "SHIFT_UP", b"[1;2B": "SHIFT_DOWN",
                b"[2A": "SHIFT_UP", b"[2B": "SHIFT_DOWN",
                b"[1;3A": "ALT_UP", b"[1;3B": "ALT_DOWN",
                b"[3A": "ALT_UP", b"[3B": "ALT_DOWN",
                b"[1;4A": "ALT_SHIFT_UP", b"[1;4B": "ALT_SHIFT_DOWN",
                b"[4A": "ALT_SHIFT_UP", b"[4B": "ALT_SHIFT_DOWN",
                b"[1;5A": "CTRL_UP", b"[1;5B": "CTRL_DOWN",
                b"[5A": "CTRL_UP", b"[5B": "CTRL_DOWN",
                b"Oa": "CTRL_UP", b"Ob": "CTRL_DOWN",
                b"[1;6A": "CTRL_SHIFT_UP", b"[1;6B": "CTRL_SHIFT_DOWN",
                b"[6A": "CTRL_SHIFT_UP", b"[6B": "CTRL_SHIFT_DOWN",
                b"[1;9A": "ALT_UP", b"[1;9B": "ALT_DOWN",
                b"[1;10A": "ALT_SHIFT_UP", b"[1;10B": "ALT_SHIFT_DOWN",
                b"[H": "HOME", b"[F": "END", b"OH": "HOME", b"OF": "END",
                b"[1~": "HOME", b"[4~": "END", b"[7~": "HOME", b"[8~": "END",
                b"[5~": "PAGE_UP", b"[6~": "PAGE_DOWN",
                b"[5;2~": "PAGE_UP", b"[6;2~": "PAGE_DOWN",
                b"[5;5~": "PAGE_UP", b"[6;5~": "PAGE_DOWN",
                b"[3~": "DELETE",
                b"[Z": "SHIFT_TAB"
            }
            return mapping.get(body, "")

        if raw in (bytes([13]), bytes([10])):
            return "ENTER"
        elif raw == b" ":
            return "SPACE"
        elif raw == b"\t":
            return "TAB"
        elif raw in (bytes([127]), bytes([8])):
            return "BACKSPACE"
        elif raw == bytes([3]):  # Ctrl+C
            return "CTRL_C"
        elif raw == bytes([4]):  # Ctrl+D
            return "CTRL_D"
        elif raw == bytes([26]):  # Ctrl+Z
            return "UNDO"

        if raw[0] >= 0xC0:
            needed = 2 if raw[0] < 0xE0 else (3 if raw[0] < 0xF0 else 4)
            ch_b = raw
            while len(ch_b) < needed:
                r, _, _ = select.select([fd], [], [], 0.03)
                if not r:
                    break
                ch_b += os.read(fd, 1)
            try:
                return ch_b.decode("utf-8")
            except Exception:
                return ""
        try:
            return raw.decode("utf-8")
        except Exception:
            return ""
    except Exception:
        return ""
