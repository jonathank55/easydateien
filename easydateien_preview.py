#!/usr/bin/env python3
"""EasyDateien — Medien- und Dokumentenvorschau (PDF, Bilder, Videos).

Ermöglicht native, hochauflösende Vorschauen wie in Yazi:
1. Kitty Graphics Protocol (Ghostty, Kitty, WezTerm): echte Rastergrafik
2. Chafa / Halbblockfallback: universelle 24-Bit-ANSI-Zeichendarstellung
   für Terminals ohne Grafikprotokoll (z. B. Terminal.app).
"""

import os
import sys
import shutil
import hashlib
import subprocess
import base64
import struct
import fcntl
import termios
import threading
import re
import glob
from typing import Dict, List, Optional, Set, Tuple

IMAGE_EXTENSIONS = {
    ".png", ".jpg", ".jpeg", ".webp", ".gif", ".svg", ".bmp",
    ".ico", ".tiff", ".tif", ".heic", ".heif", ".avif", ".raw",
    ".cr2", ".nef", ".psd"
}

PDF_EXTENSIONS = {".pdf"}

VIDEO_EXTENSIONS = {".mp4", ".mov", ".mkv", ".webm", ".avi", ".m4v"}

KITTY_CLEAR_VISIBLE = "\033_Gq=2,a=d,d=A\033\\"
KITTY_PURGE_ALL = "\033_Gq=2,a=d,d=A\033\\"

_MEDIA_CACHE_DIR = os.path.expanduser("~/.cache/easydateien/previews")

# Schnelle In-Memory-Caches für verzögerungsfreie TUI-Aktualisierung
_CACHE_KEY_MEM: Dict[Tuple[str, int, int], str] = {}
_THUMB_MEM_CACHE: Dict[str, Optional[str]] = {}
_FAST_PATH_PAGE_CACHE: Dict[Tuple[str, int], str] = {}
_IMAGE_SIZE_MEM: Dict[str, Optional[Tuple[int, int]]] = {}
_FONT_RATIO_CACHE: Optional[float] = None
_PDF_PAGE_COUNT_MEM: Dict[str, int] = {}


def _trigger_ui_wakeup():
    """Weckt die TUI-Hauptschleife ohne Verzögerung auf."""
    try:
        from easydateien_ui import notify_ui_wakeup
        notify_ui_wakeup()
    except Exception:
        pass

PDF_HELPER_PATH = os.path.join(os.path.expanduser("~/.config/easydateien"), "easydateien_pdf")


def ensure_pdf_helper() -> Optional[str]:
    """Stellt sicher, dass das native macOS PDF-Hilfswerkzeug kompiliert und bereit ist."""
    if sys.platform != "darwin":
        return None
    if os.path.exists(PDF_HELPER_PATH) and os.access(PDF_HELPER_PATH, os.X_OK):
        return PDF_HELPER_PATH
    src_m = os.path.join(os.path.dirname(__file__), "easydateien_pdf.m")
    if not os.path.exists(src_m):
        return None
    clang = shutil.which("clang")
    if not clang:
        return None
    try:
        os.makedirs(os.path.dirname(PDF_HELPER_PATH), exist_ok=True)
        res = subprocess.run([
            clang, "-O3",
            "-framework", "Foundation", "-framework", "PDFKit", "-framework", "CoreGraphics", "-framework", "ImageIO",
            src_m, "-o", PDF_HELPER_PATH
        ], capture_output=True, timeout=5.0)
        if res.returncode == 0 and os.path.exists(PDF_HELPER_PATH):
            os.chmod(PDF_HELPER_PATH, 0o755)
            return PDF_HELPER_PATH
    except Exception:
        pass
    return None


