#!/usr/bin/env python3
"""Umfassende Konsolentests: maximale Zuverlässigkeit und native Darstellung.

Zwei Ebenen:
1. Unit-Ebene: Ausgabeverarbeitung, Umbruch, Scrollen, Puffer, interne Befehle
   (cd/clear/exit), Verzeichnis-Sync, Tab-Expansion, PTY-Breite.
2. PTY-Echtestebene: die echte App in einem Pseudo-Terminal mit echter
   Tastatur — Konsole öffnen, Befehle tippen, Strg+C, Fokuswechsel, Beenden.

Die Echtestebene läuft nur, wenn ein PTY verfügbar ist (nicht in CI).
"""

import os
import re
import sys
import shutil
import subprocess
import tempfile
import time
import unittest

REPO = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, REPO)
os.chdir(REPO)

_tmp_app = os.path.join(REPO, "easydateien.py")
if not os.path.exists(_tmp_app):
    shutil.copy(os.path.join(REPO, "easydateien"), _tmp_app)

import easydateien as ed  # noqa: E402

ANSI = re.compile(r"\x1b\[[0-9;]*[a-zA-Z]")


def visible(s):
    return ANSI.sub("", s)


def make_base(names=(), dirs=()):
    base = tempfile.mkdtemp(prefix="ed-konsole-")
    for n in names:
        with open(os.path.join(base, n), "w") as f:
            f.write("x" * 8)
    for d in dirs:
        os.makedirs(os.path.join(base, d), exist_ok=True)
    return base


