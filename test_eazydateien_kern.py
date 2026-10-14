#!/usr/bin/env python3
"""Regressionstests für EasyDateien — Kernfunktionen ohne Terminal.

Jeder Test deckt eine zentrale Funktion ab. Läuft überall (CI, lokale Sandbox)
und benötigt kein interaktives Terminal und keine macOS-spezifischen Tools.
App-Tests laden das Hauptprogramm unter dem Modulnamen `easydateien_app`,
damit Konfigurationsdateien des echten Systems unberührt bleiben.
"""

import importlib.util
import os
import sys
import tempfile
import unittest
import re
import zipfile

import easydateien_common as common

REPO = os.path.dirname(os.path.abspath(__file__))
APP_PATH = os.path.join(REPO, "easydateien")

import shutil as _shutil
_tmp_app = APP_PATH + ".py"
if not os.path.exists(_tmp_app):
    _shutil.copy(APP_PATH, _tmp_app)
ed = importlib.import_module("easydateien")
ed = importlib.reload(ed)


class TestKeyBindings(unittest.TestCase):
    """Tastenbelegungen: Single Source of Truth und Konfliktfreiheit."""

    def test_keymap_ohne_doppelbelegung(self):
        keymap = common.build_keymap(None)
        self.assertIsInstance(keymap, dict)
        self.assertGreater(len(keymap), 10)

    def test_wichtige_tasten_vorhanden(self):
        keymap = common.build_keymap(None)
        for taste in ("g", "-", "h", "q", "DELETE", "c", "x", "p", "u"):
            self.assertIn(taste, keymap, f"Taste '{taste}' fehlt in keymap")

    def test_mark_dir_und_goto_aktiv(self):
        keymap = common.build_keymap(None)
        self.assertEqual(keymap.get("-"), "mark_dir")
        self.assertEqual(keymap.get("g"), "goto")

    def test_keybindings_aus_config_kompatibel(self):
        bindings = common.get_keybindings_from_config({})
        self.assertEqual(bindings, common.KEY_BINDINGS)

    def test_ungueltige_keybinding_tokens_werden_bereinigt(self):
        # Fruehere Fehler erzeugten leere/ungueltige Token in der User-Config;
        # diese duerfen die Validierung nie sperren (ESC aus dem Editor).
        kaputt = {
            "keybindings": [
                ["Navigation & Ansicht", "goto", "Gehe zu", ["g", "", "  "], "Gehe zu"],
                ["Dateioperationen", "trash", "Löschen", ["", "UNBEKANNT"], "Papierkorb"],
            ]
        }
        bindings = common.get_keybindings_from_config(kaputt)
        by_action = {b[1]: b for b in bindings}
        self.assertEqual(by_action["trash"][3], ("DELETE",),
                         "Ungültige Token wurden nicht bereinigt; trash-Standard fehlt")
        for _s, _a, _d, keys, _desc in bindings:
            for k in keys:
                self.assertTrue(k and k.strip() and k not in ("UNBEKANNT", "resize"),
                                f"Ungültiges Token {k!r} verblieb in der Belegung")
        try:
            common.build_keymap(kaputt)
        except ValueError as e:
            self.fail(f"Build_keymap scheitert an bereinigten Belegungen: {e}")

    def test_trash_standard_ist_entfernen(self):
        self.assertEqual(common.KEY_BINDINGS[[b[1] for b in common.KEY_BINDINGS].index("trash")][3],
                         ("DELETE",))

    def test_hilfemenue_dynamisch_und_vollstaendig(self):
        items = common.build_help_items(common.KEY_BINDINGS)
        text = "\n".join(items)
        for expected in ("Gehe zu", "merken", "Hilfe", "beenden", "Navigation & Ansicht"):
            self.assertIn(expected, text)
        self.assertIn("Navigation & Ansicht", items[0])


