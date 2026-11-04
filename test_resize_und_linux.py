#!/usr/bin/env python3
"""Tests für dynamische Fenstergrößenanpassung und Linux-Kompatibilität."""

import os
import sys
import unittest
import tempfile
import shutil
import struct
from unittest.mock import patch, MagicMock

REPO = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, REPO)
os.chdir(REPO)

import easydateien_common as common
import easydateien_ui as ui
import easydateien_preview as preview
import easydateien as ed


class TestDynamicResize(unittest.TestCase):
    """Testet die dynamische Anpassung an Terminalgrößenänderungen."""

    def test_env_columns_lines_ignored(self):
        """Stellt sicher, dass gesetzte COLUMNS/LINES die Kernel-Terminalgröße nicht blockieren."""
        os.environ["COLUMNS"] = "130"
        os.environ["LINES"] = "45"
        # get_terminal_size muss bei gültigem tty oder Fallback zuverlässig arbeiten
        sz = common.get_terminal_size((80, 24))
        self.assertIsInstance(sz, os.terminal_size)
        self.assertGreater(sz.columns, 0)
        self.assertGreater(sz.lines, 0)
        # Und die blockierenden Variablen wurden bereinigt
        self.assertNotIn("COLUMNS", os.environ)
        self.assertNotIn("LINES", os.environ)

    def test_sigwinch_pipe_and_flag(self):
        """Prüft, dass _bei_sigwinch das Aufweck-Byte schreibt und das Flag setzt."""
        ui._verwerfe_resize_events()
        ui.check_and_clear_winch_flag()

        # Simuliere SIGWINCH-Signal
        ui._bei_sigwinch(28, None)
        self.assertTrue(ui.check_and_clear_winch_flag())
        self.assertFalse(ui.check_and_clear_winch_flag())

        # Pipe enthält das Aufweck-Byte
        import select
        r, _, _ = select.select([ui.RESIZE_PIPE[0]], [], [], 0.1)
        self.assertIn(ui.RESIZE_PIPE[0], r)
        ui._verwerfe_resize_events()

    def test_konfigurator_uses_shared_resize_pipe(self):
        """Konfigurator und Hauptapp nutzen dieselbe Pipe ohne Konflikte."""
        import easydateien_konfigurator as cfg_mod
        self.assertIs(cfg_mod.RESIZE_PIPE, ui.RESIZE_PIPE)


class TestLinuxCompatibility(unittest.TestCase):
    """Testet alle Linux-spezifischen Funktionspfade."""

    def test_linux_trash_dir_and_detection(self):
        """Prüft XDG-Papierkorb-Erkennung für Linux."""
        with patch.dict(os.environ, {"XDG_DATA_HOME": "/tmp/test-xdg-data"}):
            with patch("easydateien_ui.sys.platform", "linux"):
                trash = ui.get_trash_dir()
                self.assertEqual(trash, "/tmp/test-xdg-data/Trash/files")
                self.assertTrue(ui.is_trash_dir("/tmp/test-xdg-data/Trash"))
                self.assertTrue(ui.is_trash_dir("/tmp/test-xdg-data/Trash/files"))
                self.assertFalse(ui.is_trash_dir("/tmp/test-xdg-data/Documents"))

    def test_linux_opener_default(self):
        """Prüft, dass auf Linux der Standard-Opener auf xdg-open auflöst."""
        app = ed.EasyDateienApp()
        app.config["opener"] = "open %s"
        with patch("easydateien_actions.sys.platform", "linux"):
            fe = ui.FileEntry("/tmp/test.txt", "test.txt")
            with patch("subprocess.Popen") as mock_popen:
                app.open_with_system(fe)
                mock_popen.assert_called_once()
                cmd_arg = mock_popen.call_args[0][0]
                # Shell-Befehl muss xdg-open enthalten
                self.assertTrue(any("xdg-open" in str(a) for a in cmd_arg))

    def test_linux_clipboard_text_copy_and_paste(self):
        """Prüft Zwischenablage-Operationen über Linux wl-copy und xclip."""
        # 1. Wayland wl-copy
        with patch("easydateien_ui.sys.platform", "linux"):
            with patch("shutil.which", side_effect=lambda bin: "/usr/bin/wl-copy" if bin == "wl-copy" else None):
                with patch("subprocess.Popen") as mock_popen:
                    mock_proc = MagicMock()
                    mock_popen.return_value = mock_proc
                    ui._copy_text_now("hallo-linux")
                    mock_popen.assert_called_once()
                    self.assertEqual(mock_popen.call_args[0][0], ["wl-copy"])

            # 2. X11 xclip
            with patch("shutil.which", side_effect=lambda bin: "/usr/bin/xclip" if bin == "xclip" else None):
                with patch("subprocess.Popen") as mock_popen:
                    mock_proc = MagicMock()
                    mock_popen.return_value = mock_proc
                    ui._copy_text_now("hallo-x11")
                    mock_popen.assert_called_once()
                    self.assertEqual(mock_popen.call_args[0][0], ["xclip", "-selection", "clipboard"])

    def test_linux_clipboard_text_get(self):
        """Prüft Auslesen der Zwischenablage unter Linux."""
        with patch("easydateien_ui.sys.platform", "linux"):
            with patch("shutil.which", side_effect=lambda bin: "/usr/bin/wl-paste" if bin == "wl-paste" else None):
                with patch("subprocess.check_output", return_value="inhalt-linux\n") as mock_out:
                    res = ui.get_clipboard_text()
                    self.assertEqual(res, "inhalt-linux\n")

    def test_native_jpeg_dimension_reading_without_sips(self):
        """Liest Pixeldimensionen einer JPEG-Datei ohne sips (nativ in Python)."""
        # Minimaler gültiger JPEG-Header mit SOF0-Segment (Breite: 320, Höhe: 240)
        # SOF0 Marker: 0xFF, 0xC0; Länge: 0x00, 0x11; Precision: 8; Höhe: 240 (0x00F0); Breite: 320 (0x0140)
        sof0 = b"\xff\xc0\x00\x11\x08" + struct.pack(">HH", 240, 320) + b"\x03\x01\x11\x00\x02\x11\x01\x03\x11\x01"
        jpeg_data = b"\xff\xd8" + sof0 + b"\xff\xd9"

        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f:
            f.write(jpeg_data)
            tmp_path = f.name

        try:
            with patch("easydateien_preview.shutil.which", return_value=None):
                dims = preview._read_image_pixel_size_raw(tmp_path)
                self.assertIsNotNone(dims)
                self.assertEqual(dims, (320, 240))
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)


if __name__ == "__main__":
    unittest.main()