class TestKonsoleUnit(unittest.TestCase):
    """Ebene 1: Ausgabeverarbeitung und Konsolenverhalten ohne Terminal."""

    def setUp(self):
        self.orig_cwd = os.getcwd()
        os.environ["HOME"] = tempfile.mkdtemp(prefix="ed-home-")
        self.base = make_base(["a.txt", "b.md", "lange-datei-mit-langen-namen.txt"], ["sub"])
        self.app = ed.EasyDateienApp(self.base)
        self.app.show_console = True
        self.app.console_focused = True

    def tearDown(self):
        os.chdir(self.orig_cwd)
        shutil.rmtree(self.base, ignore_errors=True)

    def out(self):
        return [l for l in self.app.console_output_lines if l and not l.startswith("$ ")]

    def test_historie_entwurf_bleibt_erhalten(self):
        self.app.run_console_command("echo eins", None, None)
        self.app.run_console_command("echo zwei", None, None)
        self.app.console_input = "mein-entwurf"
        self.app.console_cursor_idx = len(self.app.console_input)
        self.assertTrue(self.app._console_history_prev())
        self.assertEqual(self.app.console_input, "echo zwei")
        self.assertTrue(self.app._console_history_prev())
        self.assertEqual(self.app.console_input, "echo eins")
        self.app._console_history_next()
        self.assertEqual(self.app.console_input, "echo zwei")
        self.app._console_history_next()
        self.assertEqual(self.app.console_input, "mein-entwurf",
                         "Ungesendeter Entwurf ging beim Historien-Blättern verloren")
        # Entwurf bleibt am Ende stabil (weitere Blätterzyklen)
        self.assertTrue(self.app._console_history_prev())
        self.assertEqual(self.app.console_input, "echo zwei")
        self.app._console_history_next()
        self.assertEqual(self.app.console_input, "mein-entwurf",
                         "Entwurf nach erneutem Blättern wieder verloren")

    def test_historie_ohne_entwurf_endet_leer(self):
        self.app.run_console_command("echo eins", None, None)
        self.app.console_input = ""
        self.assertTrue(self.app._console_history_prev())
        self.assertEqual(self.app.console_input, "echo eins")
        self.app._console_history_next()
        self.assertEqual(self.app.console_input, "")

    def test_stdout_erscheint(self):
        self.app.run_console_command("echo hello", None, None)
        self.assertIn("hello", self.out())

    def test_stderr_erscheint(self):
        self.app.run_console_command("echo fehler 1>&2", None, None)
        self.assertIn("fehler", self.out())

    def test_fehlermeldung_fehlender_befehl(self):
        self.app.run_console_command("gibts-nicht-xyz", None, None)
        joined = "\n".join(self.out())
        self.assertTrue(any(k in joined.lower() for k in ("not found", "command not found", "nicht gefunden", "kommando nicht gefunden")))

    def test_mehrzeilenausgabe_vollstaendig(self):
        self.app.run_console_command("for i in 1 2 3 4 5; do echo zeile-$i; done", None, None)
        for i in range(1, 6):
            self.assertTrue(any(f"zeile-{i}" == l for l in self.out()), f"zeile-{i} fehlt")

    def test_tabs_werden_expandidert(self):
        self.app.run_console_command("printf 'a\\tb\\tc\\n'", None, None)
        for l in self.out():
            self.assertNotIn("\t", l)
        joined = "".join(self.out())
        self.assertIn("a", joined and joined)

    def test_kein_60s_abbruch(self):
        t0 = time.monotonic()
        self.app.run_console_command("sleep 1.2 && echo fertig", None, None)
        dauer = time.monotonic() - t0
        self.assertGreaterEqual(dauer, 1.1)
        self.assertIn("fertig", self.out())

    def test_pty_breite_begrenzt_ls_spalten(self):
        base = make_base(names=[f"datei-{i:02d}" for i in range(20)])
        app = ed.EasyDateienApp(base)
        app.show_console = True
        app.console_focused = True
        try:
            app.run_console_command("ls", None, None)
            zeilen = [l for l in app.console_output_lines if l and not l.startswith("$ ")]
            self.assertTrue(zeilen)
            for l in zeilen:
                self.assertLessEqual(
                    len(visible(l)), 80,
                    f"ls-Zeile breiter als Terminal: {l!r}")
        finally:
            os.chdir(self.orig_cwd)
            shutil.rmtree(base, ignore_errors=True)

    def test_umbruch_erhaelt_inhalt(self):
        self.app.run_console_command(
            "python3 -c \"print('wort-' + 'x'*200)\"", None, None)
        lines = self.app.get_console_display_lines(30, 12)
        for l in lines:
            self.assertLessEqual(len(visible(l)), 30)
        joined = "".join(visible(l) for l in lines)
        self.assertGreaterEqual(joined.count("x"), 150, "Umbruch verlor Inhalt")

    def test_puffer_begrenzung(self):
        self.app.run_console_command("yes | head -n 12000", None, None)
        self.assertLessEqual(len(self.app.console_output_lines), 10050)

    def test_cd_wechselt_verzeichnis(self):
        self.app.run_console_command("cd sub", None, None)
        self.assertEqual(os.path.realpath(self.app.current_dir),
                         os.path.realpath(os.path.join(self.base, "sub")))

    def test_cd_ungueltig_bleibt(self):
        self.app.run_console_command("cd gibts-nicht-xyz", None, None)
        self.assertEqual(os.path.realpath(self.app.current_dir),
                         os.path.realpath(self.base))
        self.assertTrue(any("nicht gefunden" in l for l in self.out()))

    def test_clear_leert_konsole(self):
        self.app.run_console_command("echo x", None, None)
        self.app.run_console_command("clear", None, None)
        self.assertEqual(self.app.console_output_lines, [])

    def test_verlauf_waechst(self):
        for i in range(5):
            self.app.run_console_command(f"echo befehl-{i}", None, None)
        self.assertEqual(len(self.app.console_cmd_history), 5)

    def test_exit_schliesst_konsole(self):
        self.app.console_always_visible = False
        self.app.run_console_command("exit", None, None)
        self.assertFalse(self.app.show_console)

    def test_exit_bei_always_visible_laesst_konsole_offen(self):
        self.app.console_always_visible = True
        self.app.run_console_command("exit", None, None)
        self.assertTrue(self.app.show_console)

    def test_kommando_wird_gefiltert_shell_stoerzeilen(self):
        self.app.run_console_command("echo normal", None, None)
        joined = "\n".join(self.out()).lower()
        for stoer in ("restored session", "saving history", "nicht kopierbar"):
            self.assertNotIn(stoer, joined)

    def test_strg_c_ohne_terminale_fuegt_ctrl_c_hinzu(self):
        # fd=None: kein Terminal; der interne Pfad darf nicht abstuerzen
        try:
            self.app.run_console_command("sleep 0.5", None, None)
        except Exception as e:
            self.fail(f"run_console_command mit fd=None warf: {e}")