class TestHilfsfunktionen(unittest.TestCase):
    """Zentrale Hilfsfunktionen der common-Bibliothek."""

    def test_str_width_und_pad_to_width(self):
        self.assertEqual(common.str_width("abc"), 3)
        self.assertGreaterEqual(common.str_width("äöü"), 3)

    def test_format_keys(self):
        self.assertEqual(common.format_keys(("UP",)), "↑")
        self.assertIn(" / ", common.format_keys(("ESC", "CTRL_C")))

    def test_natural_key(self):
        self.assertLess(ed.natural_key("datei2"), ed.natural_key("datei10"))
        self.assertEqual(ed.natural_key("ABC"), ed.natural_key("abc"))

    def test_listing_signature_erkennt_aenderung(self):
        e1 = ed.FileEntry("/x/a.txt", "a.txt", None)
        e1.size = 1
        e1.mtime = 100.0
        sig1 = ed.listing_signature([e1])
        e1.size = 2
        self.assertNotEqual(sig1, ed.listing_signature([e1]))

    def test_get_file_type_desc(self):
        class Fake:
            is_symlink = False
            is_broken = False
            is_dir = True
            is_exec = False
            ext = ""

        self.assertEqual(ed.get_file_type_desc(Fake()), "Verzeichnis")
        Fake.is_dir = False
        Fake.ext = ".py"
        self.assertEqual(ed.get_file_type_desc(Fake()), "Python-Skript")


