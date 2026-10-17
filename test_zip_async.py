"""Tests fuer die asynchrone ZIP-Erstellung (Hintergrund-Thread + Polling).

Die App darf waehrend einer laufenden ZIP-Erstellung nicht blockieren:
start_zip_creation() kehrt sofort zurueck, poll_zip_creation() meldet den
Fortschritt und schliesst den Job im Hauptthread ab (Status, Undo, Auswahl).
"""

import importlib.util
import os
import sys
import tempfile
import time
import unittest
import zipfile

REPO = os.path.dirname(os.path.abspath(__file__))
APP_PATH = os.path.join(REPO, "easydateien")

import shutil as _shutil
_tmp_app = APP_PATH + ".py"
if not os.path.exists(_tmp_app):
    _shutil.copy(APP_PATH, _tmp_app)
ed = importlib.import_module("easydateien")
ed = importlib.reload(ed)


class TestZipAsync(unittest.TestCase):
    """Asynchrone ZIP-Erstellung: kein Blockieren, korrekter Abschluss."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.base = self._tmp.name
        self.dir_a = os.path.join(self.base, "ordner_a")
        os.makedirs(self.dir_a)
        # Genuegend Dateien, damit der Thread messbar laeuft
        self.gross_dir = os.path.join(self.dir_a, "gross")
        os.makedirs(self.gross_dir)
        for i in range(300):
            with open(os.path.join(self.gross_dir, f"datei_{i:04d}.txt"), "w") as f:
                f.write("x" * 2048)
        with open(os.path.join(self.dir_a, "klein.txt"), "w") as f:
            f.write("klein")
        os.makedirs(os.path.join(self.base, "Downloads"), exist_ok=True)
        os.makedirs(os.path.join(self.base, "Documents"), exist_ok=True)
        os.environ["HOME"] = self.base
        ed.HOME_DIR = self.base
        ed.CONFIG_DIR = os.path.join(self.base, ".config", "easydateien")
        ed.CONFIG_FILE = os.path.join(ed.CONFIG_DIR, "config.json")
        self.app = ed.EasyDateienApp(self.dir_a)

    def tearDown(self):
        # Laufenden Thread sauber beenden, bevor das Temp-Verzeichnis verschwindet
        thread = getattr(self.app, "_zip_thread", None)
        if thread is not None and thread.is_alive():
            thread.join(timeout=10.0)
        self._tmp.cleanup()

    def _warte_auf_abschluss(self, timeout=15.0):
        """Pollt wie die Hauptschleife, bis der Job abgeschlossen ist."""
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if self.app.poll_zip_creation():
                return True
            thread = getattr(self.app, "_zip_thread", None)
            if thread is None:
                return True
            time.sleep(0.01)
        return False

    def test_start_kehrt_sofort_zurueck(self):
        self.app.selected_paths.add(self.gross_dir)
        t0 = time.monotonic()
        gestartet = self.app.start_zip_creation()
        elapsed = time.monotonic() - t0
        self.assertTrue(gestartet)
        # Start darf auch bei 300 Dateien nicht blockieren
        self.assertLess(elapsed, 2.0)
        self.assertIn("ZIP wird erstellt", self.app.status_message)

    def test_zip_wird_erstellt_und_abgeschlossen(self):
        self.app.selected_paths.add(self.gross_dir)
        self.assertTrue(self.app.start_zip_creation())
        self.assertTrue(self._warte_auf_abschluss())
        self.assertIsNone(self.app._zip_thread)
        zips = [f for f in os.listdir(self.dir_a) if f.endswith(".zip")]
        self.assertEqual(len(zips), 1)
        zip_path = os.path.join(self.dir_a, zips[0])
        self.assertTrue(zipfile.is_zipfile(zip_path))
        with zipfile.ZipFile(zip_path) as zf:
            self.assertEqual(len(zf.namelist()), 300)
        # Abschluss im Hauptthread: Status, Undo, Auswahl
        self.assertIn("ZIP erstellt", self.app.status_message)
        self.assertEqual(self.app.status_level, "success")
        self.assertTrue(any(a.action_type == "create_zip" for a in self.app.undo_stack))
        self.assertEqual(self.app.items[self.app.selected_idx].name, zips[0])
        # Auswahl wurde geleert
        self.assertEqual(self.app.selected_paths, set())

    def test_app_bleibt_waehrend_erstellung_benutzbar(self):
        self.app.selected_paths.add(self.gross_dir)
        self.assertTrue(self.app.start_zip_creation())
        # Waehrend der Thread laeuft: Navigation und andere Aktionen funktionieren
        idx_vorher = self.app.selected_idx
        self.app.selected_idx = min(len(self.app.items) - 1, idx_vorher + 1)
        self.app.toggle_select()
        self.app.toggle_select()
        self.assertTrue(self.app._zip_thread.is_alive() or self.app._zip_thread is None)
        # Polling meldet Fortschritt, ohne abzuschliessen
        self.app.poll_zip_creation()
        self.assertTrue(self._warte_auf_abschluss())
        self.assertIn("ZIP erstellt", self.app.status_message)

    def test_doppelter_start_wird_abgewiesen(self):
        self.app.selected_paths.add(self.gross_dir)
        self.assertTrue(self.app.start_zip_creation())
        # Solange der erste Job laeuft, darf kein zweiter starten
        if self.app._zip_thread.is_alive():
            self.assertFalse(self.app.start_zip_creation())
            self.assertIn("bereits", self.app.status_message)
        self.assertTrue(self._warte_auf_abschluss())

    def test_kein_ziel_keine_aktion(self):
        self.app.selected_paths.clear()
        self.app.items = []
        self.assertFalse(self.app.start_zip_creation())
        self.assertIn("ausgew\u00e4hlt", self.app.status_message)

    def test_nur_eine_datei_name_aus_datei(self):
        self.app.selected_paths.clear()
        self.app.selected_paths.add(os.path.join(self.dir_a, "klein.txt"))
        self.assertTrue(self.app.start_zip_creation())
        self.assertTrue(self._warte_auf_abschluss())
        self.assertIn("klein.txt.zip", os.listdir(self.dir_a))
        with zipfile.ZipFile(os.path.join(self.dir_a, "klein.txt.zip")) as zf:
            self.assertEqual(zf.namelist(), ["klein.txt"])

    def test_fehler_im_thread_erzeugt_fehlermeldung(self):
        # Ziel loeschen, bevor der Thread startet: os.walk/os.path.isdir schlaegt fehl
        self.app.selected_paths.add(self.gross_dir)
        self.assertTrue(self.app.start_zip_creation())
        # Thread sofort stoppen und Fehler simulieren
        self.app._zip_thread.join(timeout=10.0)
        self.app._zip_result = {"dest": os.path.join(self.dir_a, "kaputt.zip"), "skipped": 0, "error": RuntimeError("Testfehler")}
        # Datei existiert nicht -> os.remove schlaegt fehl (abgefangen), Status trotzdem gesetzt
        self.assertTrue(self.app.poll_zip_creation())
        self.assertIn("Fehler beim Erstellen des ZIP-Archivs", self.app.status_message)
        self.assertEqual(self.app.status_level, "error")
        self.assertFalse(any(a.action_type == "create_zip" for a in self.app.undo_stack))

    def test_synchroner_pfad_create_zip_archive(self):
        # Bestehender synchroner Aufruf (Tests) muss unveraendert funktionieren
        self.app.selected_paths.add(os.path.join(self.dir_a, "klein.txt"))
        zip_path = self.app.create_zip_archive()
        self.assertTrue(zip_path and zipfile.is_zipfile(zip_path))
        self.assertEqual(os.path.basename(zip_path), "klein.txt.zip")
        self.assertIsNone(self.app._zip_thread)
        self.assertIn("ZIP erstellt", self.app.status_message)

    def test_undo_create_zip_loescht_archiv(self):
        self.app.selected_paths.add(os.path.join(self.dir_a, "klein.txt"))
        zip_path = self.app.create_zip_archive()
        self.assertTrue(os.path.exists(zip_path))
        self.app.undo_last_action()
        self.assertFalse(os.path.exists(zip_path))


if __name__ == "__main__":
    unittest.main()
