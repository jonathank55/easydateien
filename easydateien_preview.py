#!/usr/bin/env python3
"""EasyDateien — Medien- und Dokumentenvorschau (PDF, Bilder, Videos).

Ermöglicht native, hochauflösende Vorschauen wie in Yazi:
1. Kitty Graphics Protocol (Ghostty, Kitty, WezTerm): echte Rastergrafik
2. Chafa / Halbblock-Fallback: universelle 24-Bit-ANSI-Zeichendarstellung
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
from typing import List, Optional, Tuple

IMAGE_EXTENSIONS = {
    ".png", ".jpg", ".jpeg", ".webp", ".gif", ".svg", ".bmp",
    ".ico", ".tiff", ".tif", ".heic", ".heif", ".avif", ".raw",
    ".cr2", ".nef", ".psd"
}

PDF_EXTENSIONS = {".pdf"}

VIDEO_EXTENSIONS = {".mp4", ".mov", ".mkv", ".webm", ".avi", ".m4v"}

KITTY_CLEAR_VISIBLE = "\033_Ga=d\033\\"
KITTY_PURGE_ALL = "\033_Ga=d,d=A\033\\"

_MEDIA_CACHE_DIR = os.path.expanduser("~/.cache/easydateien/previews")


def get_media_cache_dir() -> str:
    """Liefert den Cache-Ordner für Vorschaubilder und legt ihn bei Bedarf an."""
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


def get_terminal_font_ratio() -> float:
    """Ermittelt das Breite-zu-Höhe-Verhältnis einer Terminal-Textzelle."""
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
                    return ratio
    except Exception:
        pass
    return 0.5


def get_image_pixel_size(path: str) -> Optional[Tuple[int, int]]:
    """Liest die tatsächlichen Pixel-Dimensionen (Breite, Höhe) einer Bilddatei aus."""
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


def compute_fit_dimensions(img_w: int, img_h: int, max_cols: int, max_rows: int, font_ratio: float = 0.5) -> Tuple[int, int]:
    """Berechnet Zell-Dimensionen unter strikter Beibehaltung des nativen Seitenverhältnisses."""
    if img_w <= 0 or img_h <= 0 or max_cols <= 0 or max_rows <= 0:
        return (max(1, max_cols), max(1, max_rows))

    # Visuelles Seitenverhältnis in Textzellen-Einheiten
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
        raw = f"{path}_{st.st_mtime_ns}_{st.st_size}"
    except OSError:
        raw = path
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def generate_preview_thumbnail(path: str, max_dim: int = 800) -> Optional[str]:
    """Erzeugt ein optimiertes PNG-Vorschaubild im Cache und gibt dessen Pfad zurück.

    Verwendet deterministische Fallback-Ketten:
    - PDF: pdftoppm -> sips (macOS) -> magick -> qlmanage
    - Bild: Direktnutzung bei Standardformaten <= 2 MB, sonst sips -> magick
    - Video: ffmpeg Frame 1 -> qlmanage
    """
    if not path or not os.path.isfile(path):
        return None

    ext = os.path.splitext(path)[1].lower()
    cache_dir = get_media_cache_dir()
    cache_key = get_file_cache_key(path)

    # 1. PDF-Dokument
    if ext in PDF_EXTENSIONS:
        cached_png = os.path.join(cache_dir, f"pdf_{cache_key}.png")
        if os.path.exists(cached_png) and os.path.getsize(cached_png) > 0:
            return cached_png

        # A) pdftoppm (Poppler - schnell und scharf)
        pdftoppm = shutil.which("pdftoppm")
        if pdftoppm:
            prefix = os.path.join(cache_dir, f"tmp_pdf_{cache_key}")
            cmd = [
                pdftoppm, "-png", "-f", "1", "-l", "1",
                "-scale-to-x", str(max_dim), "-scale-to-y", "-1",
                path, prefix
            ]
            try:
                res = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=4.0)
                gen_file = f"{prefix}-1.png"
                if res.returncode == 0 and os.path.exists(gen_file):
                    os.replace(gen_file, cached_png)
                    return cached_png
            except (subprocess.TimeoutExpired, OSError):
                pass

        # B) sips (macOS nativ vorinstalliert)
        sips = shutil.which("sips")
        if sips:
            try:
                cmd = [sips, "-s", "format", "png", path, "--out", cached_png]
                res = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=4.0)
                if res.returncode == 0 and os.path.exists(cached_png) and os.path.getsize(cached_png) > 0:
                    subprocess.run([sips, "-Z", str(max_dim), cached_png], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=2.0)
                    return cached_png
            except (subprocess.TimeoutExpired, OSError):
                pass

        # C) magick (ImageMagick)
        magick = shutil.which("magick")
        if magick:
            try:
                cmd = [magick, "-density", "150", f"{path}[0]", "-resize", f"{max_dim}x{max_dim}>", cached_png]
                res = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=4.0)
                if res.returncode == 0 and os.path.exists(cached_png) and os.path.getsize(cached_png) > 0:
                    return cached_png
            except (subprocess.TimeoutExpired, OSError):
                pass

        # D) qlmanage (macOS QuickLook)
        qlmanage = shutil.which("qlmanage")
        if qlmanage:
            try:
                cmd = [qlmanage, "-t", "-s", str(max_dim), "-o", cache_dir, path]
                res = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=4.0)
                gen_file = os.path.join(cache_dir, f"{os.path.basename(path)}.png")
                if res.returncode == 0 and os.path.exists(gen_file):
                    os.replace(gen_file, cached_png)
                    return cached_png
            except (subprocess.TimeoutExpired, OSError):
                pass

        return None

    # 2. Bilddatei
    elif ext in IMAGE_EXTENSIONS:
        try:
            fsize = os.path.getsize(path)
        except OSError:
            fsize = 0

        # Standard-Webformate mit moderater Größe können direkt übertragen werden
        if ext in (".png", ".jpg", ".jpeg", ".webp") and fsize <= 2 * 1024 * 1024:
            return path

        cached_png = os.path.join(cache_dir, f"img_{cache_key}.png")
        if os.path.exists(cached_png) and os.path.getsize(cached_png) > 0:
            return cached_png

        # Konvertierung / Skalierung via sips
        sips = shutil.which("sips")
        if sips:
            try:
                cmd = [sips, "-s", "format", "png", path, "--out", cached_png]
                res = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=3.0)
                if res.returncode == 0 and os.path.exists(cached_png) and os.path.getsize(cached_png) > 0:
                    if fsize > 2 * 1024 * 1024:
                        subprocess.run([sips, "-Z", str(max_dim), cached_png], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=2.0)
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
                    return cached_png
            except (subprocess.TimeoutExpired, OSError):
                pass

        # SVG: Falls sips/magick scheitern, chafa/direkt probieren
        if ext == ".svg":
            return path

        return path if os.path.exists(path) else None

    # 3. Videodatei
    elif ext in VIDEO_EXTENSIONS:
        cached_png = os.path.join(cache_dir, f"vid_{cache_key}.png")
        if os.path.exists(cached_png) and os.path.getsize(cached_png) > 0:
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
                    return cached_png
            except (subprocess.TimeoutExpired, OSError):
                pass

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
            hdr = f"a=T,f={fmt},t=d,c={cols},r={rows},q=2,m={m}"
        else:
            hdr = f"m={m}"
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

        # Halbblock-Zeilen konstruieren (je 2 vertikale Pixel pro Textzelle: oben FG, unten BG)
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
