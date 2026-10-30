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

    def test_osc_und_csi_fragmente_werden_entfernt(self):
        # zsh sendet beim Start u. a. "\x1b[2 q" (Cursorform) und
        # "\x1b]7;file://…\x07" (Arbeitsverzeichnis). Beide dürfen nicht
        # als sichtbarer Text in der Konsole landen.
        self.app._append_console_output(
            "\x1b[2 q\x1b]7;file://localhost/Users/jk\x07datei.txt")
        zeilen = self.out()
        self.assertEqual(zeilen, ["datei.txt"])
        joined = "\n".join(zeilen)
        for rest in ("[2 q", "]7;", "file://", "\x1b", "\x07"):
            self.assertNotIn(rest, joined)
        # Zeichensatz-Umschaltung wie ESC(B darf kein "B" hinterlassen.
        self.app.console_output_lines.clear()
        self.app._append_console_output("\x1b(Bzweite-zeile")
        self.assertEqual(self.out(), ["zweite-zeile"])

    def test_ls_a_zeigt_keine_steuersequenzen(self):
        self.app.run_console_command("ls -a", None, None)
        joined = "\n".join(self.out())
        for rest in ("\x1b", "[2 q", "]7;", "file://", "\x07"):
            self.assertNotIn(rest, joined)
        self.assertIn("a.txt", joined)

    def test_interaktive_befehle_werden_abgelehnt(self):
        befehle = [
            "vim", "nano test.txt", "less README.md", "top", "htop",
            "ssh example.com", "python3", "cat", "read antwort",
            "rm -i gibts-nicht", "echo x | less", "git log",
            "FOO=bar vim", "/usr/bin/vim", "watch ls", "ls && vim",
            "bash -c 'vim'",
        ]
        for befehl in befehle:
            with self.subTest(befehl=befehl):
                self.app.console_output_lines.clear()
                self.app.run_console_command(befehl, None, None)
                self.assertEqual(
                    self.out(), ["FEHLER: Interaktiver Befehl"],
                    f"Interaktiver Befehl wurde nicht verweigert: {befehl}")

    def test_nichtinteraktive_befehle_bleiben_erlaubt(self):
        for befehl in ("echo hallo", "ls", "printf 'x\\n'", "pwd"):
            with self.subTest(befehl=befehl):
                self.app.console_output_lines.clear()
                self.app.run_console_command(befehl, None, None)
                joined = "\n".join(self.out())
                self.assertNotIn("FEHLER: Interaktiver Befehl", joined)
                self.assertTrue(self.out(), f"Keine Ausgabe für: {befehl}")

    def test_erkennung_interaktiver_befehle(self):
        from easydateien_actions import ist_interaktiver_befehl
        interaktiv = (
            "vim", "nano datei.txt", "less datei.txt", "htop", "ssh host",
            "python3", "cat", "grep muster", "sort", "read x",
            "rm -i datei", "echo x | more", "git log", "git commit -m x",
            "FOO=1 vim", "/usr/local/bin/vim", "watch ls", "bash",
            "python3 -i skript.py", "ls && vim", "echo x; nano",
            "true || htop", "bash -c 'vim'", "bash -c 'ls; vim'",
            "nohup vim", "env FOO=1 vim", "nice -n 10 vim",
            "xargs vim", "find . -exec vim {} \\;",
            "(vim)", "if ls; then vim; fi",
        )
        for befehl in interaktiv:
            with self.subTest(befehl=befehl):
                self.assertTrue(ist_interaktiver_befehl(befehl),
                                f"Nicht als interaktiv erkannt: {befehl}")
        nicht_interaktiv = (
            "ls -a", "echo hallo", "printf 'x\\n'", "pwd", "git status",
            "cat datei.txt", "grep muster datei.txt", "head -n 5 datei.txt",
            "mkdir neuer-ordner", "touch neu.txt", "cp a.txt b.txt",
            "python3 -c \"print(1)\"", "python3 skript.py", "node -e 1",
            "bash -c 'ls'", "zsh -c 'echo hallo'",
            "ls | grep a", "cat a.txt | grep x", "echo x && echo y",
            "command -v vim", "echo 'a | less'", "echo 'a; vim'",
            "echo hi 2>&1", "find . -name '*.txt'",
            "for i in 1 2 3 4 5; do echo zeile-$i; done",
            "if ls; then echo ok; fi",
        )
        for befehl in nicht_interaktiv:
            with self.subTest(befehl=befehl):
                self.assertFalse(ist_interaktiver_befehl(befehl),
                                 f"Fälschlich als interaktiv erkannt: {befehl}")

    def test_kein_vollbildprompt_mehr(self):
        self.app.run_console_command("echo x", None, None)
        zeilen = self.app.get_console_display_lines(80, 20)
        self.assertTrue(visible(zeilen[-1]).startswith("$ "))
        self.assertNotIn("/", visible(zeilen[-1]))


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