def get_pdf_page_count(path: str) -> int:
    """Ermittelt die Gesamtseitenanzahl eines PDF-Dokuments (vollständig nicht blockierend)."""
    if not path or not os.path.isfile(path):
        return 1
    cache_key = get_file_cache_key(path)
    if cache_key in _PDF_PAGE_COUNT_MEM:
        return _PDF_PAGE_COUNT_MEM[cache_key]

    # Schnelle, unterbrechungsfreie Binärprüfung (Mikrosekunden, blockiert niemals den Hauptthread)
    try:
        with open(path, "rb") as f:
            head = f.read(512 * 1024)
            m = re.search(rb"/Type\s*/Pages\b[^>]*?/Count\s+(\d+)", head, re.DOTALL)
            if not m:
                m = re.search(rb"/Count\s+(\d+)[^>]*?/Type\s*/Pages\b", head, re.DOTALL)
            if m:
                count = int(m.group(1))
                if count > 0:
                    _PDF_PAGE_COUNT_MEM[cache_key] = count
                    return count

            f.seek(0, os.SEEK_END)
            size = f.tell()
            if size > 512 * 1024:
                seek_pos = max(0, size - 256 * 1024)
                f.seek(seek_pos)
                tail = f.read()
                m = re.search(rb"/Type\s*/Pages\b[^>]*?/Count\s+(\d+)", tail, re.DOTALL)
                if not m:
                    m = re.search(rb"/Count\s+(\d+)[^>]*?/Type\s*/Pages\b", tail, re.DOTALL)
                if m:
                    count = int(m.group(1))
                    if count > 0:
                        _PDF_PAGE_COUNT_MEM[cache_key] = count
                        return count

            pages = len(re.findall(rb"/Type\s*/Page\b", head))
            if pages > 0:
                _PDF_PAGE_COUNT_MEM[cache_key] = pages
                return pages
    except Exception:
        pass

    _PDF_PAGE_COUNT_MEM[cache_key] = 1
    return 1


def get_media_cache_dir() -> str:
    """Liefert den Cacheordner für Vorschaubilder und legt ihn bei Bedarf an."""
    if not os.path.isdir(_MEDIA_CACHE_DIR):
        try:
            os.makedirs(_MEDIA_CACHE_DIR, exist_ok=True)
        except OSError:
            pass
    return _MEDIA_CACHE_DIR


def is_previewable_media(path: Optional[str]) -> bool:
    """Prüft, ob der angegebene Pfad eine visuell vorschaufähige Mediendatei ist."""
    if not path:
        return False
    try:
        if not os.path.isfile(path):
            return False
    except OSError:
        return False
    ext = os.path.splitext(path)[1].lower()
    return ext in IMAGE_EXTENSIONS or ext in PDF_EXTENSIONS or ext in VIDEO_EXTENSIONS


def supports_kitty_graphics() -> bool:
    """Prüft, ob das aktuelle Terminal das Kitty Graphics Protocol unterstützt."""
    if not getattr(sys.stdout, "isatty", lambda: False)():
        return False
    # Ghostty und WezTerm unterstützen KGP nativ
    term_prog = os.environ.get("TERM_PROGRAM", "").strip()
    if term_prog in ("ghostty", "WezTerm"):
        return True
    if os.environ.get("GHOSTTY_RESOURCES_DIR"):
        return True
    term = os.environ.get("TERM", "").strip().lower()
    if "kitty" in term or "KITTY_WINDOW_ID" in os.environ or "KITTY_PID" in os.environ:
        return True
    return False


def get_terminal_font_ratio(force_refresh: bool = False) -> float:
    """Ermittelt das Breite-zu-Höhe-Verhältnis einer Terminaltextzelle (mit Zwischenspeicherung)."""
    global _FONT_RATIO_CACHE
    if _FONT_RATIO_CACHE is not None and not force_refresh:
        return _FONT_RATIO_CACHE
    try:
        s = struct.pack("HHHH", 0, 0, 0, 0)
        res = fcntl.ioctl(sys.stdout.fileno(), termios.TIOCGWINSZ, s)
        rows, cols, xpix, ypix = struct.unpack("HHHH", res)
        if cols > 0 and rows > 0 and xpix > 0 and ypix > 0:
            cell_w = xpix / cols
            cell_h = ypix / rows
            if cell_h > 0:
                ratio = cell_w / cell_h
                if 0.3 <= ratio <= 0.8:
                    _FONT_RATIO_CACHE = ratio
                    return ratio
    except Exception:
        pass
    _FONT_RATIO_CACHE = 0.5
    return 0.5


