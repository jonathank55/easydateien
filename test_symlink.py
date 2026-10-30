#!/usr/bin/env python3
"""Tests fuer die Verknuepfungsfunktion (v) in EasyDateien.

Ebene 1: Kernfunktion create_symlink/remove_symlink (Modul easydateien_symlink).
Ebene 2: App-Integration create_symlink_for_selection (Erstellen, Kollision,
         Undo, Fehlerfaelle) ohne Terminal.
"""
import os
import shutil
import sys
import tempfile
import unittest

os.environ.setdefault("HOME", "/tmp/easydateien-test-home")
os.makedirs(os.environ["HOME"], exist_ok=True)
REPO = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, REPO)
os.chdir(REPO)

_shutil_tmp_app = os.path.join(REPO, "easydateien.py")
if not os.path.exists(_shutil_tmp_app):
    shutil.copy(os.path.join(REPO, "easydateien"), _shutil_tmp_app)

import easydateien as ed  # noqa: E402
import easydateien_common as common  # noqa: E402
from easydateien_symlink import create_symlink, remove_symlink, SymlinkError  # noqa: E402


class TestSymlinkKern(unittest.TestCase):
    """Kernfunktion isoliert (Auszug der umfangreichen Entwicklungstestsuite)."""

    def setUp(self):
        self.base = tempfile.mkdtemp(prefix="ed-sl-")
        self.ziel = os.path.join(self.base, "ziel.txt")
        with open(self.ziel, "w") as f:
            f.write("inhalt")

    def tearDown(self):
        shutil.rmtree(self.base, ignore_errors=True)

    def test_erstellen_und_lesen(self):
        lp = os.path.join(self.base, "link")
        create_symlink(self.ziel, lp)
        self.assertTrue(os.path.islink(lp))
        self.assertEqual(os.readlink(lp), self.ziel)
        with open(lp) as f:
            self.assertEqual(f.read(), "inhalt")

    def test_exists(self):
        lp = os.path.join(self.base, "link")
        create_symlink(self.ziel, lp)
        with self.assertRaises(SymlinkError):
            create_symlink(self.ziel, lp)

    def test_overwrite_nur_symlink(self):
        echte = os.path.join(self.base, "echt.txt")
        with open(echte, "w") as f:
            f.write("wichtig")
        with self.assertRaises(SymlinkError):
            create_symlink(self.ziel, echte, overwrite=True)
        with open(echte) as f:
            self.assertEqual(f.read(), "wichtig")

    def test_target_missing(self):
        with self.assertRaises(SymlinkError):
            create_symlink(os.path.join(self.base, "fehlt"), os.path.join(self.base, "l"))

    def test_remove_symlink(self):
        lp = os.path.join(self.base, "link")
        create_symlink(self.ziel, lp)
        remove_symlink(lp)
        self.assertFalse(os.path.lexists(lp))
        self.assertTrue(os.path.isfile(self.ziel))