class TestAppKern(unittest.TestCase):
    """App-Kernfunktionen mit echten temporären Verzeichnissen."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.base = self._tmp.name
        self.dir_a = os.path.join(self.base, "ordner_a")
        self.dir_b = os.path.join(self.base, "ordner_b")
        os.makedirs(self.dir_a)
        os.makedirs(self.dir_b)
        with open(os.path.join(self.dir_a, "datei.txt"), "w") as f:
            f.write("test")
        os.makedirs(os.path.join(self.base, "Downloads"), exist_ok=True)
        os.makedirs(os.path.join(self.base, "Documents"), exist_ok=True)
        os.environ["HOME"] = self.base
        ed.HOME_DIR = self.base
        ed.CONFIG_DIR = os.path.join(self.base, ".config", "easydateien")
        ed.CONFIG_FILE = os.path.join(ed.CONFIG_DIR, "config.json")
        self.app = ed.EasyDateienApp(self.dir_a)

    def tearDown(self):
        self._tmp.cleanup()

    def test_start_im_verzeichnis(self):
        self.assertEqual(self.app.current_dir, self.dir_a)
        self.assertGreaterEqual(len(self.app.items), 1)

    def test_verzeichniswechsel_und_parent(self):
        self.app.enter_directory(self.dir_b)
        self.assertEqual(self.app.current_dir, self.dir_b)
        self.app.go_parent_directory()
        self.assertEqual(self.app.current_dir, self.base)

    def test_navigation_setzt_last_visited_nicht(self):
        self.app.enter_directory(self.dir_b)
        self.assertIsNone(self.app.last_visited_dir)

    def test_aktion_setzt_last_visited(self):
        self.app.toggle_select()
        self.assertEqual(self.app.last_visited_dir, self.dir_a)
        self.app.enter_directory(self.dir_b)
        self.app.touch_last_used_dir()
        self.assertEqual(self.app.last_visited_dir, self.dir_b)

    def test_markieren_und_g_sprung(self):
        self.app.marked_dir = self.app.current_dir
        self.app.enter_directory(self.dir_b)
        self.app.active_dialog = "goto_menu"
        self.app.handle_dialog_key("-", None)
        self.assertEqual(self.app.current_dir, self.dir_a)

    def test_g_sprung_fallback_zuletzt_verwendet(self):
        self.app.toggle_select()
        self.app.enter_directory(self.dir_b)
        self.app.active_dialog = "goto_menu"
        self.app.handle_dialog_key("-", None)
        self.assertEqual(self.app.current_dir, self.dir_a)

    def test_gemerkter_ordner_hat_immer_vorrang(self):
        self.app.marked_dir = self.dir_a
        self.app.toggle_select()
        self.app.enter_directory(self.dir_b)
        self.app.touch_last_used_dir()
        self.app.enter_directory(self.base)
        self.app.active_dialog = "goto_menu"
        self.app.handle_dialog_key("-", None)
        self.assertEqual(self.app.current_dir, self.dir_a)
        self.app.active_dialog = "goto_menu"
        self.app.handle_dialog_key("-", None)
        self.assertEqual(self.app.current_dir, self.dir_a)

    def test_zeigerposition_wird_bei_g_sprung_wiederhergestellt(self):
        for i, it in enumerate(self.app.items):
            if it.name == "datei.txt":
                self.app.selected_idx = i
                break
        self.app.marked_dir = self.dir_a
        self.app.enter_directory(self.dir_b)
        self.app.active_dialog = "goto_menu"
        self.app.handle_dialog_key("-", None)
        self.assertEqual(self.app.current_dir, self.dir_a)
        self.assertEqual(self.app.items[self.app.selected_idx].name, "datei.txt")

    def test_zeigerposition_wird_beim_verlassen_gespeichert(self):
        self.app.selected_idx = 0
        self.app.enter_directory(self.dir_b)
        self.assertEqual(self.app.dir_cursor_memory.get(self.dir_a), 0)

    def test_gemerkter_ordner_gilt_bis_neues_merken(self):
        self.app.marked_dir = self.dir_a
        self.app.marked_dir = self.dir_b
        self.app.enter_directory(self.base)
        self.app.active_dialog = "goto_menu"
        self.app.handle_dialog_key("-", None)
        self.assertEqual(self.app.current_dir, self.dir_b)

    def test_g_sprung_ohne_verfuegbaren_ordner(self):
        self.app.last_visited_dir = None
        self.app.marked_dir = None
        self.app.active_dialog = "goto_menu"
        self.app.handle_dialog_key("-", None)
        self.assertEqual(self.app.current_dir, self.dir_a)
        self.assertIn("verfügbar", self.app.status_message)

    def test_goto_menu_gd_gf_ht(self):
        self.app.enter_directory(self.base)
        self.app.active_dialog = "goto_menu"
        self.app.handle_dialog_key("d", None)
        self.assertTrue(self.app.current_dir.endswith("Downloads"))
        self.app.active_dialog = "goto_menu"
        self.app.handle_dialog_key("f", None)
        self.assertTrue(self.app.current_dir.endswith("Documents"))

    def test_cursor_bleibt_bei_refresh(self):
        names = [it.name for it in self.app.items]
        self.assertIn("datei.txt", names)
        idx = names.index("datei.txt")
        self.app.selected_idx = idx
        self.app.refresh_items()
        self.assertEqual(self.app.items[self.app.selected_idx].name, "datei.txt")

    def test_markieren_einer_datei(self):
        for it in self.app.items:
            if it.name == "datei.txt":
                self.app.selected_idx = self.app.items.index(it)
                break
        self.app.toggle_select()
        self.assertIn(os.path.join(self.dir_a, "datei.txt"), self.app.selected_paths)

    def test_auswahl_aufheben(self):
        self.app.selected_paths.add(os.path.join(self.dir_a, "datei.txt"))
        self.app.toggle_select_all()
        self.assertEqual(self.app.selected_paths, set())

    def test_filter(self):
        self.app.filter_query = "datei"
        self.app.refresh_items()
        self.assertTrue(all("datei" in it.name.lower() for it in self.app.items))

    def test_ordner_erstellen_mit_markierung(self):
        import shutil as _sh
        for n in ("x.txt", "y.txt", "z.txt"):
            open(os.path.join(self.dir_a, n), "w").write(n)
        self.app.refresh_items()
        self.app.selected_paths = {os.path.join(self.dir_a, "x.txt"), os.path.join(self.dir_a, "y.txt")}
        self.app.active_dialog = "new"
        self.app.dialog_input = "Sammelordner/"
        self.app.handle_dialog_key("ENTER", None)
        self.assertIn("Sammelordner", self.app.status_message)
        self.assertTrue(os.path.exists(os.path.join(self.dir_a, "Sammelordner/x.txt")))
        self.assertTrue(os.path.exists(os.path.join(self.dir_a, "Sammelordner/y.txt")))
        self.assertTrue(os.path.exists(os.path.join(self.dir_a, "z.txt")))
        self.assertFalse(self.app.selected_paths)
        self.app.undo_last_action()
        self.assertTrue(os.path.exists(os.path.join(self.dir_a, "x.txt")))
        self.assertFalse(os.path.exists(os.path.join(self.dir_a, "Sammelordner")))

    def test_ordner_erstellen_ohne_verschiebung_bei_vormerkung(self):
        open(os.path.join(self.dir_a, "v.txt"), "w").write("v")
        self.app.refresh_items()
        self.app.clipboard_mode = "copy"
        self.app.clipboard_paths = [os.path.join(self.dir_a, "v.txt")]
        self.app.selected_paths = {os.path.join(self.dir_a, "v.txt")}
        self.app.active_dialog = "new"
        self.app.dialog_input = "KeinVerschub/"
        self.app.handle_dialog_key("ENTER", None)
        self.assertTrue(os.path.exists(os.path.join(self.dir_a, "v.txt")))
        self.assertTrue(os.path.isdir(os.path.join(self.dir_a, "KeinVerschub")))
        self.assertEqual(os.listdir(os.path.join(self.dir_a, "KeinVerschub")), [])

    def test_konsole_tabs_expandiert_und_umbruch(self):
        import shutil as _sh
        for n in ("a.txt", "b.txt"):
            open(os.path.join(self.dir_a, n), "w").write(n)
        self.app.show_console = True
        self.app.console_focused = True
        self.app.run_console_command("printf 'alpha\\tbeta\\tgamma-lang-dies-ist-ein-sehr-langes-wort\\n'", None, None)
        self.app.refresh_items()
        # Tabs duerfen nirgends landen
        for l in self.app.console_output_lines:
            self.assertNotIn("\t", l)
        # Schmale Konsole: Umbruch statt Abschneiden, Inhalt bleibt erhalten
        lines = self.app.get_console_display_lines(28, 10)
        joined = "".join(re.sub(r"\x1b\[[0-9;]*[a-zA-Z]", "", l) for l in lines)
        self.assertIn("gamma-lang", joined)
        for l in lines:
            self.assertLessEqual(len(re.sub(r"\x1b\[[0-9;]*[a-zA-Z]", "", l)), 28)


    def test_zip_erstellen_und_entpacken(self):
        for it in self.app.items:
            if it.name == "datei.txt":
                self.app.selected_idx = self.app.items.index(it)
                break
        self.app.selected_paths.add(os.path.join(self.dir_a, "datei.txt"))
        zip_path = self.app.create_zip_archive()
        self.assertTrue(zip_path and zipfile.is_zipfile(zip_path))
        with zipfile.ZipFile(zip_path) as zf:
            self.assertIn("datei.txt", zf.namelist())

    def test_undo_stack_nach_dateiaktion(self):
        vorher = len(self.app.undo_stack)
        neuer_pfad = os.path.join(self.dir_a, "neu.txt")
        with open(neuer_pfad, "a"):
            pass
        self.app.undo_stack.append(ed.UndoAction("create", "Erstellen von neu.txt", {"path": neuer_pfad}))
        self.assertEqual(len(self.app.undo_stack), vorher + 1)

    def test_konfiguration_laden_ergaenzt_fehlende_schluessel(self):
        cfg = self.app.load_config()
        self.assertIsInstance(cfg, dict)
        self.assertGreater(len(cfg), 0)

    def test_statusmeldung_setzen(self):
        self.app.set_status("Testnachricht", "success")
        self.assertEqual(self.app.status_message, "Testnachricht")
        self.assertEqual(self.app.status_level, "success")

    def test_get_short_dir(self):
        kurz = self.app.get_short_dir(os.path.join(self.base, "ordner_a"))
        self.assertIsInstance(kurz, str)
        self.assertTrue(kurz)


if __name__ == "__main__":
    unittest.main()