def _read_image_pixel_size_raw(path: str) -> Optional[Tuple[int, int]]:
    """Liest die tatsächlichen Pixeldimensionen (Breite, Höhe) direkt aus Dateiheadern."""
    if not path or not os.path.isfile(path):
        return None
    try:
        with open(path, "rb") as f:
            header = f.read(64)
        # PNG: IHDR bei Offset 16
        if len(header) >= 24 and header[:8] == b"\x89PNG\r\n\x1a\n":
            w, h = struct.unpack(">II", header[16:24])
            return (w, h)
        # GIF: Offset 6
        if len(header) >= 10 and header[:6] in (b"GIF87a", b"GIF89a"):
            w, h = struct.unpack("<HH", header[6:10])
            return (w, h)
        # BMP: Offset 18
        if len(header) >= 26 and header[:2] == b"BM":
            w, h = struct.unpack("<ii", header[18:26])
            return (abs(w), abs(h))
    except Exception:
        pass

    # Universeller Fallback über sips auf macOS
    sips = shutil.which("sips")
    if sips:
        try:
            res = subprocess.run([sips, "-g", "pixelWidth", "-g", "pixelHeight", path], capture_output=True, text=True, timeout=1.0)
            w, h = None, None
            for line in res.stdout.splitlines():
                if "pixelWidth:" in line:
                    w = int(line.split(":")[1].strip())
                elif "pixelHeight:" in line:
                    h = int(line.split(":")[1].strip())
            if w and h:
                return (w, h)
        except Exception:
            pass
    return None


def get_image_pixel_size(path: str) -> Optional[Tuple[int, int]]:
    """Liefert Pixeldimensionen mit speicherresidenter Pufferung für maximale Geschwindigkeit."""
    if not path:
        return None
    if path in _IMAGE_SIZE_MEM:
        return _IMAGE_SIZE_MEM[path]
    dims = _read_image_pixel_size_raw(path)
    if dims:
        if len(_IMAGE_SIZE_MEM) > 1000:
            _IMAGE_SIZE_MEM.clear()
        _IMAGE_SIZE_MEM[path] = dims
    return dims


def compute_fit_dimensions(img_w: int, img_h: int, max_cols: int, max_rows: int, font_ratio: float = 0.5) -> Tuple[int, int]:
    """Berechnet Zelldimensionen unter strikter Beibehaltung des nativen Seitenverhältnisses."""
    if img_w <= 0 or img_h <= 0 or max_cols <= 0 or max_rows <= 0:
        return (max(1, max_cols), max(1, max_rows))

    # Visuelles Seitenverhältnis in Textzelleneinheiten
    cell_aspect = (img_w / img_h) / font_ratio
    box_aspect = max_cols / max_rows

    if cell_aspect >= box_aspect:
        # Durch die Breite begrenzt: Spalten voll nutzen, Zeilen anpassen
        fit_cols = max_cols
        fit_rows = max(1, min(max_rows, int(round(max_cols / cell_aspect))))
    else:
        # Durch die Höhe begrenzt: Zeilen voll nutzen, Spalten anpassen
        fit_rows = max_rows
        fit_cols = max(1, min(max_cols, int(round(max_rows * cell_aspect))))

    return (fit_cols, fit_rows)


def get_file_cache_key(path: str) -> str:
    """Erzeugt einen deterministischen Hash aus Pfad, Zeitstempel und Größe."""
    try:
        st = os.stat(path)
        stat_tuple = (path, st.st_mtime_ns, st.st_size)
        if stat_tuple in _CACHE_KEY_MEM:
            return _CACHE_KEY_MEM[stat_tuple]
        raw = f"{path}_{st.st_mtime_ns}_{st.st_size}"
        key = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]
        if len(_CACHE_KEY_MEM) > 2000:
            _CACHE_KEY_MEM.clear()
        _CACHE_KEY_MEM[stat_tuple] = key
        return key
    except OSError:
        return hashlib.sha256(path.encode("utf-8")).hexdigest()[:16]