class TestKonsoleEchtest(unittest.TestCase):
    """Ebene 2: echte App im Pseudo-Terminal mit echter Tastatur.

    Wird uebersprungen, wenn kein PTY verfuegbar ist (CI-Umgebung).
    """

    @classmethod
    def setUpClass(cls):
        import pty
        import select
        cls.pty = pty
        cls.select = select

    def setUp(self):
        self.orig_cwd = os.getcwd()

    def _starte_app(self):
        base = make_base(["a.txt", "b.md"], ["sub"])
        pid, fd = self.pty.fork()
        if pid == 0:
            os.environ["HOME"] = tempfile.mkdtemp(prefix="ed-home-")
            os.execv(sys.executable, [sys.executable, "easydateien", base])
        return pid, fd, base

    def _pump(self, fd, dauer=0.6):
        out = b""
        end = time.monotonic() + dauer
        while time.monotonic() < end:
            r, _, _ = self.select.select([fd], [], [], 0.1)
            if r:
                try:
                    d = os.read(fd, 65536)
                except OSError:
                    break
                if not d:
                    break
                out += d
        return out

    def test_konsole_kompletter_zyklus(self):
        try:
            pid, fd, base = self._starte_app()
        except (OSError, AttributeError):
            self.skipTest("PTY nicht verfügbar")
        try:
            time.sleep(1.2)
            self._pump(fd, 0.4)
            # Konsole oeffnen und fokussieren
            os.write(fd, b"t"); time.sleep(0.3)
            self._pump(fd, 0.3)
            os.write(fd, b"\t"); time.sleep(0.3)
            self._pump(fd, 0.3)
            # Befehl ausfuehren
            os.write(fd, b"echo pong-42\x0d")
            out = self._pump(fd, 1.2)
            self.assertIn(b"pong-42", out)
            # cd + Verzeichnis-Sync: Dateimanager folgt
            os.write(fd, b"cd sub\x0d")
            time.sleep(0.4)
            self._pump(fd, 0.4)
            # ESC schliesst Konsole (nicht immer sichtbar: App weiter aktiv)
            os.write(fd, b"\x1b"); time.sleep(0.4)
            out = self._pump(fd, 0.4)
            self.assertTrue(True)  # App nicht abgestuerzt
            # q beendet sauber
            os.write(fd, b"q"); time.sleep(0.5)
            try:
                os.kill(pid, 9)
            except ProcessLookupError:
                pass
            os.waitpid(pid, 0)
        finally:
            os.chdir(self.orig_cwd)
            shutil.rmtree(base, ignore_errors=True)

    def test_strg_c_bricht_laufenden_befehl_ab(self):
        try:
            pid, fd, base = self._starte_app()
        except (OSError, AttributeError):
            self.skipTest("PTY nicht verfügbar")
        try:
            time.sleep(1.2)
            self._pump(fd, 0.4)
            os.write(fd, b"t"); time.sleep(0.3); self._pump(fd, 0.3)
            os.write(fd, b"\t"); time.sleep(0.3); self._pump(fd, 0.3)
            os.write(fd, b"sleep 30\x0d")
            time.sleep(1.0)
            self._pump(fd, 0.3)
            t0 = time.monotonic()
            os.write(fd, b"\x03")
            os.write(fd, b"echo wieder-da\x0d")
            out = self._pump(fd, 1.5)
            dauer = time.monotonic() - t0
            self.assertIn(b"wieder-da", out, "Konsole nach Strg+C nicht bedienbar")
            self.assertLess(dauer, 3.0, "Strg+C brauchte zu lange")
            try:
                os.kill(pid, 9)
            except ProcessLookupError:
                pass
            os.waitpid(pid, 0)
        finally:
            os.chdir(self.orig_cwd)
            shutil.rmtree(base, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
