#!/usr/bin/env python3
"""Goldene Rendering-Tests: frieren das exakte heutige Bildschirmverhalten ein.

Jede Refaktorierung (Modul-Split, Dispatch-Umbau, ...) muss diese Hashes
unveraendert lassen. Aenderungen am Rendering sind damit sofort sichtbar.
Aufbau bewusst deterministisch: feste Dateinamen, feste Groessen, feste
Zeiten; zufaellige Temp-Verzeichnisnamen werden normalisiert.
"""

import hashlib
import os
import re
import sys
import unittest

REPO = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, REPO)
os.chdir(REPO)

import shutil as _shutil

_tmp_app = os.path.join(REPO, "easydateien.py")
if not os.path.exists(_tmp_app):
    _shutil.copy(os.path.join(REPO, "easydateien"), _tmp_app)

import easydateien as ed  # noqa: E402


def _normalize(lines, base):
    """Ersetzt variable Anteile (Temp-Pfad, Ordnername) durch feste Platzhalter."""
    out = []
    base_name = os.path.basename(base)
    for l in lines:
        v = re.sub(r"\x1b\[[0-9;]*[a-zA-Z]", "", l)
        v = v.replace(base, "/BASE").replace(base_name, "BASE")
        v = re.sub(r"tmp[A-Za-z0-9_]{4,}", "TMP", v)
        out.append(v)
    return out


def _hash(lines):
    return hashlib.sha256("\n".join(lines).encode("utf-8")).hexdigest()[:16]


def _build_fixture():
    base = os.path.join(os.environ.get("TMPDIR", "/tmp"),
                        "easydateien-golden")
    _shutil.rmtree(base, ignore_errors=True)
    os.makedirs(base)
    files = {
        "alpha.md": (1200, 1790000000),
        "bericht.pdf": (250000, 1790000600),
        "install.sh": (5000, 1790001200),
        "notizen.txt": (40, 1790001800),
    }
    for name, (size, mtime) in files.items():
        p = os.path.join(base, name)
        with open(p, "wb") as f:
            f.write(b"x" * size)
        os.utime(p, (mtime, mtime))
    os.makedirs(os.path.join(base, "Unterlagen"))
    os.utime(os.path.join(base, "Unterlagen"), (1790002400, 1790002400))
    return base


class TestGoldenRendering(unittest.TestCase):
    """Exakte Bildschirm-Hashes: bei Abweichung NICHT blind anpassen,
    sondern die Ursache der Darstellungsanderung klaeren."""

    @classmethod
    def setUpClass(cls):
        os.environ["HOME"] = "/tmp/easydateien-golden-home"
        os.makedirs("/tmp/easydateien-golden-home", exist_ok=True)
        cls.base = _build_fixture()

    def _app(self):
        app = ed.EasyDateienApp(self.base)
        return app

    def _golden(self, cols, rows, dialog, marked=(), cut=False, label=""):
        app = self._app()
        for m in marked:
            app.selected_paths.add(os.path.join(self.base, m))
        if cut:
            app.clipboard_mode = "cut"
            app.clipboard_paths = [os.path.join(self.base, m) for m in marked]
        app.active_dialog = dialog
        lines = _normalize(app.build_screen(cols, rows), self.base)
        return _hash(lines)

    def test_golden_3spalten_normal(self):
        h = self._golden(80, 24, None, label="normal")
        self.assertEqual(h, "69040ca0d7846ce4")

    def test_golden_3spalten_markiert(self):
        h = self._golden(80, 24, None, marked=("alpha.md", "install.sh"), label="markiert")
        self.assertEqual(h, "c4a916e0204fe402")

    def test_golden_3spalten_ausgeschnitten(self):
        h = self._golden(80, 24, None, marked=("alpha.md",), cut=True, label="cut")
        self.assertEqual(h, "6dc797396d659512")

    def test_golden_goto_menue(self):
        h = self._golden(80, 24, "goto_menu", label="goto")
        self.assertEqual(h, "113bd7cc810dcfe6")

    def test_golden_hilfe_menue(self):
        h = self._golden(80, 24, "help_menu", label="hilfe")
        self.assertEqual(h, "59bff095fb0b8227")

    def test_golden_2spalten(self):
        h = self._golden(50, 24, None, marked=("notizen.txt",), label="2col")
        self.assertEqual(h, "cd4dc5ec48a0e7c1")

    def test_golden_1spalte(self):
        h = self._golden(35, 24, None, label="1col")
        self.assertEqual(h, "917c9c08270c7b7d")


if __name__ == "__main__":
    unittest.main()
