#!/usr/bin/env python3
"""Tests für die vollwertige Medien- und PDF-Vorschau (Yazi-Parität)."""

import os
import sys
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch

REPO = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, REPO)
os.chdir(REPO)

import easydateien as ed
import easydateien_preview as ep


class TestPreviewYazi(unittest.TestCase):
    """Prüft die Erkennung, Thumbnail-Erzeugung und TUI-Integration von Medienvorschauen."""

    def setUp(self):
        self.orig_cwd = os.getcwd()
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.base = self.tmp_dir.name

        # Testdateien anlegen
        self.txt_path = os.path.join(self.base, "dokument.txt")
        with open(self.txt_path, "w", encoding="utf-8") as f:
            f.write("Dies ist eine Textdatei.\nZweite Zeile.\n")

        # Echtes 1x1 PNG erstellen
        # Minimale gültige PNG-Bytes (1x1 transparenter Pixel)
        self.tiny_png = (
            b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
            b"\x08\x06\x00\x00\x00\x1f\x15c4\x00\x00\x00\rIDATx\x9cc`\x00\x00\x00"
            b"\x02\x00\x01H\xaf\xa4q\x00\x00\x00\x00IEND\xaeB`\x82"
        )
        self.png_path = os.path.join(self.base, "bild.png")
        with open(self.png_path, "wb") as f:
            f.write(self.tiny_png)

        # Echtes minimales 1-Seiten PDF erstellen
        self.mini_pdf = (
            b"%PDF-1.4\n"
            b"1 0 obj <</Type /Catalog /Pages 2 0 R>> endobj\n"
            b"2 0 obj <</Type /Pages /Kids [3 0 R] /Count 1>> endobj\n"
            b"3 0 obj <</Type /Page /Parent 2 0 R /MediaBox [0 0 100 100] /Contents 4 0 R>> endobj\n"
            b"4 0 obj <</Length 20>> stream\n"
            b"0 0 100 100 re f\n"
            b"endstream endobj\n"
            b"xref\n0 5\n0000000000 65535 f \n0000000009 00000 n \n0000000056 00000 n \n0000000111 00000 n \n0000000201 00000 n \n"
            b"trailer <</Size 5 /Root 1 0 R>>\nstartxref\n270\n%%EOF\n"
        )
        self.pdf_path = os.path.join(self.base, "dokument.pdf")
        with open(self.pdf_path, "wb") as f:
            f.write(self.mini_pdf)

        # Echtes minimales 3-Seiten PDF erstellen
        self.multi_pdf = (
            b"%PDF-1.4\n"
            b"1 0 obj <</Type /Catalog /Pages 2 0 R>> endobj\n"
            b"2 0 obj <</Type /Pages /Kids [3 0 R 5 0 R 6 0 R] /Count 3>> endobj\n"
            b"3 0 obj <</Type /Page /Parent 2 0 R /MediaBox [0 0 100 100] /Contents 4 0 R>> endobj\n"
            b"4 0 obj <</Length 20>> stream\n0 0 100 100 re f\nendstream endobj\n"
            b"5 0 obj <</Type /Page /Parent 2 0 R /MediaBox [0 0 100 100] /Contents 4 0 R>> endobj\n"
            b"6 0 obj <</Type /Page /Parent 2 0 R /MediaBox [0 0 100 100] /Contents 4 0 R>> endobj\n"
            b"xref\n0 7\n0000000000 65535 f \n0000000009 00000 n \n0000000056 00000 n \n0000000125 00000 n \n0000000215 00000 n \n0000000285 00000 n \n0000000375 00000 n \n"
            b"trailer <</Size 7 /Root 1 0 R>>\nstartxref\n470\n%%EOF\n"
        )
        self.multi_pdf_path = os.path.join(self.base, "multiseite.pdf")
        with open(self.multi_pdf_path, "wb") as f:
            f.write(self.multi_pdf)

    def tearDown(self):
        try:
            os.chdir(self.orig_cwd)
        except OSError:
            pass
        self.tmp_dir.cleanup()

    def test_media_detection(self):
        """Erkennt vorschaufähige Mediendateien präzise."""
        self.assertTrue(ep.is_previewable_media(self.png_path))
        self.assertTrue(ep.is_previewable_media(self.pdf_path))
        self.assertFalse(ep.is_previewable_media(self.txt_path))
        self.assertFalse(ep.is_previewable_media(self.base))  # Ordner
        self.assertFalse(ep.is_previewable_media("/nicht/vorhanden.png"))

    def test_generate_thumbnail_png(self):
        """Erzeugt bzw. liefert ein gültiges Vorschaubild für PNG."""
        thumb = ep.generate_preview_thumbnail(self.png_path)
        self.assertIsNotNone(thumb)
        self.assertTrue(os.path.exists(thumb))

    def test_generate_thumbnail_pdf(self):
        """Erzeugt ein Vorschaubild für ein PDF-Dokument über Poppler/sips."""
        thumb = ep.generate_preview_thumbnail(self.pdf_path)
        if thumb:  # Kann in Minimalumgebungen ohne Poppler/sips übersprungen werden
            self.assertTrue(os.path.exists(thumb))
            # Zweiter Aufruf muss Cache nutzen
            thumb2 = ep.generate_preview_thumbnail(self.pdf_path)
            self.assertEqual(thumb, thumb2)

    def test_make_kitty_sequence(self):
        """Erzeugt konforme Kitty Graphics Protocol Escape-Sequenzen mit C=1 (kein Cursorvorschub)."""
        seq = ep.make_kitty_image_sequence(self.png_path, cols=20, rows=10, row_pos=5, col_pos=40)
        self.assertTrue(seq.startswith("\033[5;40H"))
        self.assertIn("a=T", seq)
        self.assertIn("C=1", seq)
        self.assertIn("c=20", seq)
        self.assertIn("r=10", seq)
        self.assertTrue(seq.endswith("\033\\"))

    def test_kitty_clear_visible_has_delete_all(self):
        """KITTY_CLEAR_VISIBLE und KITTY_PURGE_ALL nutzen q=2,a=d,d=A gegen Geisterbilder."""
        self.assertIn("a=d", ep.KITTY_CLEAR_VISIBLE)
        self.assertIn("d=A", ep.KITTY_CLEAR_VISIBLE)
        self.assertIn("a=d", ep.KITTY_PURGE_ALL)
        self.assertIn("d=A", ep.KITTY_PURGE_ALL)

    def test_jpeg_always_converted_to_png(self):
        """JPEG-Dateien unter 2MB werden in PNG konvertiert und nicht als rohes JPEG ausgeliefert."""
        # Test-JPEG anlegen
        jpg_path = os.path.join(self.base, "test_foto.jpg")
        # 1x1 JPEG minimal
        sips = shutil.which("sips")
        if sips:
            subprocess.run([sips, "-s", "format", "jpeg", self.png_path, "--out", jpg_path],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            if os.path.exists(jpg_path):
                thumb = ep.generate_preview_thumbnail(jpg_path)
                self.assertIsNotNone(thumb)
                self.assertTrue(thumb.endswith(".png"))

    def test_details_box_preserved_for_pdf_and_image(self):
        """Details (Typ, Größe, Datum, Rechte) bleiben vollständig erhalten."""
        app = ed.EasyDateienApp(self.base)

        # Zu bild.png navigieren
        idx_png = [i for i, it in enumerate(app.items) if it.name == "bild.png"]
        if idx_png:
            app.selected_idx = idx_png[0]
            screen = app.build_screen(80, 24)
            full_screen_text = "\n".join(screen)
            self.assertIn("Details", full_screen_text)
            self.assertIn("Typ:", full_screen_text)
            self.assertIn("PNG-Bild", full_screen_text)
            self.assertIn("Größe:", full_screen_text)
            self.assertIn("Datum:", full_screen_text)
            self.assertIn("Rechte:", full_screen_text)

        # Zu dokument.pdf navigieren
        idx_pdf = [i for i, it in enumerate(app.items) if it.name == "dokument.pdf"]
        if idx_pdf:
            app.selected_idx = idx_pdf[0]
            screen = app.build_screen(80, 24)
            full_screen_text = "\n".join(screen)
            self.assertIn("Details", full_screen_text)
            self.assertIn("Typ:", full_screen_text)
            self.assertIn("PDF-Dokument", full_screen_text)
            self.assertIn("Größe:", full_screen_text)
            self.assertIn("Datum:", full_screen_text)
            self.assertIn("Rechte:", full_screen_text)

    def test_kitty_preview_active_when_supported(self):
        """Im Kitty-fähigen Terminal wird _kitty_preview mit exakter Geometrie gesetzt."""
        app = ed.EasyDateienApp(self.base)
        idx_png = [i for i, it in enumerate(app.items) if it.name == "bild.png"]
        if idx_png:
            app.selected_idx = idx_png[0]
            with patch("easydateien_view.supports_kitty_graphics", return_value=True):
                app.build_screen(80, 24)
                kp = app._kitty_preview
                self.assertIsNotNone(kp)
                png_path, pw, ph, prow, pcol = kp
                self.assertTrue(os.path.exists(png_path))
                self.assertGreater(pw, 0)
                self.assertGreater(ph, 0)
                self.assertGreater(prow, 0)
                self.assertGreater(pcol, 0)

    def test_kitty_preview_cleared_on_dialog(self):
        """Wenn ein modaler Dialog aktiv ist, wird kein Vorschaubild gezeichnet."""
        app = ed.EasyDateienApp(self.base)
        idx_png = [i for i, it in enumerate(app.items) if it.name == "bild.png"]
        if idx_png:
            app.selected_idx = idx_png[0]
            app.active_dialog = "goto_menu"
            with patch("easydateien_view.supports_kitty_graphics", return_value=True):
                app.build_screen(80, 24)
                self.assertIsNone(app._kitty_preview)

    def test_compute_fit_dimensions_preserves_aspect_ratio(self):
        """Verhindert visuelle Verzerrung/Ausdehnung durch exakte Seitenverhältnisberechnung."""
        # A4-Dokument (z. B. 800x1036) in 29x26-Box
        fit_c, fit_r = ep.compute_fit_dimensions(800, 1036, max_cols=29, max_rows=26, font_ratio=0.5)
        self.assertEqual(fit_c, 29)
        self.assertEqual(fit_r, 19)  # Nicht gestreckt auf 26, sondern exakt 19
        self.assertLessEqual(fit_r, 26)

        # Breitbild (1920x1080) in 29x26-Box
        fit_c, fit_r = ep.compute_fit_dimensions(1920, 1080, max_cols=29, max_rows=26, font_ratio=0.5)
        self.assertEqual(fit_c, 29)
        self.assertEqual(fit_r, 8)
        self.assertLessEqual(fit_r, 26)

        # Extrem hohes Bild (500x2000)
        fit_c, fit_r = ep.compute_fit_dimensions(500, 2000, max_cols=29, max_rows=26, font_ratio=0.5)
        self.assertEqual(fit_c, 13)
        self.assertEqual(fit_r, 26)
        self.assertLessEqual(fit_c, 29)

    def test_get_image_pixel_size(self):
        """Liest Pixeldimensionen direkt und fehlerfrei aus."""
        dims = ep.get_image_pixel_size(self.png_path)
        self.assertEqual(dims, (1, 1))

    def test_preview_media_config_toggle(self):
        """preview_media=False schaltet Medienvorschau ab und nutzt Standardlogik."""
        app = ed.EasyDateienApp(self.base)
        app.config["preview_media"] = False
        idx_png = [i for i, it in enumerate(app.items) if it.name == "bild.png"]
        if idx_png:
            app.selected_idx = idx_png[0]
            with patch("easydateien_view.supports_kitty_graphics", return_value=True):
                app.build_screen(80, 24)
                self.assertIsNone(app._kitty_preview)

    def test_get_cached_thumbnail_and_async_worker(self):
        """Prüft, dass get_cached_thumbnail nicht blockiert und der Worker im Hintergrund rendert."""
        import time
        # Frischer Pfad
        pdf_name = "test_async_doc.pdf"
        pdf_path = os.path.join(self.base, pdf_name)
        with open(pdf_path, "wb") as f:
            f.write(self.mini_pdf)

        # Vorab darf kein Thumbnail existieren (weder Disk noch Mem)
        cache_key = ep.get_file_cache_key(pdf_path)
        disk_cache = os.path.join(ep.get_media_cache_dir(), f"pdf_{cache_key}.png")
        if os.path.exists(disk_cache):
            os.remove(disk_cache)
        ep._THUMB_MEM_CACHE.pop(cache_key, None)

        # 1. get_cached_thumbnail muss sofort None liefern (0ms Verzögerung)
        t0 = time.time()
        self.assertIsNone(ep.get_cached_thumbnail(pdf_path))
        t_check = time.time() - t0
        self.assertLess(t_check, 0.05)

        # 2. Worker anfordern
        ep.request_preview(pdf_path)

        # 3. Warten bis Worker fertig ist
        for _ in range(30):
            if ep.poll_preview_ready(pdf_path):
                break
            time.sleep(0.05)

        # 4. Nun muss get_cached_thumbnail sofort den Pfad liefern
        cached = ep.get_cached_thumbnail(pdf_path)
        if cached:  # Falls sips/Poppler verfügbar
            self.assertTrue(os.path.exists(cached))

    def test_rapid_scrolling_nonblocking(self):
        """Schnelles Durchblättern vieler PDF-Dateien blockiert den Hauptthread zu keinem Zeitpunkt."""
        import time
        for i in range(10):
            p = os.path.join(self.base, f"blatter_{i}.pdf")
            with open(p, "wb") as f:
                f.write(self.mini_pdf)

        app = ed.EasyDateienApp(self.base)
        pdf_indices = [idx for idx, it in enumerate(app.items) if it.name.startswith("blatter_")]

        t0 = time.time()
        for idx in pdf_indices:
            app.selected_idx = idx
            app.build_screen(80, 24)
        duration = time.time() - t0

        # 10 PDF-Bildschirme müssen in unter 0.1 Sekunden gerendert sein (<10ms pro Frame)
        self.assertLess(duration, 0.1)

    def test_multipage_pdf_page_count(self):
        """Ermittelt die korrekte Seitenanzahl für 1-seitige und mehrseitige PDFs."""
        self.assertEqual(ep.get_pdf_page_count(self.pdf_path), 1)
        self.assertEqual(ep.get_pdf_page_count(self.multi_pdf_path), 3)

    def test_multipage_pdf_scrolling(self):
        """Blättern mit _scroll_preview schaltet Seiten vor und zurück mit Begrenzungsanschlag."""
        app = ed.EasyDateienApp(self.base)
        idx_multi = [i for i, it in enumerate(app.items) if it.name == "multiseite.pdf"][0]
        app.selected_idx = idx_multi
        app.build_screen(80, 24)

        self.assertEqual(getattr(app, "pdf_page", 1), 1)

        # Seite 1 -> 2 vorblättern
        gescrollt = app._scroll_preview(1)
        self.assertTrue(gescrollt)
        self.assertEqual(app.pdf_page, 2)

        # Seite 2 -> 3 vorblättern
        gescrollt = app._scroll_preview(1)
        self.assertTrue(gescrollt)
        self.assertEqual(app.pdf_page, 3)

        # Anschlag am Ende: darf nicht über Seite 3 hinausgehen
        gescrollt = app._scroll_preview(1)
        self.assertFalse(gescrollt)
        self.assertEqual(app.pdf_page, 3)

        # Seite 3 -> 2 zurückblättern
        gescrollt = app._scroll_preview(-1)
        self.assertTrue(gescrollt)
        self.assertEqual(app.pdf_page, 2)

        # Seite 2 -> 1 zurückblättern
        gescrollt = app._scroll_preview(-1)
        self.assertTrue(gescrollt)
        self.assertEqual(app.pdf_page, 1)

        # Anschlag am Anfang: darf nicht unter Seite 1 gehen
        gescrollt = app._scroll_preview(-1)
        self.assertFalse(gescrollt)
        self.assertEqual(app.pdf_page, 1)

    def test_multipage_pdf_details_card(self):
        """Die Detail-Box zeigt für mehrseitige PDFs die Seitenzahl an."""
        app = ed.EasyDateienApp(self.base)
        idx_multi = [i for i, it in enumerate(app.items) if it.name == "multiseite.pdf"][0]
        app.selected_idx = idx_multi

        # Seite 1 rendern
        lines = app.build_screen(80, 24)
        full_text = "\n".join(lines)
        self.assertIn("Seite:", full_text)
        self.assertIn("1 / 3", full_text)

        # Auf Seite 2 blättern und neu rendern
        app._scroll_preview(1)
        lines = app.build_screen(80, 24)
        full_text = "\n".join(lines)
        self.assertIn("Seite:", full_text)
        self.assertIn("2 / 3", full_text)

    def test_multipage_pdf_page_reset_on_navigation(self):
        """Beim Wechsel auf eine andere Datei wird die Seitenzahl auf 1 zurückgesetzt."""
        app = ed.EasyDateienApp(self.base)
        idx_multi = [i for i, it in enumerate(app.items) if it.name == "multiseite.pdf"][0]
        idx_txt = [i for i, it in enumerate(app.items) if it.name == "dokument.txt"][0]

        app.selected_idx = idx_multi
        app.build_screen(80, 24)
        app._scroll_preview(1)
        self.assertEqual(app.pdf_page, 2)

        # Zu anderer Datei wechseln
        app.selected_idx = idx_txt
        app.build_screen(80, 24)
        self.assertEqual(app.pdf_page, 1)


if __name__ == "__main__":
    unittest.main()
