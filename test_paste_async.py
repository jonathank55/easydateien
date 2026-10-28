"""Tests fuer das asynchrone Einfuegen (Hintergrund-Thread + Polling).

Grosse Kopier- und Verschiebevorgaenge duerfen die App nicht blockieren:
start_paste() kehrt sofort zurueck, poll_paste() meldet den Fortschritt und
schliesst den Job im Hauptthread ab (Status, Undo, Zwischenablage, Anzeige).
"""

import importlib.util
import os
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

REPO = os.path.dirname(os.path.abspath(__file__))
APP_PATH = os.path.join(REPO, "easydateien")

import shutil as _shutil
_tmp_app = APP_PATH + ".py"
if not os.path.exists(_tmp_app):
    _shutil.copy(APP_PATH, _tmp_app)
ed = importlib.import_module("easydateien")
ed = importlib.reload(ed)


class TestPasteAsync(unittest.TestCase):
    """Asynchrones Einfuegen: kein Blockieren, korrekter Abschluss, Undo."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.base = self._tmp.name
        self.src_dir = os.path.join(self.base, "quelle")
        self.dst_dir = os.path.join(self.base, "ziel")
        os.makedirs(self.src_dir)
        os.makedirs(self.dst_dir)
        # Grosser Ordner: 250 Dateien
        self.big_src = os.path.join(self.src_dir, "gross")
        os.makedirs(self.big_src)
        for i in range(250):
            with open(os.path.join(self.big_src, f"d_{i:04d}.txt"), "w") as f:
                f.write("y" * 2048)
        os.makedirs(os.path.join(self.base, "Downloads"), exist_ok=True)
        os.makedirs(os.path.join(self.base, "Documents"), exist_ok=True)
        os.environ["HOME"] = self.base
        ed.HOME_DIR = self.base
        ed.CONFIG_DIR = os.path.join(self.base, ".config", "easydateien")
        ed.CONFIG_FILE = os.path.join(ed.CONFIG_DIR, "config.json")
        self.orig_cwd = os.getcwd()
        self.app = ed.EasyDateienApp(self.dst_dir)
        self.app.clipboard_mode = "copy"
        self.app.clipboard_paths = [self.big_src]

    def tearDown(self):
        thread = getattr(self.app, "_paste_thread", None)
        if thread is not None and thread.is_alive():
            thread.join(timeout=10.0)
        os.chdir(self.orig_cwd)
        self._tmp.cleanup()

    def _warte_auf_abschluss(self, timeout=15.0):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if self.app.poll_paste():
                return True
            if getattr(self.app, "_paste_thread", None) is None:
                return True
            time.sleep(0.01)
        return False

    def test_start_kehrt_sofort_zurueck(self):
        t0 = time.monotonic()
        gestartet = self.app.start_paste(list(self.app.clipboard_paths))
        elapsed = time.monotonic() - t0
        self.assertTrue(gestartet)
        self.assertLess(elapsed, 2.0)
        self.assertIn("Einf\u00fcgen l\u00e4uft", self.app.status_message)

    def test_grosser_ordner_wird_vollstaendig_kopiert(self):
        self.assertTrue(self.app.start_paste(list(self.app.clipboard_paths)))
        self.assertTrue(self._warte_auf_abschluss())
        self.assertIsNone(self.app._paste_thread)
        ziel_ordner = os.path.join(self.dst_dir, "gross")
        self.assertTrue(os.path.isdir(ziel_ordner))
        self.assertEqual(len(os.listdir(ziel_ordner)), 250)
        # Original bleibt bei Kopieren erhalten
        self.assertEqual(len(os.listdir(self.big_src)), 250)
        # Abschluss: Status, Undo, Zwischenablage geleert
        self.assertIn("eingef\u00fcgt", self.app.status_message)
        self.assertEqual(self.app.status_level, "success")
        self.assertTrue(any(a.action_type == "paste" for a in self.app.undo_stack))
        self.assertEqual(self.app.clipboard_paths, [])
        self.assertIsNone(self.app.clipboard_mode)

    def test_app_bleibt_waehrend_paste_benutzbar(self):
        self.assertTrue(self.app.start_paste(list(self.app.clipboard_paths)))
        idx_vorher = self.app.selected_idx
        self.app.selected_idx = min(len(self.app.items) - 1, idx_vorher + 1)
        self.app.toggle_select()
        self.app.toggle_select()
        self.app.poll_paste()
        self.assertTrue(self._warte_auf_abschluss())
        self.assertIn("eingef\u00fcgt", self.app.status_message)

    def test_doppelter_start_wird_abgewiesen(self):
        self.assertTrue(self.app.start_paste(list(self.app.clipboard_paths)))
        if self.app._paste_thread.is_alive():
            self.assertFalse(self.app.start_paste(list(self.app.clipboard_paths)))
            self.assertIn("bereits", self.app.status_message)
        self.assertTrue(self._warte_auf_abschluss())

    def test_cut_verschiebt_und_leert_ziel(self):
        self.app.clipboard_mode = "cut"
        self.assertTrue(self.app.start_paste(list(self.app.clipboard_paths)))
        self.assertTrue(self._warte_auf_abschluss())
        self.assertTrue(os.path.isdir(os.path.join(self.dst_dir, "gross")))
        self.assertFalse(os.path.exists(self.big_src))
        self.assertIn("eingef\u00fcgt", self.app.status_message)

    def test_namenskollision_erzeugt_nummerierung(self):
        # Ziel existiert bereits -> Kopie erhaelt (1)
        os.makedirs(os.path.join(self.dst_dir, "gross"))
        self.assertTrue(self.app.start_paste(list(self.app.clipboard_paths)))
        self.assertTrue(self._warte_auf_abschluss())
        self.assertTrue(os.path.isdir(os.path.join(self.dst_dir, "gross (1)")))
        self.assertIn("eingef\u00fcgt", self.app.status_message)

    def test_undo_nach_paste_stellt_zustand_her(self):
        self.assertTrue(self.app.start_paste(list(self.app.clipboard_paths)))
        self.assertTrue(self._warte_auf_abschluss())
        self.assertTrue(os.path.isdir(os.path.join(self.dst_dir, "gross")))
        self.app.undo_last_action()
        self.assertFalse(os.path.exists(os.path.join(self.dst_dir, "gross")))
        # Original bleibt erhalten (Kopie)
        self.assertTrue(os.path.isdir(self.big_src))

    def test_undo_nach_cut_stellt_quelle_wieder_her(self):
        self.app.clipboard_mode = "cut"
        self.assertTrue(self.app.start_paste(list(self.app.clipboard_paths)))
        self.assertTrue(self._warte_auf_abschluss())
        self.assertFalse(os.path.exists(self.big_src))
        self.app.undo_last_action()
        self.assertTrue(os.path.isdir(self.big_src))
        self.assertEqual(len(os.listdir(self.big_src)), 250)

    def test_paste_clipboard_startet_async(self):
        # Kompletter Pfad ueber paste_clipboard (wie Taste p)
        self.app.paste_clipboard()
        self.assertIn("Einf\u00fcgen l\u00e4uft", self.app.status_message)
        self.assertIsNotNone(self.app._paste_thread)
        self.assertTrue(self._warte_auf_abschluss())
        self.assertTrue(os.path.isdir(os.path.join(self.dst_dir, "gross")))

    def test_paste_clipboard_leer(self):
        self.app.clipboard_paths = []
        self.app.clipboard_mode = None
        # Keine macOS-Zwischenablage in der Testumgebung -> leer
        with patch("easydateien_actions.get_macos_clipboard_files", return_value=[]):
            self.app.paste_clipboard()
            self.assertIsNone(getattr(self.app, "_paste_thread", None))
            self.assertIn("Zwischenablage leer", self.app.status_message)

    def test_synchroner_pfad_perform_paste(self):
        # Direkter synchroner Aufruf muss unveraendert funktionieren
        self.app._perform_paste(list(self.app.clipboard_paths))
        self.assertTrue(os.path.isdir(os.path.join(self.dst_dir, "gross")))
        self.assertIn("eingef\u00fcgt", self.app.status_message)
        self.assertTrue(any(a.action_type == "paste" for a in self.app.undo_stack))

    def test_fehler_im_thread_erzeugt_fehlermeldung(self):
        self.assertTrue(self.app.start_paste(list(self.app.clipboard_paths)))
        self.app._paste_thread.join(timeout=10.0)
        self.app._paste_result = {
            "records": [], "backups": [], "error": RuntimeError("Testfehler"),
            "success": 0, "last_name": "",
        }
        self.assertTrue(self.app.poll_paste())
        self.assertIn("Fehler beim Einf\u00fcgen", self.app.status_message)
        self.assertEqual(self.app.status_level, "error")
        self.assertFalse(any(a.action_type == "paste" for a in self.app.undo_stack))


if __name__ == "__main__":
    unittest.main()
