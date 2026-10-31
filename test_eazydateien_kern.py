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
from unittest.mock import patch
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
        self.assertEqual(by_action["trash"][3], ("DELETE", "BACKSPACE"),
                         "Ungültige Token wurden nicht bereinigt; trash-Standard fehlt")
        for _s, _a, _d, keys, _desc in bindings:
            for k in keys:
                self.assertTrue(k and k.strip() and k not in ("UNBEKANNT", "resize"),
                                f"Ungültiges Token {k!r} verblieb in der Belegung")
        try:
            common.build_keymap(kaputt)
        except ValueError as e:
            self.fail(f"Build_keymap scheitert an bereinigten Belegungen: {e}")

    def test_entfernen_loescht(self):
        # Entfernen (DELETE) muss auf Löschen (trash) gelegt sein (Standardbelegung)
        keymap = common.build_keymap(None)
        self.assertEqual(keymap.get("DELETE"), "trash",
                         "DELETE ist nicht auf Löschen gelegt — Entfernen würde nichts auslösen")

    def test_konfigurator_read_key_sondertasten(self):
        import easydateien_konfigurator as k
        r, w = os.pipe()
        def t(seq):
            os.write(w, seq)
            return k.read_key(r, timeout=0.3)
        self.assertEqual(t(b"\x1b[3~"), "DELETE")
        self.assertEqual(t(b"\x1b[3;5~"), "DELETE")
        self.assertEqual(t(b"\x1b[2~"), "INSERT")
        self.assertEqual(t(b"\x1b[Z"), "SHIFT_TAB")
        self.assertEqual(t(b"\x1b[9~"), "UNBEKANNT")
        self.assertEqual(t(b"\x7f"), "UNBEKANNT")
        self.assertEqual(t(b"\x1b"), "ESC")

    def test_trash_standard_ist_entfernen(self):
        self.assertEqual(common.KEY_BINDINGS[[b[1] for b in common.KEY_BINDINGS].index("trash")][3],
                         ("DELETE", "BACKSPACE"))

    def test_hilfemenue_dynamisch_und_vollstaendig(self):
        items = common.build_help_items(common.KEY_BINDINGS)
        text = "\n".join(items)
        for expected in ("Gehe zu", "merken", "Hilfe", "beenden", "Navigation & Ansicht"):
            self.assertIn(expected, text)
        self.assertIn("Navigation & Ansicht", items[0])

    def test_neue_aktion_wird_in_ihren_abschnitt_einsortiert(self):
        # Alte gespeicherte Config ohne die neueste Aktion: Die Aktion darf nicht
        # als zweiter Abschnitt gleichen Namens ans Ende geraet (Regression:
        # "Dateioperationen" erschien doppelt im Hilfemenue).
        custom = [list(b) for b in common.KEY_BINDINGS if b[1] != "symlink"]
        bindings = common.get_keybindings_from_config({"keybindings": custom})
        items = common.build_help_items(bindings)
        sections = [l.strip() for l in items
                    if l.strip() in ("Navigation & Ansicht", "Dateioperationen", "Verwaltung")]
        self.assertEqual(sections.count("Dateioperationen"), 1)
        # v steht innerhalb des Abschnitts Dateioperationen (nach u, vor Verwaltung)
        idx_u = next(i for i, l in enumerate(items) if "[u]" in l)
        idx_v = next(i for i, l in enumerate(items) if "[v]" in l)
        idx_verwaltung = next(i for i, l in enumerate(items) if l.strip() == "Verwaltung")
        self.assertLess(idx_u, idx_v)
        self.assertLess(idx_v, idx_verwaltung)
        # keymap funktioniert weiterhin
        km = common.build_keymap({"keybindings": custom})
        self.assertEqual(km.get("v"), "symlink")