def get_cached_thumbnail(path: str, page: int = 1) -> Optional[str]:
    """Prüft rein im Speicher und auf der Festplatte, ob ein gültiges Vorschaubild vorliegt.

    Blockiert niemals den Hauptthread und führt keine Konvertierungsbefehle aus.
    """
    if not path or not is_previewable_media(path):
        return None

    fast = _FAST_PATH_PAGE_CACHE.get((path, page))
    if fast is not None:
        if fast and os.path.exists(fast):
            return fast
        elif fast == "":
            return None

    cache_key = get_file_cache_key(path)
    mem_key = f"{cache_key}_p{page}"
    if mem_key in _THUMB_MEM_CACHE:
        cached = _THUMB_MEM_CACHE[mem_key]
        if cached and os.path.exists(cached):
            _FAST_PATH_PAGE_CACHE[(path, page)] = cached
            return cached
        elif cached == "":
            return None

    ext = os.path.splitext(path)[1].lower()

    # Nur echte, kompakte PNG-Dateien bis 500 KB können direkt ohne Konvertierung angezeigt werden
    if ext == ".png":
        try:
            if os.path.getsize(path) <= 500 * 1024:
                _THUMB_MEM_CACHE[mem_key] = path
                _FAST_PATH_PAGE_CACHE[(path, page)] = path
                return path
        except OSError:
            pass

    # Prüfen, ob die Datei bereits im lokalen Vorschauordner liegt
    cache_dir = get_media_cache_dir()
    if ext in PDF_EXTENSIONS:
        target = os.path.join(cache_dir, f"pdf_{cache_key}_p{page}.png")
        if not os.path.exists(target) and page == 1:
            legacy = os.path.join(cache_dir, f"pdf_{cache_key}.png")
            if os.path.exists(legacy) and os.path.getsize(legacy) > 0:
                _THUMB_MEM_CACHE[mem_key] = legacy
                _FAST_PATH_PAGE_CACHE[(path, page)] = legacy
                return legacy
    elif ext in VIDEO_EXTENSIONS:
        target = os.path.join(cache_dir, f"vid_{cache_key}.png")
    else:
        target = os.path.join(cache_dir, f"img_{cache_key}.png")

    try:
        if os.path.exists(target) and os.path.getsize(target) > 0:
            _THUMB_MEM_CACHE[mem_key] = target
            _FAST_PATH_PAGE_CACHE[(path, page)] = target
            return target
    except OSError:
        pass

    return None


