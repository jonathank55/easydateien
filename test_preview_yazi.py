#!/usr/bin/env python3
"""Tests für die vollwertige Medien- und PDF-Vorschau (Yazi-Parität)."""

import os
import sys
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
        if thumb:  # Kann in Minimal-Umgebungen ohne Poppler/sips übersprungen werden
            self.assertTrue(os.path.exists(thumb))
            # Zweiter Aufruf muss Cache nutzen
            thumb2 = ep.generate_preview_thumbnail(self.pdf_path)
            self.assertEqual(thumb, thumb2)

    def test_make_kitty_sequence(self):
        """Erzeugt konforme Kitty Graphics Protocol Escape-Sequenzen."""
        seq = ep.make_kitty_image_sequence(self.png_path, cols=20, rows=10, row_pos=5, col_pos=40)
        self.assertTrue(seq.startswith("\033[5;40H"))
        self.assertIn("\033_Ga=T,f=100,t=d,c=20,r=10,q=2", seq)
        self.assertTrue(seq.endswith("\033\\"))

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
        """Liest Pixel-Dimensionen direkt und fehlerfrei aus."""
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


if __name__ == "__main__":
    unittest.main()