class TestSymlinkApp(unittest.TestCase):
    """App-Integration: v oeffnet Dialog, Eingabe erstellt Link, Undo entfernt ihn."""

    def setUp(self):
        self.orig_cwd = os.getcwd()
        self.base = tempfile.mkdtemp(prefix="ed-sl-app-")
        self.ziel = os.path.join(self.base, "meine-datei.txt")
        with open(self.ziel, "w") as f:
            f.write("inhalt")
        self.ordner = os.path.join(self.base, "ordner")
        os.makedirs(self.ordner)
        self.app = ed.EasyDateienApp(self.base)

    def tearDown(self):
        os.chdir(self.orig_cwd)
        shutil.rmtree(self.base, ignore_errors=True)

    def test_keymap_v(self):
        self.assertEqual(self.app.keymap.get("v"), "symlink")

    def test_hilfe_enthaelt_v(self):
        items = common.build_help_items(common.KEY_BINDINGS)
        text = "\n".join(items)
        self.assertIn("Verkn", text)

    def test_erstellen_datei(self):
        self.app.selected_idx = 0  # ersten Eintrag
        # Finde Ziel im items
        idx = next(i for i, it in enumerate(self.app.items) if it.name == "meine-datei.txt")
        self.app.selected_idx = idx
        self.app.create_symlink_for_selection("mein-link")
        lp = os.path.join(self.base, "mein-link")
        self.assertTrue(os.path.islink(lp))
        self.assertEqual(os.readlink(lp), self.ziel)
        self.assertIn("Verkn", self.app.status_message)

    def test_erstellen_ordner(self):
        idx = next(i for i, it in enumerate(self.app.items) if it.name == "ordner")
        self.app.selected_idx = idx
        self.app.create_symlink_for_selection("ordner-link")
        lp = os.path.join(self.base, "ordner-link")
        self.assertTrue(os.path.islink(lp))
        self.assertTrue(os.path.isdir(lp))

    def test_erstellen_mit_auswahl(self):
        self.app.selected_paths.add(self.ziel)
        self.app.create_symlink_for_selection("auswahl-link")
        lp = os.path.join(self.base, "auswahl-link")
        self.assertTrue(os.path.islink(lp))
        self.assertEqual(os.readlink(lp), self.ziel)

    def test_erstellen_mehrere_auswahl_abgelehnt(self):
        andere = os.path.join(self.base, "andere.txt")
        with open(andere, "w") as f:
            f.write("x")
        self.app.refresh_items(force=True)
        self.app.selected_paths.add(self.ziel)
        self.app.selected_paths.add(andere)
        self.app.create_symlink_for_selection("multi-link")
        self.assertFalse(os.path.lexists(os.path.join(self.base, "multi-link")))
        self.assertIn("einzelne", self.app.status_message)

    def test_kollision_auto_name(self):
        idx = next(i for i, it in enumerate(self.app.items) if it.name == "meine-datei.txt")
        self.app.selected_idx = idx
        self.app.create_symlink_for_selection("meine-datei.txt - Link")
        self.app.refresh_items(force=True)
        self.app.selected_idx = next(i for i, it in enumerate(self.app.items) if it.name == "meine-datei.txt")
        self.app.create_symlink_for_selection("meine-datei.txt - Link")
        self.assertTrue(os.path.islink(os.path.join(self.base, "meine-datei.txt - Link")))
        self.assertTrue(os.path.islink(os.path.join(self.base, "meine-datei.txt - Link (1)")))

    def test_leerer_name_auto_vorschlag(self):
        # Leerer Name -> automatisch "<Zielname> - Link"
        idx = next(i for i, it in enumerate(self.app.items) if it.name == "meine-datei.txt")
        self.app.selected_idx = idx
        self.app.create_symlink_for_selection("")
        lp = os.path.join(self.base, "meine-datei.txt - Link")
        self.assertTrue(os.path.islink(lp))
        self.assertEqual(os.readlink(lp), self.ziel)

    def test_dialog_leerer_name_auto_vorschlag(self):
        idx = next(i for i, it in enumerate(self.app.items) if it.name == "meine-datei.txt")
        self.app.selected_idx = idx
        self.app.active_dialog = "symlink"
        self.app.dialog_input = ""
        self.app.dialog_cursor = 0
        handled = self.app.handle_dialog_key("ENTER", 0)
        self.assertTrue(handled)
        self.assertIsNone(self.app.active_dialog)
        lp = os.path.join(self.base, "meine-datei.txt - Link")
        self.assertTrue(os.path.islink(lp))

    def test_kein_ziel_leere_liste(self):
        leer = tempfile.mkdtemp(prefix="ed-sl-leer-")
        try:
            app2 = ed.EasyDateienApp(leer)
            app2.create_symlink_for_selection("egal")
            self.assertIn("Keine Datei", app2.status_message)
        finally:
            os.chdir(self.orig_cwd)
            shutil.rmtree(leer, ignore_errors=True)

    def test_undo_entfernt_link(self):
        idx = next(i for i, it in enumerate(self.app.items) if it.name == "meine-datei.txt")
        self.app.selected_idx = idx
        self.app.create_symlink_for_selection("undo-link")
        lp = os.path.join(self.base, "undo-link")
        self.assertTrue(os.path.islink(lp))
        self.assertEqual(len(self.app.undo_stack), 1)
        self.app.undo_last_action()
        self.assertFalse(os.path.lexists(lp))
        self.assertTrue(os.path.isfile(self.ziel))  # Ziel heil
        self.assertEqual(len(self.app.undo_stack), 0)

    def test_undo_ziel_bleibt_heil(self):
        idx = next(i for i, it in enumerate(self.app.items) if it.name == "meine-datei.txt")
        self.app.selected_idx = idx
        self.app.create_symlink_for_selection("ziel-check")
        self.app.undo_last_action()
        with open(self.ziel) as f:
            self.assertEqual(f.read(), "inhalt")

    def test_dialog_rendering(self):
        self.app.active_dialog = "symlink"
        self.app.dialog_input = "test-link"
        self.app.dialog_cursor = 9
        screen = "".join(self.app.build_screen(80, 24))
        plain = screen
        for seq in ("\x1b[0m", "\x1b[1m", "\x1b[7m", "\x1b[3m"):
            plain = plain.replace(seq, "")
        self.assertIn("Verkn", plain)
        self.assertIn("test-link", plain)

    def test_dialog_enter_erstellt(self):
        idx = next(i for i, it in enumerate(self.app.items) if it.name == "meine-datei.txt")
        self.app.selected_idx = idx
        self.app.active_dialog = "symlink"
        self.app.dialog_input = "dialog-link"
        self.app.dialog_cursor = len("dialog-link")
        handled = self.app.handle_dialog_key("ENTER", 0)
        self.assertTrue(handled)
        self.assertIsNone(self.app.active_dialog)
        self.assertTrue(os.path.islink(os.path.join(self.base, "dialog-link")))

    def test_dialog_esc_abbruch(self):
        self.app.active_dialog = "symlink"
        self.app.dialog_input = "egal"
        handled = self.app.handle_dialog_key("ESC", 0)
        self.assertTrue(handled)
        self.assertIsNone(self.app.active_dialog)
        self.assertFalse(os.path.lexists(os.path.join(self.base, "egal")))

    def test_status_leiste_zeigt_dialog(self):
        self.app.active_dialog = "symlink"
        self.app.dialog_input = "abc"
        screen = self.app.build_screen(80, 24)
        last = screen[-1] if screen else ""
        for seq in ("\x1b[0m", "\x1b[1m", "\x1b[7m", "\x1b[3m"):
            last = last.replace(seq, "")
        self.assertIn("Verkn", last)
        self.assertIn("abc", last)


if __name__ == "__main__":
    unittest.main()