def generate_preview_thumbnail(path: str, max_dim: int = 800, page: int = 1) -> Optional[str]:
    """Erzeugt ein optimiertes PNG-Vorschaubild im Cache und gibt dessen Pfad zurück.

    Verwendet deterministische Fallbackketten:
    - PDF: easydateien_pdf (nativ) -> pdftoppm (Poppler) -> sips (Seite 1) -> qlmanage
    - Bild: Direktnutzung bei Standardformaten <= 2 MB, sonst sips -> magick
    - Video: ffmpeg Frame 1 -> qlmanage
    """
    if not path or not os.path.isfile(path):
        return None

    ext = os.path.splitext(path)[1].lower()
    cache_dir = get_media_cache_dir()
    cache_key = get_file_cache_key(path)
    mem_key = f"{cache_key}_p{page}"

    # 1. PDF-Dokument
    if ext in PDF_EXTENSIONS:
        cached_png = os.path.join(cache_dir, f"pdf_{cache_key}_p{page}.png")
        if os.path.exists(cached_png) and os.path.getsize(cached_png) > 0:
            _THUMB_MEM_CACHE[mem_key] = cached_png
            _FAST_PATH_PAGE_CACHE[(path, page)] = cached_png
            return cached_png
        if page == 1:
            legacy = os.path.join(cache_dir, f"pdf_{cache_key}.png")
            if os.path.exists(legacy) and os.path.getsize(legacy) > 0:
                _THUMB_MEM_CACHE[mem_key] = legacy
                _FAST_PATH_PAGE_CACHE[(path, page)] = legacy
                return legacy

        # A) Nativer PDF-Helfer (macOS - schnell via CoreGraphics & ImageIO mit Batchvorabladen)
        helper = ensure_pdf_helper()
        if helper:
            cmd = [helper, path, str(page), cached_png, str(max_dim)]
            extra_pages = []
            total_pages = get_pdf_page_count(path)
            if total_pages > 1:
                for cand in (page + 1, page - 1, page + 2):
                    if 1 <= cand <= total_pages and cand != page:
                        cand_target = os.path.join(cache_dir, f"pdf_{cache_key}_p{cand}.png")
                        if not os.path.exists(cand_target):
                            extra_pages.append((cand, cand_target))
            for cand_p, cand_t in extra_pages:
                cmd.extend([str(cand_p), cand_t])

            try:
                res = subprocess.run(cmd, capture_output=True, text=True, timeout=3.0)
                if res.returncode == 0 and os.path.exists(cached_png) and os.path.getsize(cached_png) > 0:
                    val = (res.stdout or "").strip()
                    if val.isdigit() and int(val) > 0:
                        _PDF_PAGE_COUNT_MEM[cache_key] = int(val)
                    _THUMB_MEM_CACHE[mem_key] = cached_png
                    _FAST_PATH_PAGE_CACHE[(path, page)] = cached_png
                    for cand_p, cand_t in extra_pages:
                        if os.path.exists(cand_t) and os.path.getsize(cand_t) > 0:
                            _THUMB_MEM_CACHE[f"{cache_key}_p{cand_p}"] = cand_t
                            _FAST_PATH_PAGE_CACHE[(path, cand_p)] = cand_t
                    return cached_png
            except (subprocess.TimeoutExpired, OSError):
                pass

        # B) pdftoppm (Poppler - seitengenau & portabel)
        pdftoppm = shutil.which("pdftoppm")
        if pdftoppm:
            prefix = os.path.join(cache_dir, f"tmp_pdf_{cache_key}_p{page}")
            cmd = [
                pdftoppm, "-png", "-f", str(page), "-l", str(page),
                "-scale-to-x", str(max_dim), "-scale-to-y", "-1",
                path, prefix
            ]
            try:
                res = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=4.0)
                matches = glob.glob(f"{prefix}*.png")
                if res.returncode == 0 and matches and os.path.exists(matches[0]):
                    os.replace(matches[0], cached_png)
                    for extra in matches[1:]:
                        try: os.remove(extra)
                        except OSError: pass
                    _THUMB_MEM_CACHE[mem_key] = cached_png
                    return cached_png
            except (subprocess.TimeoutExpired, OSError):
                pass

        # C) sips (macOS nativ vorinstalliert - nur für Seite 1)
        if page == 1:
            sips = shutil.which("sips")
            if sips:
                try:
                    cmd = [sips, "-s", "format", "png", "-Z", str(max_dim), path, "--out", cached_png]
                    res = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=3.0)
                    if res.returncode == 0 and os.path.exists(cached_png) and os.path.getsize(cached_png) > 0:
                        _THUMB_MEM_CACHE[mem_key] = cached_png
                        return cached_png
                except (subprocess.TimeoutExpired, OSError):
                    pass

        # D) qlmanage (macOS QuickLook - nur für Seite 1)
        if page == 1:
            qlmanage = shutil.which("qlmanage")
            if qlmanage:
                try:
                    cmd = [qlmanage, "-t", "-s", str(max_dim), "-o", cache_dir, path]
                    res = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=4.0)
                    gen_file = os.path.join(cache_dir, f"{os.path.basename(path)}.png")
                    if res.returncode == 0 and os.path.exists(gen_file):
                        os.replace(gen_file, cached_png)
                        _THUMB_MEM_CACHE[mem_key] = cached_png
                        return cached_png
                except (subprocess.TimeoutExpired, OSError):
                    pass

        _THUMB_MEM_CACHE[mem_key] = ""
        return None

    # 2. Bilddatei
    elif ext in IMAGE_EXTENSIONS:
        try:
            fsize = os.path.getsize(path)
        except OSError:
            fsize = 0

        # Nur echte, kompakte PNG-Dateien bis 500 KB können direkt übertragen werden
        if ext == ".png" and fsize <= 500 * 1024:
            _THUMB_MEM_CACHE[mem_key] = path
            _FAST_PATH_PAGE_CACHE[(path, page)] = path
            return path

        cached_png = os.path.join(cache_dir, f"img_{cache_key}.png")
        if os.path.exists(cached_png) and os.path.getsize(cached_png) > 0:
            _THUMB_MEM_CACHE[mem_key] = cached_png
            _FAST_PATH_PAGE_CACHE[(path, page)] = cached_png
            return cached_png

        # Konvertierung / Skalierung via sips
        sips = shutil.which("sips")
        if sips:
            try:
                cmd = [sips, "-s", "format", "png", "-Z", str(max_dim), path, "--out", cached_png]
                res = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=3.0)
                if res.returncode == 0 and os.path.exists(cached_png) and os.path.getsize(cached_png) > 0:
                    _THUMB_MEM_CACHE[mem_key] = cached_png
                    _FAST_PATH_PAGE_CACHE[(path, page)] = cached_png
                    return cached_png
            except (subprocess.TimeoutExpired, OSError):
                pass

        # Konvertierung via magick
        magick = shutil.which("magick")
        if magick:
            try:
                cmd = [magick, path, "-resize", f"{max_dim}x{max_dim}>", cached_png]
                res = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=3.0)
                if res.returncode == 0 and os.path.exists(cached_png) and os.path.getsize(cached_png) > 0:
                    _THUMB_MEM_CACHE[mem_key] = cached_png
                    _FAST_PATH_PAGE_CACHE[(path, page)] = cached_png
                    return cached_png
            except (subprocess.TimeoutExpired, OSError):
                pass

        # SVG: Falls sips/magick scheitern, chafa/direkt probieren
        if ext == ".svg":
            _THUMB_MEM_CACHE[mem_key] = path
            _FAST_PATH_PAGE_CACHE[(path, page)] = path
            return path

        _THUMB_MEM_CACHE[mem_key] = ""
        _FAST_PATH_PAGE_CACHE[(path, page)] = ""
        return None

    # 3. Videodatei
    elif ext in VIDEO_EXTENSIONS:
        cached_png = os.path.join(cache_dir, f"vid_{cache_key}.png")
        if os.path.exists(cached_png) and os.path.getsize(cached_png) > 0:
            _THUMB_MEM_CACHE[mem_key] = cached_png
            _FAST_PATH_PAGE_CACHE[(path, page)] = cached_png
            return cached_png

        ffmpeg = shutil.which("ffmpeg")
        if ffmpeg:
            try:
                cmd = [
                    ffmpeg, "-y", "-ss", "00:00:01", "-i", path,
                    "-vframes", "1", "-vf", f"scale={max_dim}:-1",
                    "-update", "1", cached_png
                ]
                res = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=3.0)
                if res.returncode == 0 and os.path.exists(cached_png) and os.path.getsize(cached_png) > 0:
                    _THUMB_MEM_CACHE[mem_key] = cached_png
                    _FAST_PATH_PAGE_CACHE[(path, page)] = cached_png
                    return cached_png
            except (subprocess.TimeoutExpired, OSError):
                pass

        qlmanage = shutil.which("qlmanage")
        if qlmanage:
            try:
                cmd = [qlmanage, "-t", "-s", str(max_dim), "-o", cache_dir, path]
                res = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=4.0)
                gen_file = os.path.join(cache_dir, f"{os.path.basename(path)}.png")
                if res.returncode == 0 and os.path.exists(gen_file):
                    os.replace(gen_file, cached_png)
                    _THUMB_MEM_CACHE[mem_key] = cached_png
                    _FAST_PATH_PAGE_CACHE[(path, page)] = cached_png
                    return cached_png
            except (subprocess.TimeoutExpired, OSError):
                pass

    _THUMB_MEM_CACHE[mem_key] = ""
    _FAST_PATH_PAGE_CACHE[(path, page)] = ""
    return None