class TestHilfsfunktionen(unittest.TestCase):
    """Zentrale Hilfsfunktionen der common-Bibliothek."""

    def test_str_width_und_pad_to_width(self):
        self.assertEqual(common.str_width("abc"), 3)
        self.assertGreaterEqual(common.str_width("äöü"), 3)
        self.assertEqual(common.char_width("📢"), 2)
        self.assertEqual(common.char_width("🗨"), 1)
        self.assertEqual(common.char_width("\ufe0f"), 0)
        self.assertEqual(common.str_width("🗨️ Critique Journal 5.html"), 25)

    def test_format_keys(self):
        self.assertEqual(common.format_keys(("UP",)), "↑")
        self.assertIn(" / ", common.format_keys(("ESC", "CTRL_C")))

    def test_natural_key(self):
        self.assertLess(ed.natural_key("datei2"), ed.natural_key("datei10"))
        self.assertEqual(ed.natural_key("ABC"), ed.natural_key("abc"))

    def test_format_size_wie_finder(self):
        # Dezimale Einheiten (1 KB = 1000 B) und deutsches Dezimalkomma,
        # damit die Werte mit dem Finder übereinstimmen.
        self.assertEqual(ed.format_size(999), "999 B")
        self.assertEqual(ed.format_size(1000), "1 KB")
        self.assertEqual(ed.format_size(1500), "2 KB")
        self.assertEqual(ed.format_size(1234567), "1,2 MB")
        self.assertEqual(ed.format_size(123456789), "123,5 MB")
        self.assertEqual(ed.format_size(12187883808), "12,19 GB")
        self.assertEqual(ed.format_size(1234567890123), "1,23 TB")

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
        self.orig_cwd = os.getcwd()
        self.app = ed.EasyDateienApp(self.dir_a)

    def tearDown(self):
        os.chdir(self.orig_cwd)
        self._tmp.cleanup()

    def test_sync_cwd_wechselt_arbeitsverzeichnis(self):
        self.app.enter_directory(self.dir_b)
        self.assertEqual(os.path.realpath(os.getcwd()), os.path.realpath(self.dir_b))
        self.app.enter_directory(self.dir_a)
        self.assertEqual(os.path.realpath(os.getcwd()), os.path.realpath(self.dir_a))

    def test_cwd_file_wird_geschrieben(self):
        cwd_file = os.path.join(self.base, "test_cwd.txt")
        test_app = ed.EasyDateienApp(self.dir_a, cwd_file=cwd_file)
        with open(cwd_file, "r", encoding="utf-8") as f:
            self.assertEqual(f.read().strip(), self.dir_a)
        test_app.enter_directory(self.dir_b)
        with open(cwd_file, "r", encoding="utf-8") as f:
            self.assertEqual(f.read().strip(), self.dir_b)

    def test_shell_init_ausgabe(self):
        import io
        from contextlib import redirect_stdout
        buf = io.StringIO()
        with redirect_stdout(buf):
            ed.print_shell_init("zsh")
        out = buf.getvalue()
        self.assertIn("easydateien()", out)
        self.assertIn("builtin cd", out)
        self.assertIn("alias ed=", out)

        buf = io.StringIO()
        with redirect_stdout(buf):
            ed.print_shell_init("fish")
        self.assertIn("function easydateien", buf.getvalue())

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
        self.app.active_dialog = "goto_menu"
        self.app.handle_dialog_key("t", None)
        trash_dir = os.path.expanduser("~/.Trash")
        if os.path.isdir(trash_dir):
            self.assertEqual(os.path.realpath(self.app.current_dir), os.path.realpath(trash_dir))

    def test_trash_erkennung_und_scan(self):
        import easydateien_ui as ui
        trash_dir = os.path.expanduser("~/.Trash")
        if sys.platform == "darwin":
            self.assertTrue(ui.is_trash_dir(trash_dir))
            self.assertFalse(ui.is_trash_dir(self.base))

        with patch("os.scandir", side_effect=PermissionError(1, "Operation not permitted")):
            with patch("easydateien_ui.is_trash_dir", return_value=True):
                with patch("easydateien_ui.scan_trash_macos", return_value=[ui.FileEntry(os.path.join(self.base, "fake.txt"), "fake.txt")]) as mock_fallback:
                    entries = ui.scan_raw(trash_dir)
                    mock_fallback.assert_called_once_with(trash_dir)
                    self.assertEqual(len(entries), 1)
                    self.assertEqual(entries[0].name, "fake.txt")

    def test_loeschen_im_papierkorb_loescht_endgueltig(self):
        with tempfile.TemporaryDirectory() as fake_trash:
            test_file = os.path.join(fake_trash, "papierkorb_datei.txt")
            with open(test_file, "w") as f:
                f.write("inhalt")
            self.assertTrue(os.path.exists(test_file))

            self.app.enter_directory(fake_trash)
            self.app.active_dialog = "trash_confirm"
            self.app.selected_paths = {test_file}

            with patch("os.path.expanduser", return_value=fake_trash):
                self.app.handle_dialog_key("y", None)

            self.assertFalse(os.path.exists(test_file))
            self.assertIn("endgültig gelöscht", self.app.status_message)

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

    def test_dynamisches_farbschema_ohne_feste_rgb_werte(self):
        # Keine 256-Farb- oder TrueColor-Sequenzen und kein festes Bright-Black (\033[90m);
        # nur SGR-Attribute und semantische ANSI-Grundfarben (31-36).
        screen = self.app.build_screen(80, 24)
        self.assertEqual(len(screen), 24)
        for line in screen:
            self.assertEqual(common.str_width(line), 80)
            self.assertNotIn("\033[38;", line)
            self.assertNotIn("\033[48;", line)
            self.assertNotIn("\033[90m", line)
        self.assertEqual(common.C_GRAY, common.C_DIM)

    def test_vorschau_scrollen_mit_umbruch_bis_ganz_nach_unten(self):
        # Datei mit langen Zeilen (jede Rohzeile bricht mehrfach um):
        # Das Scrollen muss bis zur allerletzten umgebrochenen Zeile reichen.
        long_file = os.path.join(self.dir_a, "lang.txt")
        lines_raw = [
            f"Zeile-{i:02d} " + "Wort " * 25 + f"ENDE-{i:02d}"
            for i in range(1, 26)
        ]
        with open(long_file, "w", encoding="utf-8") as f:
            f.write("\n".join(lines_raw))
        self.app.preview_wrap = True
        self.app.select_filename("lang.txt")
        self.app.build_screen(80, 24)

        steps = 0
        while self.app._scroll_preview(1):
            steps += 1
            self.assertLess(steps, 1000)

        self.assertGreater(steps, 25, "Umbruchzeilen wurden beim Scrollen nicht berücksichtigt")
        screen = self.app.build_screen(80, 24)
        joined = "\n".join(common.ANSI_ESCAPE_RE.sub("", l) for l in screen)
        self.assertIn("ENDE-25", joined, "Letzte Zeile der Datei wird am unteren Anschlag nicht angezeigt")
        self.assertFalse(self.app._scroll_preview(1), "Am unteren Anschlag darf nicht weiter gescrollt werden")

    def test_vorschau_scrollen_ohne_umbruch_exakter_anschlag(self):
        plain_file = os.path.join(self.dir_a, "zeilen.txt")
        with open(plain_file, "w", encoding="utf-8") as f:
            f.write("\n".join(f"Eintrag-{i:02d}" for i in range(1, 31)))
        self.app.preview_wrap = False
        self.app.select_filename("zeilen.txt")
        self.app.build_screen(80, 24)

        sichtbar, _ = self.app._preview_geometrie(self.app.items[self.app.selected_idx])
        while self.app._scroll_preview(1):
            pass
        self.assertEqual(self.app.preview_scroll_offset, 30 - sichtbar)
        screen = self.app.build_screen(80, 24)
        joined = "\n".join(common.ANSI_ESCAPE_RE.sub("", l) for l in screen)
        self.assertIn("Eintrag-30", joined)

    def test_vorschau_scrollen_reset_bei_datei_und_ordnerwechsel(self):
        f1 = os.path.join(self.dir_a, "eins.txt")
        with open(f1, "w", encoding="utf-8") as f:
            f.write("\n".join(f"Z-{i}" for i in range(50)))
        sub = os.path.join(self.dir_a, "unterordner")
        os.makedirs(sub, exist_ok=True)
        self.app.select_filename("eins.txt")
        self.app.build_screen(80, 24)
        self.assertTrue(self.app._scroll_preview(5))
        self.assertEqual(self.app.preview_scroll_offset, 5)

        # Wechsel auf Ordner und zurück auf dieselbe Datei setzt Offset auf 0 zurück
        self.app.select_filename("unterordner")
        self.app.build_screen(80, 24)
        self.assertEqual(self.app.preview_scroll_offset, 0)
        self.app.select_filename("eins.txt")
        self.app.build_screen(80, 24)
        self.assertEqual(self.app.preview_scroll_offset, 0)

    def test_vorschau_scrollen_clamping_bei_resize(self):
        f1 = os.path.join(self.dir_a, "resize.txt")
        with open(f1, "w", encoding="utf-8") as f:
            f.write("\n".join(f"Zeile {i} mit etwas Text für den Umbruch" for i in range(30)))
        self.app.preview_wrap = True
        self.app.select_filename("resize.txt")
        self.app.build_screen(60, 24)
        while self.app._scroll_preview(1):
            pass
        narrow_off = self.app.preview_scroll_offset
        self.assertGreater(narrow_off, 0)

        # Breiteres Terminal -> weniger Umbruchzeilen -> Offset wird automatisch begrenzt
        screen = self.app.build_screen(140, 30)
        self.assertLess(self.app.preview_scroll_offset, narrow_off)
        joined = "\n".join(common.ANSI_ESCAPE_RE.sub("", l) for l in screen)
        self.assertIn("Zeile 29", joined)

    def test_vorschau_scrollen_per_mausrad_ueber_rechter_spalte(self):
        f1 = os.path.join(self.dir_a, "maus.txt")
        with open(f1, "w", encoding="utf-8") as f:
            f.write("\n".join(f"Mauszeile-{i}" for i in range(40)))
        self.app.select_filename("maus.txt")
        self.app.build_screen(90, 24)
        idx_vorher = self.app.selected_idx

        # Mausrad rechts (in der Vorschauspalte x=80, y=10) scrollt Vorschau, nicht Dateiliste
        self.app.handle_mouse_wheel("down", x=80, y=10)
        self.assertEqual(self.app.selected_idx, idx_vorher)
        self.assertEqual(self.app.preview_scroll_offset, 1)
        self.app.handle_mouse_wheel("up", x=80, y=10)
        self.assertEqual(self.app.preview_scroll_offset, 0)

    def test_read_key_page_up_down_varianten(self):
        r, w = os.pipe()
        try:
            def send_and_read(seq: bytes) -> str:
                os.write(w, seq)
                return ed.read_key(r, timeout=0.1)

            self.assertEqual(send_and_read(b"\x1b[5~"), "PAGE_UP")
            self.assertEqual(send_and_read(b"\x1b[6~"), "PAGE_DOWN")
            self.assertEqual(send_and_read(b"\x1b[5;2~"), "PAGE_UP")
            self.assertEqual(send_and_read(b"\x1b[6;2~"), "PAGE_DOWN")
            self.assertEqual(send_and_read(b"\x1b[5;3~"), "PAGE_UP")
            self.assertEqual(send_and_read(b"\x1b[6;3~"), "PAGE_DOWN")
            self.assertEqual(send_and_read(b"\x1b[5;10~"), "PAGE_UP")
            self.assertEqual(send_and_read(b"\x1b[6;10~"), "PAGE_DOWN")
            self.assertEqual(send_and_read(b"\x1b\x1b[5~"), "PAGE_UP")
            self.assertEqual(send_and_read(b"\x1b\x1b[6~"), "PAGE_DOWN")
            self.assertEqual(send_and_read(b"\x1b\x1b[A"), "ALT_UP")
            self.assertEqual(send_and_read(b"\x1b\x1b[B"), "ALT_DOWN")
        finally:
            os.close(r)
            os.close(w)


if __name__ == "__main__":
    unittest.main()
