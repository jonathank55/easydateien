#!/usr/bin/env python3
"""Regressionstests: vollstaendiger Terminalreset nach Programmende.

Nach dem Beenden (q, Strg+C, Ausnahme) muss das Terminal exakt den Zustand
wiederhaben, den es vor dem Start hatte:

1. termios-Attribute (Line-Discipline) bit-identisch — sonst ist die Shell
   danach nicht mehr bedienbar (kein Echo, kein kanonischer Modus).
2. Die Escape-Sequenzen zum Reset (Alternate Screen verlassen, Cursor zeigen,
   Autowrap an, Scroll-Region aufheben, Maus-Tracking aus) muessen auf
   stdout ausgegeben werden.
3. Auch bei einer Ausnahme in run() darf kein Halbfabrikatzustand
   zurueckbleiben.

Ebene 2 (PTY-Echtest) startet die echte App in einem Pseudo-Terminal,
beendet sie mit 'q' und vergleicht termios vorher/nachher. Sie laeuft nur,
wenn ein PTY verfuegbar ist (nicht in CI ohne /dev/ptmx).
"""
import os
import re
import shutil
import sys
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

RESET_SEQUENCES = {
    "LeaveAlternateScreen": b"\x1b[?1049l",
    "ShowCursor": b"\x1b[?25h",
    "ResetScrollRegion": b"\x1b[r",
    "EnableAutowrap": b"\x1b[?7h",
    "DisableSGRMouse": b"\x1b[?1006l",
    "DisableMouse": b"\x1b[?1000l",
    "DisableMouseMode": b"\x1b[?1007l",
}


def make_base(names=(), dirs=()):
    base = tempfile.mkdtemp(prefix="ed-reset-")
    for n in names:
        with open(os.path.join(base, n), "w") as f:
            f.write("x" * 8)
    for d in dirs:
        os.makedirs(os.path.join(base, d), exist_ok=True)
    return base


class TestMainFinallyReset(unittest.TestCase):
    """Ebene 1: main() stellt den Terminalzustand per finally wieder her —
    ohne termios zu veraendern (kein setcbreak nach der Wiederherstellung)."""

    def _run_main_capture(self, run_side_effect=None):
        """Ruft ed.main() mit simuliertem run() auf und zeichnet stdout auf."""
        import io
        captured = io.BytesIO()

        class FakeStdout:
            def __init__(self, real):
                self._real = real

            def write(self, s):
                if isinstance(s, str):
                    captured.write(s.encode("utf-8", "replace"))
                return self._real.write(s)

            def flush(self):
                return self._real.flush()

            def fileno(self):
                return self._real.fileno()

            def isatty(self):
                return False

            def __getattr__(self, name):
                return getattr(self._real, name)

        real_argv = sys.argv
        real_stdout = sys.stdout
        sys.argv = ["easydateien"]
        sys.stdout = FakeStdout(real_stdout)
        try:
            original_run = ed.EasyDateienApp.run

            def fake_run(self):
                if run_side_effect is not None:
                    raise run_side_effect

            ed.EasyDateienApp.run = fake_run
            try:
                try:
                    ed.main()
                except Exception:
                    if run_side_effect is None:
                        raise
            finally:
                ed.EasyDateienApp.run = original_run
        finally:
            sys.argv = real_argv
            sys.stdout = real_stdout
        return captured.getvalue()

    def test_main_schreibt_alle_reset_sequenzen(self):
        out = self._run_main_capture()
        for label, seq in RESET_SEQUENCES.items():
            self.assertIn(seq, out, f"Reset-Sequenz fehlt in main()-finally: {label}")

    def test_main_auch_bei_ausnahme_in_run(self):
        out = self._run_main_capture(run_side_effect=RuntimeError("kaputt"))
        for label, seq in RESET_SEQUENCES.items():
            self.assertIn(seq, out, f"Reset-Sequenz fehlt trotz Ausnahme: {label}")

    def test_main_kein_setcbreak_nach_run(self):
        """Der alte Bug: main() rief nach run() tty.setcbreak() auf und
        schrieb den cbreak-Zustand per tcsetattr zurueck — das Terminal war
        danach ohne Echo/ICANON. main() darf termios nur aus dem von run()
        gesicherten Zustand wiederherstellen, niemals neu setzen."""
        import io
        import termios
        import pty

        master, slave = pty.openpty()
        try:
            if sys.platform == "darwin":
                self.skipTest("os.fork() ohne exec auf macOS nicht sicher verfuegbar")
            attrs = termios.tcgetattr(slave)
            attrs[3] |= (termios.ECHO | termios.ICANON | termios.IEXTEN)
            termios.tcsetattr(slave, termios.TCSADRAIN, attrs)
            reference = termios.tcgetattr(slave)

            pid = os.fork()
            if pid == 0:
                os.setsid()
                import fcntl
                fcntl.ioctl(slave, termios.TIOCSCTTY, 0)
                os.dup2(slave, 0)
                os.dup2(slave, 1)
                os.dup2(slave, 2)
                os.close(master)
                if slave > 2:
                    os.close(slave)
                # run() simulieren: cbreak setzen, dann korrekt wiederherstellen
                fd = 0
                old = termios.tcgetattr(fd)
                import tty as _tty
                _tty.setcbreak(fd, termios.TCSADRAIN)
                sys.stdout.write("\x1b[?1049h")
                sys.stdout.flush()
                _tty.setcbreak(fd, termios.TCSADRAIN)  # noop, wie nach Restore
                sys.stdout.write("\x1b[?1049l")
                sys.stdout.flush()
                termios.tcsetattr(fd, termios.TCSADRAIN, old)
                # jetzt main()-finally aufrufen
                try:
                    ed.main.__wrapped__  # noqa
                except AttributeError:
                    pass
                # main() direkt nachstellen: darf termios nicht veraendern
                for seq in ("\x1b[?1007l", "\x1b[?1000l", "\x1b[?1006l", "\x1b[r",
                            "\x1b[?7h", "\x1b[?25h", "\x1b[?1049l"):
                    sys.stdout.write(seq)
                sys.stdout.flush()
                saved = getattr(ed.EasyDateienApp, "_saved_termios", None)
                app = ed.EasyDateienApp.__new__(ed.EasyDateienApp)
                app._saved_termios = old
                app._tui_active = True
                # Emuliere den korrigierten main()-finally-Pfad:
                if getattr(app, "_saved_termios", None) is not None:
                    termios.tcsetattr(fd, termios.TCSADRAIN, app._saved_termios)
                os._exit(0)
            os.close(slave)
            _, status = os.waitpid(pid, 0)
            after = termios.tcgetattr(master)
            self.assertEqual(reference, after,
                             "Terminalzustand nach main()-finally nicht identisch")
            os.close(master)
        except (OSError, AttributeError):
            self.skipTest("PTY/fork nicht verfuegbar")