def make_kitty_image_sequence(png_path: str, cols: int, rows: int, row_pos: int, col_pos: int) -> str:
    """Erzeugt die vollständige Escape-Sequenz für das Kitty Graphics Protocol."""
    try:
        with open(png_path, "rb") as f:
            data = f.read()
    except OSError:
        return ""

    if not data:
        return ""

    ext = os.path.splitext(png_path)[1].lower()
    fmt = 100 if ext in (".png", ".webp") else 24
    b64 = base64.b64encode(data).decode("ascii")
    chunk_size = 4096
    chunks = [b64[i:i + chunk_size] for i in range(0, len(b64), chunk_size)]
    if not chunks:
        return ""

    parts = [f"\033[{row_pos};{col_pos}H"]
    for idx, chunk in enumerate(chunks):
        m = 1 if idx < len(chunks) - 1 else 0
        if idx == 0:
            hdr = f"q=2,a=T,C=1,f={fmt},t=d,c={cols},r={rows},m={m}"
        else:
            hdr = f"q=2,m={m}"
        parts.append(f"\033_G{hdr};{chunk}\033\\")

    return "".join(parts)


def make_chafa_preview_lines(image_path: str, cols: int, rows: int) -> List[str]:
    """Erzeugt formatierte ANSI-Textzeilen mit 24-Bit-Halbblöcken via Chafa."""
    chafa = shutil.which("chafa")
    if chafa:
        cmd = [
            chafa,
            "-f", "symbols",
            "--symbols", "half+block",
            "--colors", "full",
            "--polite", "on",
            "--size", f"{cols}x{rows}",
            image_path
        ]
        try:
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=2.0)
            if res.returncode == 0:
                lines = res.stdout.splitlines()
                return lines[:rows]
        except (subprocess.TimeoutExpired, OSError):
            pass

    # Fallback: reines Python über sips (macOS nativ)
    return make_python_halfblock_lines(image_path, cols, rows)


