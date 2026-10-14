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

# HOME VOR dem Import der Programmmodule setzen: HOME_DIR wird beim Import
# aus der Umgebung gebacken und ist danach konstant. Nur so sind die
# Hashes auf jedem Rechner identisch.
os.environ["HOME"] = "/tmp/easydateien-golden-home"
os.makedirs("/tmp/easydateien-golden-home", exist_ok=True)

REPO = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, REPO)
os.chdir(REPO)

import shutil as _shutil

_tmp_app = os.path.join(REPO, "easydateien.py")
if not os.path.exists(_tmp_app):
    _shutil.copy(os.path.join(REPO, "easydateien"), _tmp_app)

import easydateien as ed  # noqa: E402


HOME_FIXED = "/tmp/easydateien-golden-home"

_GOLDEN_RUNNER = r"""
import hashlib, json, os, re, shutil, sys

HOME = "/tmp/easydateien-golden-home"
os.environ["HOME"] = HOME
os.makedirs(HOME, exist_ok=True)
REPO = sys.argv[1]
sys.path.insert(0, REPO)
shutil.copy(os.path.join(REPO, "easydateien"), os.path.join(REPO, "easydateien.py"))
import easydateien as ed

base = os.path.join(HOME, "fixture")
shutil.rmtree(base, ignore_errors=True)
os.makedirs(base)
for name, size, mt in [("alpha.md",1200,1790000000),("bericht.pdf",250000,1790000600),
                       ("install.sh",5000,1790001200),("notizen.txt",40,1790001800)]:
    p = os.path.join(base, name); open(p,"wb").write(b"x"*size); os.utime(p,(mt,mt))
os.makedirs(os.path.join(base,"Unterlagen"))
os.utime(os.path.join(base,"Unterlagen"),(1790002400,1790002400))

def normalize(lines):
    out = []
    for l in lines:
        v = re.sub(r"\x1b\[[0-9;]*[a-zA-Z]", "", l)
        v = v.replace(base, "/BASE").replace("fixture", "BASE").replace(HOME, "HOME")
        v = re.sub(r"tmp[A-Za-z0-9_]{4,}", "TMP", v)
        out.append(v)
    return out

def h(lines):
    return hashlib.sha256("\n".join(lines).encode()).hexdigest()[:16]

def golden(cols, rows, dialog, marked=(), cut=False):
    app = ed.EasyDateienApp(base)
    for m in marked: app.selected_paths.add(os.path.join(base, m))
    if cut:
        app.clipboard_mode="cut"; app.clipboard_paths=[os.path.join(base,m) for m in marked]
    app.active_dialog = dialog
    return h(normalize(app.build_screen(cols, rows)))

print(json.dumps({
    "3N": golden(80,24,None),
    "3M": golden(80,24,None,marked=("alpha.md","install.sh")),
    "3C": golden(80,24,None,marked=("alpha.md",),cut=True),
    "GOTO": golden(80,24,"goto_menu"),
    "HELP": golden(80,24,"help_menu"),
    "2N": golden(50,24,None,marked=("notizen.txt",)),
    "1N": golden(35,24,None),
}))
"""

# Hashes des heutigen, als korrekt eingefrorenen Verhaltens (bitgleich vom
# Monolithen vor dem Modul-Split; Subprozess liefert sie reproduzierbar):
EXPECTED = {
    "3N": "1b1d44741bf49d70",
    "3M": "68ad4866fd3de6a5",
    "3C": "0c274160906dabce",
    "GOTO": "a8f9cc5d6367bbd5",
    "HELP": "3b5706680a471393",
    "2N": "0146bf19d7af120f",
    "1N": "d49b4e5b75993738",
}


class TestGoldenRendering(unittest.TestCase):
    """Exakte Bildschirm-Hashes in isoliertem Subprozess.

    Bei Abweichung NICHT blind anpassen, sondern die Ursache der
    Darstellungsanderung klaeren."""

    def _run(self):
        import subprocess, json
        r = subprocess.run([sys.executable, "-c", _GOLDEN_RUNNER, REPO],
                          capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        return json.loads(r.stdout)

    def test_golden_rendering(self):
        results = self._run()
        for key, expected in EXPECTED.items():
            self.assertEqual(results.get(key), expected,
                             f"Rendering abweichend in Szenario {key}")


if __name__ == "__main__":
    unittest.main()