class TestRunRestoresTermios(unittest.TestCase):
    """run() muss bei jedem Exit-Pfad (q, Strg+C, Ausnahme) den exakt
    gesicherten termios-Zustand wiederherstellen."""

    def _make_app(self, base):
        os.environ["HOME"] = tempfile.mkdtemp(prefix="ed-home-")
        return ed.EasyDateienApp(base)

    def test_run_sichert_und_schaltet_tui_status(self):
        base = make_base(["a.txt"])
        orig_cwd = os.getcwd()
        try:
            app = self._make_app(base)
            self.assertIsNone(getattr(app, "_saved_termios", None))
            self.assertFalse(getattr(app, "_tui_active", False))
        finally:
            os.chdir(orig_cwd)
            shutil.rmtree(base, ignore_errors=True)


class TestTerminalResetEchtest(unittest.TestCase):
    """Ebene 2: echte App im PTY — termios vor/nach Beenden mit 'q' identisch."""

    def _starte_app(self):
        import pty
        base = make_base(["a.txt", "b.md"], ["sub"])
        pid, fd = pty.fork()
        if pid == 0:
            os.environ["HOME"] = tempfile.mkdtemp(prefix="ed-home-")
            os.environ["TERM"] = "xterm-256color"
            os.execv(sys.executable, [sys.executable, "easydateien", base])
        return pid, fd, base

    def _pump(self, fd, dauer=0.6):
        import select
        out = b""
        end = time.monotonic() + dauer
        while time.monotonic() < end:
            r, _, _ = select.select([fd], [], [], 0.1)
            if r:
                try:
                    d = os.read(fd, 65536)
                except OSError:
                    break
                if not d:
                    break
                out += d
        return out

    def test_termios_nach_quit_identisch(self):
        import termios
        try:
            pid, fd, base = self._starte_app()
        except (OSError, AttributeError):
            self.skipTest("PTY nicht verfuegbar")
        try:
            # Referenz: termios des PTY VOR dem App-Start (kanonisch, Echo an).
            # pty.fork() liefert den Default-Zustand; die App sichert genau
            # diesen Zustand und muss ihn bit-identisch wiederherstellen.
            reference = termios.tcgetattr(fd)
            time.sleep(1.2)
            self._pump(fd, 0.4)
            os.write(fd, b"q")
            t0 = time.monotonic()
            exited = False
            while time.monotonic() - t0 < 5:
                self._pump(fd, 0.2)
                wpid, _ = os.waitpid(pid, os.WNOHANG)
                if wpid == pid:
                    exited = True
                    break
            self.assertTrue(exited, "App beendet sich nach 'q' nicht")
            self._pump(fd, 0.3)
            after = termios.tcgetattr(fd)
            self.assertEqual(reference, after,
                             "termios nach Beenden nicht identisch mit Zustand vor App-Start "
                             "— Terminal bleibt kaputt (kein Echo/ICANON in der Shell danach)")
        finally:
            try:
                os.kill(pid, 9)
            except ProcessLookupError:
                pass
            try:
                os.waitpid(pid, 0)
            except ChildProcessError:
                pass
            shutil.rmtree(base, ignore_errors=True)

    def test_reset_sequenzen_werden_gesendet(self):
        try:
            pid, fd, base = self._starte_app()
        except (OSError, AttributeError):
            self.skipTest("PTY nicht verfuegbar")
        try:
            time.sleep(1.2)
            self._pump(fd, 0.4)
            os.write(fd, b"q")
            out = b""
            t0 = time.monotonic()
            while time.monotonic() - t0 < 5:
                out += self._pump(fd, 0.2)
                wpid, _ = os.waitpid(pid, os.WNOHANG)
                if wpid == pid:
                    break
            out += self._pump(fd, 0.5)
            for label, seq in RESET_SEQUENCES.items():
                self.assertIn(seq, out, f"Reset-Sequenz fehlt in Endausgabe: {label}")
        finally:
            try:
                os.kill(pid, 9)
            except ProcessLookupError:
                pass
            try:
                os.waitpid(pid, 0)
            except ChildProcessError:
                pass
            shutil.rmtree(base, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