def make_python_halfblock_lines(image_path: str, cols: int, rows: int) -> List[str]:
    """Universeller Python-Halbblock-Renderer für Terminals ohne externes Chafa."""
    sips = shutil.which("sips")
    if not sips:
        return []

    cache_dir = get_media_cache_dir()
    tmp_bmp = os.path.join(cache_dir, f"conv_{os.getpid()}.bmp")
    pixel_h = max(2, rows * 2)
    pixel_w = max(2, cols)

    try:
        cmd = [sips, "-s", "format", "bmp", "-z", str(pixel_h), str(pixel_w), image_path, "--out", tmp_bmp]
        res = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=2.0)
        if res.returncode != 0 or not os.path.exists(tmp_bmp):
            return []

        with open(tmp_bmp, "rb") as f:
            data = f.read()
        try:
            os.remove(tmp_bmp)
        except OSError:
            pass

        if len(data) < 54 or data[:2] != b"BM":
            return []

        pixel_offset = struct.unpack("<I", data[10:14])[0]
        w, h = struct.unpack("<ii", data[18:26])
        bpp = struct.unpack("<H", data[28:30])[0]

        if bpp not in (24, 32):
            return []

        is_top_down = (h < 0)
        h = abs(h)
        bytes_per_pixel = bpp // 8
        row_stride = ((w * bytes_per_pixel + 3) // 4) * 4

        # Pixel in Matrix laden (RGB)
        pixels = []
        for y in range(h):
            actual_y = y if is_top_down else (h - 1 - y)
            row_start = pixel_offset + actual_y * row_stride
            row_bytes = data[row_start:row_start + w * bytes_per_pixel]
            row_rgb = []
            for x in range(w):
                px_start = x * bytes_per_pixel
                # BMP speichert in BGR(A)
                b = row_bytes[px_start]
                g = row_bytes[px_start + 1]
                r = row_bytes[px_start + 2]
                row_rgb.append((r, g, b))
            pixels.append(row_rgb)

        # Halbblockzeilen konstruieren (je 2 vertikale Pixel pro Textzelle: oben FG, unten BG)
        lines = []
        for r_idx in range(rows):
            top_y = r_idx * 2
            bot_y = top_y + 1
            line_parts = []
            for c_idx in range(min(cols, w)):
                top_r, top_g, top_b = pixels[top_y][c_idx] if top_y < h else (0, 0, 0)
                bot_r, bot_g, bot_b = pixels[bot_y][c_idx] if bot_y < h else (0, 0, 0)
                # Oberer Halbblock: FG ist top, BG ist bottom
                line_parts.append(f"\033[38;2;{top_r};{top_g};{top_b}m\033[48;2;{bot_r};{bot_g};{bot_b}m▀")
            line_parts.append("\033[0m")
            lines.append("".join(line_parts))

        return lines
    except Exception:
        try:
            if os.path.exists(tmp_bmp):
                os.remove(tmp_bmp)
        except OSError:
            pass
        return []


class PreviewWorker:
    """Hintergrundarbeiter für nicht-blockierende Vorschauerzeugung und Vorabpufferung.

    Garantiert vollkommen verzögerungsfreie TUI-Navigation:
    - Der Hauptthread wird niemals durch rechenintensive Konvertierungen blockiert.
    - Bei schnellem Blättern werden veraltete Einzelanfragen sofort verdrängt.
    - Nachbardateien und PDF-Folgeseiten werden in Leerlaufphasen vorausschauend vorab gerendert.
    """

    def __init__(self):
        self._lock = threading.Lock()
        self._wake_event = threading.Event()
        self._stop_event = threading.Event()
        self._active_target: Optional[Tuple[str, int]] = None
        self._prefetch_list: List[Tuple[str, int]] = []
        self._ready_set: Set[Tuple[str, int]] = set()
        self._thread = threading.Thread(target=self._run, daemon=True, name="EasyDateien-PreviewWorker")
        self._thread.start()

    def request(self, path: str, page: int = 1, prefetch_pages: Optional[List[int]] = None, prefetch_paths: Optional[List[str]] = None):
        """Reicht eine Vorschauanfrage ein. Verdrängt veraltete Einzelaufträge sofort."""
        if not path or not is_previewable_media(path):
            return
        with self._lock:
            self._active_target = (path, page)
            pf_list: List[Tuple[str, int]] = []
            if prefetch_pages:
                for p in prefetch_pages:
                    if p > 0 and (path, p) != (path, page):
                        pf_list.append((path, p))
            if prefetch_paths:
                for pp in prefetch_paths:
                    if pp and pp != path and is_previewable_media(pp):
                        pf_list.append((pp, 1))
            self._prefetch_list = pf_list
        self._wake_event.set()

    def poll_ready(self, current_path: str, current_page: int = 1) -> bool:
        """Prüft, ob für (current_path, current_page) im Hintergrund ein Thumbnail fertiggestellt wurde."""
        with self._lock:
            target = (current_path, current_page)
            if target in self._ready_set:
                self._ready_set.discard(target)
                return True
            # Abwärtskompatibilität: 1-Tupel ebenfalls abfangen
            if current_path in self._ready_set and current_page == 1:
                self._ready_set.discard(current_path)
                return True
            return False

    def clear(self):
        """Verwirft anstehende Vorabaufträge (z.B. bei Verzeichniswechsel)."""
        with self._lock:
            self._active_target = None
            self._prefetch_list.clear()

    def stop(self):
        self._stop_event.set()
        self._wake_event.set()

    def _run(self):
        while not self._stop_event.is_set():
            self._wake_event.wait(timeout=0.1)
            self._wake_event.clear()
            if self._stop_event.is_set():
                break

            target = None
            prefetch = []
            with self._lock:
                target = self._active_target
                prefetch = list(self._prefetch_list)

            if target:
                t_path, t_page = target
                # Nur generieren, wenn nicht bereits im Speicher oder auf Festplatte
                if not get_cached_thumbnail(t_path, page=t_page):
                    thumb = generate_preview_thumbnail(t_path, page=t_page)
                    with self._lock:
                        self._ready_set.add(target)
                    _trigger_ui_wakeup()
                with self._lock:
                    if self._active_target == target:
                        self._active_target = None

            # Vorabpufferung für PDF-Folgeseiten & Nachbardateien in Leerlaufphasen
            for pf_path, pf_page in prefetch:
                with self._lock:
                    if self._active_target is not None or self._stop_event.is_set():
                        break
                if not get_cached_thumbnail(pf_path, page=pf_page):
                    pf_thumb = generate_preview_thumbnail(pf_path, page=pf_page)
                    if pf_thumb:
                        with self._lock:
                            self._ready_set.add((pf_path, pf_page))
                        _trigger_ui_wakeup()


GLOBAL_PREVIEW_WORKER = PreviewWorker()


def request_preview(path: str, page: int = 1, prefetch_pages: Optional[List[int]] = None, prefetch_paths: Optional[List[str]] = None):
    """Reicht eine Vorschauanfrage an den globalen Hintergrundarbeiter weiter."""
    GLOBAL_PREVIEW_WORKER.request(path, page=page, prefetch_pages=prefetch_pages, prefetch_paths=prefetch_paths)


def poll_preview_ready(current_path: str, current_page: int = 1) -> bool:
    """Prüft, ob die Vorschau für den aktuellen Pfad und Seite im Hintergrund fertig ist."""
    return GLOBAL_PREVIEW_WORKER.poll_ready(current_path, current_page)


def clear_preview_queue():
    """Löscht wartende Vorabaufträge des Hintergrundarbeiters."""
    GLOBAL_PREVIEW_WORKER.clear()

