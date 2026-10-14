#!/usr/bin/env python3
"""EasyDateien — Aktionen: Dateioperationen, Navigation, Konsole, Dialoge, Maus.

Alle Methoden des EasyDateienApp-Action-Mixins. Entstanden durch mechanischen
Modul-Split; die Logik ist unveraendert. Erwartet die Attribute des Kerns (__init__)
und die Helfer aus easydateien_ui.
"""

from easydateien_common import (
    CONFIG_FILE, DEFAULT_CONFIG,
    KEY_BINDINGS, CHORD_ACTIONS, get_keybindings_from_config, build_keymap,
)
from easydateien_ui import *

import os
import sys
import re
import time
import datetime
import shutil
import select
import signal
import zipfile
import subprocess
import stat
import json


class EasyDateienActions:
    """Mixin: sämtliche Methoden mit Seiteneffekten (Dateien, Navigation, Dialoge)."""


    # ------------------------------------------------------------------ Terminal

    def set_mouse_tracking(self, enable: bool):
        """Aktiviert oder deaktiviert das SGR-Maus-Tracking im Terminal deterministisch."""
        if enable:
            if not self._mouse_tracking_active:
                sys.stdout.write("\033[?1000h\033[?1006h")
                sys.stdout.flush()
                self._mouse_tracking_active = True
        else:
            if self._mouse_tracking_active:
                sys.stdout.write("\033[?1006l\033[?1000l")
                sys.stdout.flush()
                self._mouse_tracking_active = False

    def sync_mouse_state(self):
        """Synchronisiert das Terminal-Maus-Tracking mit dem aktuellen Konfigurationsstatus."""
        should_enable = bool(self.config.get("mouse_support", True)) and not (self.show_console and self.console_focused)
        self.set_mouse_tracking(should_enable)

    def suspend_tui(self, fd: int, old_settings):
        """Verlässt die Vollbildansicht (für Editor, Shell, interaktive Programme)."""
        self.set_mouse_tracking(False)
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
        sys.stdout.write(ENABLE_AUTOWRAP + SHOW_CURSOR + "\033[?1049l")
        sys.stdout.flush()

    def resume_tui(self, fd: int):
        """Kehrt in die Vollbildansicht zurück und erzwingt ein vollständiges Neuzeichnen."""
        tty.setcbreak(fd, termios.TCSADRAIN)
        try:
            termios.tcflush(fd, termios.TCIFLUSH)  # liegengebliebene Tasten des Fremdprogramms verwerfen
        except Exception:
            pass
        sys.stdout.write("\033[?1049h" + HIDE_CURSOR + DISABLE_AUTOWRAP + "\033[?1007h")
        self.sync_mouse_state()
        sys.stdout.write("\033[2J\033[3J\033[H")
        sys.stdout.flush()
        self._prev_frame = None
        self.refresh_items()

    def load_config(self) -> dict:
        """Delegiert an die zentrale Konfigurationslogik (Single Source of Truth)."""
        return load_config()

    def set_status(self, msg: str, level: str = "info"):
        self.status_message = msg
        self.status_level = level
        self.status_expiry_moves = 0
        self.status_time = time.monotonic()
    @staticmethod
    def dir_stamp(path: str) -> int:
        """Änderungsstempel eines Ordners (ändert sich bei Anlegen, Löschen und Umbenennen von Einträgen)."""
        try:
            return os.stat(path).st_mtime_ns
        except OSError:
            return -1

    def get_raw_entries(self, path: str, fresh: bool = False) -> List[FileEntry]:
        """Liefert die Einträge eines Ordners aus dem Cache; veraltete Caches werden automatisch neu eingelesen."""
        stamp = self.dir_stamp(path)
        cached = self._raw_cache.get(path)
        if cached and cached[0] == stamp and not fresh:
            return cached[2]
        entries = scan_raw(path)
        self._raw_version += 1
        self._raw_cache[path] = (stamp, self._raw_version, entries)
        if len(self._raw_cache) > 64:
            oldest = min(self._raw_cache, key=lambda p: self._raw_cache[p][1])
            if oldest != path:
                del self._raw_cache[oldest]
        return entries

    def get_arranged(self, path: str, use_filter: bool = False) -> List[FileEntry]:
        """Liefert die gefilterte und sortierte Ansicht eines Ordners (mit Cache je Konfiguration)."""
        raw = self.get_raw_entries(path)
        version = self._raw_cache[path][1]
        cfg = self.config
        flt = self.filter_query if use_filter else ""
        key = (path, version, cfg.get("show_hidden", False), cfg.get("sort_by", "mtime"),
               cfg.get("sort_reverse", True), cfg.get("sort_dir_first", True), flt)
        res = self._arranged_cache.get(key)
        if res is None:
            res = arrange_entries(raw, key[2], key[3], key[4], key[5], flt)
            if len(self._arranged_cache) > 48:
                self._arranged_cache.clear()
            self._arranged_cache[key] = res
        return res

    def refresh_items(self, force: bool = True):
        """Liest den aktuellen Ordner frisch ein. Der Cursor bleibt auf derselben Datei, auch wenn sich die Liste ändert.

        Der Parameter `force` bleibt aus Kompatibilitätsgründen erhalten; es wird stets frisch eingelesen,
        denn die Anzeige muss jederzeit exakt den Ordnerzustand widerspiegeln.
        """
        prev_path = None
        prev_idx = self.selected_idx
        if self.items and 0 <= self.selected_idx < len(self.items):
            prev_path = self.items[self.selected_idx].path

        self._cur_stamp = self.dir_stamp(self.current_dir)
        raw = self.get_raw_entries(self.current_dir, fresh=True)
        self._cur_sig = listing_signature(raw)
        # Cache löschen, um sicherzustellen, dass neue Sortieroptionen angewendet werden
        self.clear_sort_caches()
        self.items = self.get_arranged(self.current_dir, use_filter=True)

        if prev_path is not None:
            for i, it in enumerate(self.items):
                if it.path == prev_path:
                    self.selected_idx = i
                    break
            else:
                self.selected_idx = prev_idx
        if self.selected_idx >= len(self.items):
            self.selected_idx = max(0, len(self.items) - 1)
        if self.selected_idx < 0:
            self.selected_idx = 0

    def poll_changes(self) -> bool:
        """Prüft kostengünstig auf Änderungen im Dateisystem; True bedeutet: Bildschirm neu zeichnen.

        Ordner-Stempel werden bei jedem Aufruf geprüft (ein stat-Aufruf je sichtbarem Ordner). Zusätzlich
        werden die sichtbaren Ordner in adaptiven Abständen komplett neu eingelesen, damit auch Größen- und
        Zeitänderungen einzelner Dateien (z. B. laufende Downloads) sofort erscheinen.
        """
        changed = False
        now = time.monotonic()

        if (self.status_message and not self.active_dialog and self.status_time
                and now - self.status_time > self.STATUS_TIMEOUT):
            self.status_message = ""
            changed = True

        full_poll = now >= self._next_full_poll
        if full_poll or self.dir_stamp(self.current_dir) != self._cur_stamp:
            before = self._cur_sig
            t0 = time.monotonic()
            self.refresh_items()
            elapsed = time.monotonic() - t0
            if self._cur_sig != before:
                changed = True
            if full_poll:
                self._next_full_poll = time.monotonic() + max(0.5, elapsed * 10)

        for path in self._pane_paths:
            cached = self._raw_cache.get(path)
            if cached is None or cached[0] != self.dir_stamp(path):
                changed = True
            elif full_poll:
                old_sig = listing_signature(cached[2])
                new_entries = self.get_raw_entries(path, fresh=True)
                if listing_signature(new_entries) != old_sig:
                    changed = True
        return changed

    def enter_directory(self, new_path: str):
        """Wechselt in einen Ordner und setzt Cursor, Ansicht und Filter zurück.
        Eine zuvor gemerkte Zeigerposition des Zielordners wird wiederhergestellt."""
        new_path = os.path.abspath(new_path)
        if new_path != self.current_dir:
            self.dir_cursor_memory[self.current_dir] = self.selected_idx
        self.current_dir = new_path
        self.items = []
        self.selected_idx = 0
        self.view_start = 0
        if self.filter_query:
            self.filter_query = ""
        self.refresh_items()
        remembered_idx = self.dir_cursor_memory.get(self.current_dir)
        if remembered_idx is not None and self.items:
            self.selected_idx = max(0, min(remembered_idx, len(self.items) - 1))

    def touch_last_used_dir(self):
        """Merkt den aktuellen Ordner als 'zuletzt verwendet' — wird von Aktionen aufgerufen,
        nicht von der reinen Navigation."""
        self.last_visited_dir = self.current_dir

    def change_directory(self, new_path: str):
        if os.path.isdir(new_path):
            self.enter_directory(new_path)

    def select_filename(self, name: str) -> bool:
        """Wählt eine Datei nach Namen aus und stellt sicher, dass die Dateiliste aktuell ist."""
        self.refresh_items()
        for i, it in enumerate(self.items):
            if it.name == name:
                self.selected_idx = i
                return True
        return False

    def reveal_filename(self, name: str) -> bool:
        """Wie select_filename, hebt aber Filter und Versteckt-Ausblendung auf, falls sie den Eintrag verbergen."""
        if self.select_filename(name):
            return True
        if self.filter_query:
            self.filter_query = ""
            if self.select_filename(name):
                return True
        if name.startswith(".") and not self.config.get("show_hidden", False):
            self.config["show_hidden"] = True
            self.refresh_items()
            return self.select_filename(name)
        return False

    def go_parent_directory(self):
        parent = os.path.dirname(self.current_dir)
        if parent and parent != self.current_dir:
            prev_name = os.path.basename(self.current_dir)
            self.enter_directory(parent)
            self.select_filename(prev_name)
            # Stelle sicher, dass der Cursor nicht auf 0 bleibt, falls select_filename fehlschlägt
            if self.selected_idx == 0 and self.items and self.items[0].name != prev_name:
                # Falls der vorherige Ordner nicht gefunden wurde, suche ihn in allen Items
                for i, it in enumerate(self.items):
                    if it.name == prev_name:
                        self.selected_idx = i
                        break
    @staticmethod
    def build_command(template: str, path: str) -> str:
        """Setzt den Pfad (sicher für die Shell gequotet) in eine Befehlsvorlage ein; ohne %s wird er angehängt."""
        quoted = shlex.quote(path)
        return template.replace("%s", quoted) if "%s" in template else f"{template} {quoted}"

    def open_with_system(self, item: FileEntry):
        opener = self.config.get("opener", "open %s") or "open %s"
        cmd = self.build_command(opener, item.path)
        user_shell, env = get_shell_environment()
        try:
            subprocess.Popen([user_shell, "-c", cmd], start_new_session=True, env=env,
                             stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            self.set_status(f"Geöffnet: {item.name}", "success")
        except Exception as e:
            self.set_status(f"Fehler: {e}", "error")

    def open_in_editor(self, item: FileEntry, fd: Optional[int], old_settings):
        """Öffnet die Datei im konfigurierten Texteditor (Standard: nano; in den Einstellungen änderbar)."""
        if item.is_dir:
            self.set_status("Ordner lassen sich nicht im Editor öffnen", "warning")
            return
        template = self.config.get("text_editor", "nano %s") or "nano %s"
        user_shell, env = get_shell_environment()
        try:
            editor_bin = shlex.split(template)[0]
        except (ValueError, IndexError):
            self.set_status(f"Ungültiger Editor-Befehl: {template}", "error")
            return
        if not shutil.which(editor_bin, path=env.get("PATH")):
            self.set_status(f"Editor „{editor_bin}“ nicht gefunden (Einstellung: m)", "error")
            return
        if fd is None or old_settings is None:
            return
        cmd = self.build_command(template, item.path)
        self.suspend_tui(fd, old_settings)
        try:
            subprocess.run([user_shell, "-c", cmd], env=env, cwd=self.current_dir)
        except KeyboardInterrupt:
            pass
        except Exception as e:
            self.set_status(f"Fehler beim Editor: {e}", "error")
        finally:
            self.resume_tui(fd)

    def toggle_select(self):
        if not self.items:
            return
        self.touch_last_used_dir()
        item = self.items[self.selected_idx]
        if item.path in self.selected_paths:
            self.selected_paths.remove(item.path)
            self.set_status(f"Auswahl: {len(self.selected_paths)}" if self.selected_paths else "Auswahl aufgehoben")
        else:
            self.selected_paths.add(item.path)
            if item.path in self.clipboard_paths:
                self.clipboard_paths.remove(item.path)
            self.set_status(f"Auswahl: {len(self.selected_paths)}")
        if self.selected_idx < len(self.items) - 1:
            self.selected_idx += 1

    def toggle_select_all(self):
        all_paths = {it.path for it in self.items}
        if not all_paths:
            return
        self.touch_last_used_dir()
        if self.selected_paths.issuperset(all_paths):
            self.selected_paths.clear()
            self.set_status("Auswahl aufgehoben")
        else:
            self.selected_paths.update(all_paths)
            self.set_status(f"Alle {len(self.selected_paths)} markiert")

    def cut_selection(self):
        if not self.items:
            return
        self.touch_last_used_dir()
        cur_p = self.items[self.selected_idx].path
        if self.selected_paths:
            # Auswahl zur Vormerkung hinzufügen; bestehende Vormerkung bleibt erhalten (ohne ESC wird nichts aufgehoben)
            targets = list(self.clipboard_paths)
            for p in self.selected_paths:
                if p not in targets:
                    targets.append(p)
            self.selected_paths.clear()
        elif self.clipboard_mode == "cut" and cur_p in self.clipboard_paths:
            # Toggle: Vormerkung zurück in die Auswahl übernehmen (wieder mit "*" markiert)
            self.selected_paths.update(self.clipboard_paths)
            self.clipboard_mode = None
            self.clipboard_paths = []
            self.set_status(f"Auswahl: {len(self.selected_paths)}")
            return
        elif self.clipboard_paths:
            # Zeiger-Datei zur Vormerkung hinzufügen statt die Vormerkung zu ersetzen
            targets = list(self.clipboard_paths)
            if cur_p not in targets:
                targets.append(cur_p)
        else:
            targets = [cur_p]
        self.clipboard_mode = "cut"
        self.clipboard_paths = targets
        sync_to_macos_clipboard(targets)
        self.set_status(f"{len(targets)} ausgeschnitten (p = einfügen)", "warning")

    def copy_selection(self):
        if not self.items:
            return
        self.touch_last_used_dir()
        cur_p = self.items[self.selected_idx].path
        if self.selected_paths:
            # Auswahl zur Vormerkung hinzufügen; bestehende Vormerkung bleibt erhalten (ohne ESC wird nichts aufgehoben)
            targets = list(self.clipboard_paths)
            for p in self.selected_paths:
                if p not in targets:
                    targets.append(p)
            self.selected_paths.clear()
        elif self.clipboard_mode == "copy" and cur_p in self.clipboard_paths:
            # Toggle: Vormerkung zurück in die Auswahl übernehmen (wieder mit "*" markiert)
            self.selected_paths.update(self.clipboard_paths)
            self.clipboard_mode = None
            self.clipboard_paths = []
            self.set_status(f"Auswahl: {len(self.selected_paths)}")
            return
        elif self.clipboard_paths:
            # Zeiger-Datei zur Vormerkung hinzufügen statt die Vormerkung zu ersetzen
            targets = list(self.clipboard_paths)
            if cur_p not in targets:
                targets.append(cur_p)
        else:
            targets = [cur_p]
        self.clipboard_mode = "copy"
        self.clipboard_paths = targets
        sync_to_macos_clipboard(targets)
        self.set_status(f"{len(targets)} kopiert (Cmd+V im Finder, p hier)", "success")

    def paste_clipboard(self):
        sources = list(self.clipboard_paths) if self.clipboard_paths else get_macos_clipboard_files()
        if not sources:
            self.set_status("Zwischenablage leer", "warning")
            return
        self.touch_last_used_dir()

        # Prüfe auf Konflikte und frage nach Ersetzung
        conflicts = []
        for src in sources:
            if not os.path.exists(src):
                continue
            name = os.path.basename(src)
            dest = os.path.join(self.current_dir, name)
            if os.path.exists(dest):
                conflicts.append((src, dest))

        if conflicts:
            self.active_dialog = "overwrite_confirm"
            self.dialog_input = ""
            self.dialog_cursor = 0
            self.dialog_target_item = None
            self.conflicts_to_resolve = conflicts
            self.conflict_resolution = {}
            return

        # Keine Konflikte - direkt einfügen
        self._perform_paste(sources)

    def _perform_paste(self, sources: List[str], allow_replace: bool = False):
        """Führt das eigentliche Einfügen durch, nachdem Konflikte aufgelöst wurden.

        allow_replace=True wird nach bestätigter Ersetzungsanfrage übergeben: Vorhandene
        Ziele werden dann gesichert und tatsächlich ersetzt statt mit „ (1)“ umzubenennen.
        """
        success = 0
        last_name = ""
        pasted_records = []
        failed = False
        is_cut = (self.clipboard_mode == "cut")
        replaced_backups = []

        for src in sources:
            if not os.path.exists(src):
                continue
            name = os.path.basename(src)
            dest = os.path.join(self.current_dir, name)

            # Überspringe, wenn Quelle und Ziel identisch sind (bei Ausschneiden)
            if os.path.abspath(src) == os.path.abspath(dest) and is_cut:
                continue

            # Bei Kopieren: Füge Nummerierung hinzu, wenn Datei bereits existiert.
            # Nur wenn der Ersetzungsdialog bestätigt wurde, wird wirklich ersetzt.
            backup_dest = None
            if not is_cut and os.path.lexists(dest):
                if allow_replace:
                    backup_dest = self._stash_existing(dest)
                else:
                    base, ext = os.path.splitext(name)
                    c = 1
                    while os.path.lexists(dest):
                        dest = os.path.join(self.current_dir, f"{base} ({c}){ext}")
                        c += 1

            try:
                backup_path = None
                if is_cut and os.path.lexists(dest) and os.path.abspath(src) != os.path.abspath(dest):
                    backup_path = self._stash_existing(dest)
                if is_cut:
                    try:
                        shutil.move(src, dest)
                    except Exception:
                        self._restore_backup(backup_path, dest)
                        raise
                    pasted_records.append((src, dest))
                    if backup_path:
                        replaced_backups.append((dest, backup_path))
                else:
                    try:
                        if os.path.isdir(src):
                            shutil.copytree(src, dest)
                        else:
                            shutil.copy2(src, dest)
                    except Exception:
                        self._restore_backup(backup_dest, dest)
                        raise
                    pasted_records.append((None, dest))
                    if backup_dest:
                        replaced_backups.append((dest, backup_dest))
                success += 1
                last_name = os.path.basename(dest)
            except Exception as e:
                self.set_status(f"Fehler beim Einfügen: {e}", "error")
                failed = True
                break

        if pasted_records:
            desc = f"Einfügen von {len(pasted_records)} Element(en)"
            self.undo_stack.append(UndoAction("paste", desc, {"is_cut": is_cut, "records": pasted_records, "replaced_backups": replaced_backups}))

        if not failed:
            self.clipboard_mode = None
            self.clipboard_paths = []
        self.refresh_items()
        if last_name:
            self.reveal_filename(last_name)
        if not failed:
            self.set_status(f"{success} eingefügt", "success")

    def _perform_replace(self, pr: dict):
        """Führt das bestätigte Ersetzen eines vorhandenen Eintrags aus (Umbenennen bzw. Neuerstellen)."""
        mode = pr.get("mode")
        dest = pr.get("dest")
        name = pr.get("name", "")
        try:
            if mode == "rename":
                src = pr.get("src")
                backup_path = self._stash_existing(dest)
                try:
                    os.rename(src, dest)  # ersetzt eine vorhandene Datei bzw. einen leeren Ordner
                except Exception:
                    self._restore_backup(backup_path, dest)
                    raise
                desc = f"Umbenennen von {os.path.basename(src)} in {name}"
                self.undo_stack.append(UndoAction("rename", desc, {"old_path": src, "new_path": dest, "replaced_backup": backup_path}))
                self.refresh_items(force=True)
                self.select_filename(name)
                self.set_status(f"Ersetzt: {name} (u = Rückgängig)", "success")
            elif mode == "new":
                if pr.get("is_dir_target") and os.path.isdir(dest):
                    # Ordner vorhanden: nichts zu ersetzen
                    self.set_status(f"Ordner existiert bereits: {name}", "info")
                    return
                backup_path = None
                if pr.get("is_dir_target"):
                    os.makedirs(dest, exist_ok=True)
                else:
                    backup_path = self._stash_existing(dest)
                    try:
                        open(dest, "w").close()  # vorhandene Datei durch leere Datei ersetzen
                    except Exception:
                        self._restore_backup(backup_path, dest)
                        raise
                self.refresh_items(force=True)
                self.select_filename(name)
                if pr.get("is_dir_target"):
                    self.set_status(f"Ordner erstellt: {name} (u = Rückgängig)", "success")
                    self.undo_stack.append(UndoAction("create", f"Erstellen von {name}", {"path": dest}))
                else:
                    self.set_status(f"Datei ersetzt: {name} (u = Rückgängig)", "success")
                    self.undo_stack.append(UndoAction("create", f"Ersetzen von {name}", {"path": dest, "replaced_backup": backup_path}))
        except Exception as e:
            self.set_status(f"Fehler beim Ersetzen: {e}", "error")

    def _stash_existing(self, path: str) -> Optional[str]:
        """Sichert einen vorhandenen Pfad vor dem Ersetzen, damit das Rückgängigmachen ihn wiederherstellen kann."""
        if not path or not os.path.lexists(path):
            return None
        os.makedirs(self.UNDO_BACKUP_DIR, exist_ok=True)
        stem, ext = os.path.splitext(os.path.basename(path))
        dest = os.path.join(self.UNDO_BACKUP_DIR, f"{stem}{ext}")
        c = 1
        while os.path.lexists(dest):
            dest = os.path.join(self.UNDO_BACKUP_DIR, f"{stem}_{int(time.time())}_{c}{ext}")
            c += 1
        shutil.move(path, dest)
        return dest

    def _restore_backup(self, backup_path: Optional[str], original_path: str) -> bool:
        """Stellt einen zuvor gesicherten Pfad an seiner ursprünglichen Stelle wieder her."""
        if not backup_path or not os.path.lexists(backup_path):
            return False
        target = original_path
        if os.path.lexists(target):
            stem, ext = os.path.splitext(original_path)
            c = 1
            while os.path.lexists(target):
                target = f"{stem}_wiederhergestellt_{c}{ext}"
                c += 1
        os.makedirs(os.path.dirname(original_path), exist_ok=True)
        shutil.move(backup_path, target)
        return True
    @staticmethod
    def unique_path(directory: str, stem: str, suffix: str = "") -> str:
        """Liefert einen noch nicht vergebenen Pfad „stem suffix“, „stem (1) suffix“, …"""
        dest = os.path.join(directory, f"{stem}{suffix}")
        c = 1
        while os.path.lexists(dest):
            dest = os.path.join(directory, f"{stem} ({c}){suffix}")
            c += 1
        return dest

    def create_zip_archive(self):
        self.touch_last_used_dir()
        """Erstellt ein ZIP-Archiv aus der Auswahl (oder dem Eintrag unter dem Cursor) und springt darauf."""
        targets = list(self.selected_paths) if self.selected_paths else ([self.items[self.selected_idx].path] if self.items else [])
        if not targets:
            self.set_status("Keine Dateien/Ordner ausgewählt", "warning")
            return None

        # Filtere ungültige Pfade (z. B. Socket-Handles oder nicht existierende Dateien)
        valid_entries = []
        for target in sorted(targets):
            if not os.path.exists(target):
                self.set_status(f"Warnung: „{os.path.basename(target)}“ existiert nicht und wird übersprungen", "warning")
                continue
            if stat.S_ISSOCK(os.stat(target).st_mode):
                self.set_status(f"Warnung: „{os.path.basename(target)}“ ist ein Socket und wird übersprungen", "warning")
                continue
            valid_entries.append(FileEntry(target, os.path.basename(target)))

        # Gleiche Anordnung wie in der Dateiansicht, damit Archiv-Inhalt und Vorschau konsistent sortiert sind
        valid_entries = arrange_entries(
            valid_entries,
            show_hidden=True,
            sort_by=self.config.get("sort_by", "mtime"),
            sort_reverse=self.config.get("sort_reverse", True),
            sort_dir_first=self.config.get("sort_dir_first", True),
        )
        valid_targets = [e.path for e in valid_entries]

        if not valid_targets:
            self.set_status("Keine gültigen Dateien/Ordner zum Archivieren", "error")
            return None

        # Bestimme den Basisnamen für das ZIP-Archiv
        if len(valid_targets) == 1:
            base_name = os.path.basename(valid_targets[0])
        else:
            base_name = f"Archiv_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}"
        if base_name.lower().endswith(".zip"):
            base_name = base_name[:-4]

        dest = self.unique_path(self.current_dir, base_name, ".zip")
        skipped = 0

        try:
            with zipfile.ZipFile(dest, "w", zipfile.ZIP_DEFLATED) as zf:
                for target in valid_targets:
                    base_dir = os.path.dirname(os.path.abspath(target))
                    if os.path.isdir(target):
                        for root, dirs, files in os.walk(target):
                            rel_root = os.path.relpath(root, base_dir)
                            if not dirs and not files:
                                zf.writestr(rel_root.rstrip("/") + "/", "")  # leere Ordner bewahren
                            for file in files:
                                file_path = os.path.join(root, file)
                                try:
                                    if not os.path.exists(file_path) or stat.S_ISSOCK(os.stat(file_path).st_mode):
                                        skipped += 1
                                        continue
                                    zf.write(file_path, os.path.relpath(file_path, base_dir))
                                except OSError:
                                    skipped += 1
                    else:
                        try:
                            zf.write(target, os.path.basename(target))
                        except OSError:
                            skipped += 1
        except Exception as e:
            try:
                os.remove(dest)
            except OSError:
                pass
            self.refresh_items()
            self.set_status(f"Fehler beim Erstellen des ZIP-Archivs: {e}", "error")
            return None

        self.selected_paths.clear()
        self.refresh_items()
        zip_name = os.path.basename(dest)
        self.reveal_filename(zip_name)  # Zeiger springt direkt auf das neue Archiv
        self.undo_stack.append(UndoAction("create_zip", f"ZIP {zip_name}", {"path": dest}))
        if skipped:
            self.set_status(f"ZIP erstellt: {zip_name} ({skipped} übersprungen)", "warning")
        else:
            self.set_status(f"ZIP erstellt: {zip_name}", "success")
        return dest

    def extract_zip_archive(self):
        self.touch_last_used_dir()
        """Entpackt markierte bzw. das ausgewählte ZIP-Archiv in einen neuen Ordner und springt darauf."""
        if not self.items:
            self.set_status("Keine Datei ausgewählt", "warning")
            return None

        if self.selected_paths:
            archives = sorted(p for p in self.selected_paths if p.lower().endswith(".zip") and os.path.isfile(p))
            if not archives:
                self.set_status("Keine ZIP-Archive in der Auswahl", "warning")
                return None
        else:
            item = self.items[self.selected_idx]
            if item.is_dir or not item.name.lower().endswith(".zip"):
                self.set_status(f"„{item.name}“ ist kein ZIP-Archiv", "warning")
                return None
            archives = [item.path]

        last_dir = None
        done = 0
        for archive in archives:
            stem = os.path.splitext(os.path.basename(archive))[0] or "Archiv"
            extract_dir = self.unique_path(self.current_dir, stem)
            try:
                with zipfile.ZipFile(archive, "r") as zip_ref:
                    zip_ref.extractall(extract_dir)
            except Exception as e:
                shutil.rmtree(extract_dir, ignore_errors=True)
                reason = "beschädigt oder kein gültiges ZIP" if isinstance(e, zipfile.BadZipFile) else str(e)
                self.set_status(f"Fehler beim Entpacken von „{os.path.basename(archive)}“: {reason}", "error")
                continue
            self.undo_stack.append(UndoAction("create", f"Entpacken von {os.path.basename(archive)}", {"path": extract_dir}))
            last_dir = extract_dir
            done += 1

        self.selected_paths.clear()
        self.refresh_items()
        if last_dir:
            name = os.path.basename(last_dir)
            self.reveal_filename(name)  # Zeiger springt direkt auf den entpackten Ordner
            if done > 1:
                self.set_status(f"{done} ZIP-Archive entpackt (zuletzt: {name})", "success")
            else:
                self.set_status(f"ZIP entpackt nach: {name}", "success")
        return last_dir

    def undo_last_action(self):
        self.touch_last_used_dir()
        """Macht die letzte Dateioperation (Löschen, Umbenennen, Erstellen, Einfügen, ZIP) rückgängig."""
        if not self.undo_stack:
            self.set_status("Nichts zum Rückgängigmachen vorhanden", "info")
            return

        action = self.undo_stack.pop()
        trash_dir = os.path.expanduser("~/.Trash")
        try:
            os.makedirs(trash_dir, exist_ok=True)
        except OSError:
            pass

        try:
            if action.action_type == "trash":
                restored = 0
                for orig_p, trash_p in action.data.get("records", []):
                    if os.path.exists(trash_p):
                        os.makedirs(os.path.dirname(orig_p), exist_ok=True)
                        dest_target = orig_p
                        if os.path.exists(dest_target):
                            stem, ext = os.path.splitext(orig_p)
                            c = 1
                            while os.path.exists(dest_target):
                                dest_target = f"{stem}_restored_{c}{ext}"
                                c += 1
                        shutil.move(trash_p, dest_target)
                        restored += 1
                self.refresh_items(force=True)
                self.set_status(f"Rückgängig: {restored} Element(e) aus Papierkorb wiederhergestellt", "success")

            elif action.action_type == "rename":
                old_p = action.data.get("old_path")
                new_p = action.data.get("new_path")
                if new_p and os.path.exists(new_p) and not os.path.exists(old_p):
                    os.rename(new_p, old_p)
                    restored = self._restore_backup(action.data.get("replaced_backup"), new_p)
                    self.refresh_items(force=True)
                    self.select_filename(os.path.basename(old_p))
                    if restored:
                        self.set_status(f"Rückgängig: Name in „{os.path.basename(old_p)}“ zurückgesetzt, ersetzte Datei wiederhergestellt", "success")
                    else:
                        self.set_status(f"Rückgängig: Name in „{os.path.basename(old_p)}“ zurückgesetzt", "success")

            elif action.action_type == "create":
                p = action.data.get("path")
                # Bei Ordner-Erstellung mit verschobenen Elementen: erst die
                # Elemente an ihren Ursprung zuruecklegen, dann Ordner entfernen.
                for old_src, new_dst in (action.data.get("moved_records") or []):
                    try:
                        if os.path.exists(new_dst) and not os.path.exists(old_src):
                            shutil.move(new_dst, old_src)
                    except Exception:
                        pass
                if p and os.path.exists(p):
                    dest_p = os.path.join(trash_dir, os.path.basename(p))
                    c = 1
                    stem, ext = os.path.splitext(os.path.basename(p))
                    while os.path.exists(dest_p):
                        dest_p = os.path.join(trash_dir, f"{stem}_{int(time.time())}_{c}{ext}")
                        c += 1
                    shutil.move(p, dest_p)
                    restored = self._restore_backup(action.data.get("replaced_backup"), p)
                    self.refresh_items(force=True)
                    if restored:
                        self.set_status(f"Rückgängig: {os.path.basename(p)} gelöscht, ersetzte Datei wiederhergestellt", "success")
                    else:
                        self.set_status(f"Rückgängig: {os.path.basename(p)} gelöscht", "success")

            elif action.action_type == "create_zip":
                p = action.data.get("path")
                if p and os.path.exists(p):
                    dest_p = os.path.join(trash_dir, os.path.basename(p))
                    c = 1
                    stem, ext = os.path.splitext(os.path.basename(p))
                    while os.path.exists(dest_p):
                        dest_p = os.path.join(trash_dir, f"{stem}_{int(time.time())}_{c}{ext}")
                        c += 1
                    shutil.move(p, dest_p)
                    self.refresh_items(force=True)
                    self.set_status(f"Rückgängig: {os.path.basename(p)} gelöscht", "success")

            elif action.action_type == "paste":
                is_cut = action.data.get("is_cut", False)
                records = action.data.get("records", [])
                reverted = 0
                backups = dict(action.data.get("replaced_backups", []))
                for src_p, dest_p in records:
                    if dest_p and os.path.exists(dest_p):
                        if is_cut and src_p:
                            os.makedirs(os.path.dirname(src_p), exist_ok=True)
                            shutil.move(dest_p, src_p)
                            reverted += 1
                            self._restore_backup(backups.get(dest_p), dest_p)
                        else:
                            trash_dest = os.path.join(trash_dir, os.path.basename(dest_p))
                            c = 1
                            stem, ext = os.path.splitext(os.path.basename(dest_p))
                            while os.path.exists(trash_dest):
                                trash_dest = os.path.join(trash_dir, f"{stem}_{int(time.time())}_{c}{ext}")
                                c += 1
                            shutil.move(dest_p, trash_dest)
                            reverted += 1
                            self._restore_backup(backups.get(dest_p), dest_p)
                self.refresh_items(force=True)
                self.set_status(f"Rückgängig: Einfügen von {reverted} Element(en) zurückgesetzt", "success")
        except Exception as e:
            self.set_status(f"Fehler bei Rückgängig: {e}", "error")

    def clear_sort_caches(self):
        """Löscht alle Caches, die von den Sortierparametern abhängen."""
        self.cached_parent_dir = None
        self.cached_parent_items = []
        self.cached_child_path = None
        self.cached_child_items = []
        self._arranged_cache.clear()

    def toggle_sort(self):
        modes = ["mtime", "name", "size", "ext"]
        cur = self.config.get("sort_by", "mtime")
        nxt = modes[(modes.index(cur) + 1) % len(modes)] if cur in modes else "mtime"
        self.config["sort_by"] = nxt
        desc = {"mtime": "Datum", "name": "Name", "size": "Größe", "ext": "Dateityp"}
        self.clear_sort_caches()
        self.refresh_items(force=True)
        self.set_status(f"Sortierung: {desc.get(nxt, nxt)}", "info")

    def get_short_dir(self, path: str) -> str:
        if path == HOME_DIR:
            return "~"
        if path.startswith(HOME_DIR + "/"):
            return "~" + path[len(HOME_DIR):]
        return path

    def load_file_preview_lines(self, path: str, max_lines: int, wrap_width: Optional[int] = None) -> List[str]:
        cfg = self.config
        # Sortierparameter gehören zum Cache-Schlüssel, damit die Vorschau derselben Anordnung wie die Dateispalten folgt
        sort_key = (path, cfg.get("sort_by", "mtime"), cfg.get("sort_reverse", True), cfg.get("sort_dir_first", True))
        # Änderungstempel der Datei: bei Inhaltsänderung (z. B. externer Editor) wird die Vorschau neu geladen
        try:
            st = os.stat(path)
            file_stamp: Optional[Tuple[int, int]] = (st.st_mtime_ns, st.st_size)
        except OSError:
            file_stamp = None
        cache_key = (sort_key, file_stamp)
        if (self.cached_file_preview_path != path or self.cached_file_preview_key != cache_key
                or not self.cached_file_preview_lines):
            lines = []
            try:
                if zipfile.is_zipfile(path):
                    with zipfile.ZipFile(path, "r") as zf:
                        infos = zf.infolist()
                        zip_entries = []
                        for info in infos:
                            fe = FileEntry("", info.filename)
                            fe.size = info.file_size
                            fe.is_dir = info.is_dir()
                            try:
                                fe.mtime = time.mktime(info.date_time + (0, 0, -1))
                            except (OverflowError, ValueError):
                                fe.mtime = 0.0
                            zip_entries.append(fe)
                        # Gleiche Anordnung wie in den Dateispalten (versteckte Dateien eingeschlossen)
                        zip_entries = arrange_entries(
                            zip_entries,
                            show_hidden=True,
                            sort_by=cfg.get("sort_by", "mtime"),
                            sort_reverse=cfg.get("sort_reverse", True),
                            sort_dir_first=cfg.get("sort_dir_first", True),
                        )
                        lines.append(f"Archiv-Inhalt ({len(infos)} Dateien):")
                        for fe in zip_entries[:max_lines - 1]:
                            if fe.is_dir:
                                lines.append(f" {fe.name}")
                            else:
                                lines.append(f" {fe.name} ({format_size(fe.size)})")
                else:
                    with open(path, "r", encoding="utf-8", errors="replace") as f:
                        for _ in range(max_lines * 3):  # Mehr Zeilen lesen, falls Umbruch aktiviert ist
                            line = f.readline()
                            if not line:
                                break
                            clean_line = line.rstrip("\r\n").replace("\t", "    ")
                            clean_line = re.sub(r"[\x00-\x08\x0b-\x1f\x7f-\x9f]", "", clean_line)
                            lines.append(clean_line)
            except Exception:
                lines = ["[Binäre Datei oder nicht lesbar]"]

            self.cached_file_preview_path = path
            self.cached_file_preview_key = cache_key
            self.cached_file_preview_lines = lines

        lines = self.cached_file_preview_lines

        # Umbruch nach dem Cache anwenden, damit auch Cache-Treffer und Breitenänderungen (Resize) umbrechen
        if self.preview_wrap and wrap_width and wrap_width > 0:
            wrapped = []
            for l in lines[:max_lines * 3]:
                wrapped.extend(wrap_line_to_width(l, wrap_width))
            return wrapped[:max_lines]

        return lines[:max_lines]

    def get_console_display_lines(self, width: int, height: int) -> List[str]:
        if height <= 0 or width <= 0:
            return []
        # Standard: nur "$ " ohne Pfad
        prompt = "$ "
        # Ausnahme: interaktiver Befehl + Konsole füllt Fenster (große Höhe)
        if self.last_cmd_interactive and height >= 15:
            full_prompt = f"{self.get_short_dir(self.current_dir)} $ "
            if str_width(full_prompt) <= width - 4:
                prompt = full_prompt
        avail = max(1, width - str_width(prompt))
        inp = self.console_input
        c_pos = self.console_cursor_idx

        if len(inp) + 1 > avail:
            start = max(0, min(c_pos - avail + 5, len(inp) - avail + 1))
            disp_slice = inp[start:start + avail]
            rel_c = c_pos - start
            if self.console_focused:
                if 0 <= rel_c < len(disp_slice):
                    disp_inp = disp_slice[:rel_c] + f"{C_INVERT}{disp_slice[rel_c]}{C_RESET}" + disp_slice[rel_c+1:]
                else:
                    disp_inp = disp_slice + f"{C_INVERT} {C_RESET}"
            else:
                disp_inp = disp_slice
        else:
            if self.console_focused:
                if c_pos < len(inp):
                    disp_inp = inp[:c_pos] + f"{C_INVERT}{inp[c_pos]}{C_RESET}" + inp[c_pos+1:]
                else:
                    disp_inp = inp + f"{C_INVERT} {C_RESET}"
            else:
                disp_inp = inp

        prompt_line = pad_to_width(f"{prompt}{disp_inp}", width)
        out = []
        needed = height - 1
        if needed > 0:
            wrapped_lines: List[str] = []
            for raw_line in self.console_output_lines:
                wrapped_lines.extend(wrap_line_to_width(raw_line, width))
            max_off = max(0, len(wrapped_lines) - needed)
            self.console_scroll_offset = max(0, min(max_off, self.console_scroll_offset))
            start = max(0, len(wrapped_lines) - needed - self.console_scroll_offset)
            chunk = wrapped_lines[start: start + needed]
            for l in chunk:
                out.append(pad_to_width(l, width))
            while len(out) < needed:
                out.insert(0, " " * width)
        out.append(prompt_line)
        return out

    _CONSOLE_IGNORED_PATTERNS = (
        "restored session", "saving session", "saving history",
        "copying shared history", "copying history", "completed.",
        "no job control in this shell",
        "session contents restored", "session saved",
    )

    def _append_console_output(self, text: str) -> None:
        """Fuegt Ausgabe der Konsole hinzu: filtert Shell-Stoerzeilen, entfernt
        ANSI- und Steuerzeichen und begrenzt den Puffer."""
        for l in text.splitlines():
            l_lower = l.lower()
            if any(p in l_lower for p in self._CONSOLE_IGNORED_PATTERNS):
                continue
            clean_l = ANSI_ESCAPE_RE.sub("", l)
            clean_l = clean_l.replace("\t", "        ")
            clean_l = re.sub(r"[\x00-\x08\x0b-\x1f\x7f-\x9f]", "", clean_l)
            if clean_l:
                self.console_output_lines.append(clean_l)
        limit = 10000
        if len(self.console_output_lines) > limit:
            del self.console_output_lines[:len(self.console_output_lines) - limit]

    def _render_console_live(self) -> None:
        """Zeichnet den Bildschirm waehrend eines laufenden Befehls neu, damit
        die streamende Konsolenausgabe live sichtbar ist."""
        try:
            curr_size = shutil.get_terminal_size((80, 24))
            term_cols, term_rows = curr_size.columns, curr_size.lines
            lines = self.build_screen(term_cols, term_rows)
            out_buf = [f"\033[1;{term_rows}r"]
            for r_idx, l in enumerate(lines[:term_rows]):
                out_buf.append(f"\033[{r_idx+1};1H\033[2K{l}")
            sys.stdout.write("".join(out_buf))
            sys.stdout.flush()
        except Exception:
            pass

    def _run_console_streaming(self, cmd: str, user_shell: str, env, fd: Optional[int]) -> None:
        """Fuehrt einen nicht-interaktiven Befehl in einem echten Pseudo-Terminal
        aus. Verhaelt sich wie ein Standard-Terminal: Ausgabe streamt live ins
        Panel, Strg+C erreicht den Befehl selbst (erst SIGINT, dann SIGKILL),
        es gibt kein hartes Zeitlimit."""
        master_fd, slave_fd = os.openpty()
        try:
            proc = subprocess.Popen(
                [user_shell, "-l", "-i", "-c", cmd],
                cwd=self.current_dir,
                stdin=slave_fd,
                stdout=slave_fd,
                stderr=slave_fd,
                env=env,
                start_new_session=True,
            )
        except Exception:
            os.close(master_fd)
            os.close(slave_fd)
            raise
        os.close(slave_fd)

        watch_stdin = fd is not None
        buf = b""
        last_render = 0.0
        ctrl_c_count = 0
        try:
            while True:
                try:
                    rlist, _, _ = select.select([master_fd] + ([fd] if watch_stdin else []), [], [], 0.1)
                except InterruptedError:
                    continue
                if watch_stdin and fd in rlist:
                    try:
                        in_data = os.read(fd, 32)
                    except OSError:
                        in_data = b""
                    if b"\x03" in in_data:
                        ctrl_c_count += 1
                        self.console_output_lines.append("^C")
                        try:
                            if ctrl_c_count == 1:
                                os.killpg(proc.pid, signal.SIGINT)
                            else:
                                os.killpg(proc.pid, signal.SIGKILL)
                        except Exception:
                            pass
                if master_fd in rlist:
                    try:
                        chunk = os.read(master_fd, 65536)
                    except OSError:
                        chunk = b""
                    if not chunk:
                        break
                    buf += chunk
                    while True:
                        positions = [p for p in (buf.find(b"\n"), buf.find(b"\r")) if p >= 0]
                        if not positions:
                            break
                        nl = min(positions)
                        line, buf = buf[:nl], buf[nl + 1:]
                        self._append_console_output(line.decode("utf-8", errors="replace"))
                    now = time.monotonic()
                    if now - last_render >= 0.15:
                        last_render = now
                        self._render_console_live()
            if buf:
                self._append_console_output(buf.decode("utf-8", errors="replace"))
            try:
                proc.wait(timeout=5)
            except Exception:
                try:
                    os.killpg(proc.pid, signal.SIGKILL)
                except Exception:
                    pass
                try:
                    proc.wait(timeout=2)
                except Exception:
                    pass
        finally:
            try:
                os.close(master_fd)
            except OSError:
                pass

    def run_console_command(self, cmd: str, fd: Optional[int], old_settings):
        cmd = cmd.strip()
        self.console_input = ""
        self.console_cursor_idx = 0
        if not cmd:
            return
        self.touch_last_used_dir()
        self.console_cmd_history.append(cmd)
        self.console_history_idx = len(self.console_cmd_history)
        self.console_output_lines.append(f"$ {cmd}")
        self.console_scroll_offset = 0
        if cmd in ("exit", "quit"):
            if not self.console_always_visible:
                self.show_console = False
                self.console_focused = False
            else:
                self.set_status("Konsole immer eingeblendet")
            return
        if cmd == "clear":
            self.console_output_lines.clear()
            self.console_scroll_offset = 0
            return
        if cmd.startswith("cd ") or cmd == "cd":
            target = cmd[3:].strip() if len(cmd) > 3 else HOME_DIR
            target = os.path.expanduser(target)
            target = os.path.join(self.current_dir, target)
            if os.path.isdir(target):
                self.change_directory(target)
            else:
                self.console_output_lines.append(f"cd: Verzeichnis nicht gefunden: {target}")
            return
        tokens = cmd.split()
        first_prog = os.path.basename(tokens[0]) if tokens else ""
        interactive_tools = {
            "start", "aider", "goose", "agy", "agy-real", "nano", "vim", "vi", "emacs", "micro",
            "nvim", "helix", "hx", "kak", "ed", "joe", "ne",
            "top", "htop", "btop", "glances", "bottom", "nvtop", "gtop",
            "less", "more", "bat", "most", "man", "info", "pydoc",
            "python", "python3", "ipython", "node", "ruby", "irb", "php", "lua", "julia", "gh",
            "bash", "zsh", "sh", "fish", "ksh", "csh", "tcsh",
            "ssh", "sftp", "telnet", "nc", "netcat",
            "fzf", "fzy", "peco", "skim", "sk",
            "tmux", "screen", "zellij", "cmatrix", "lazygit", "lazydocker", "tig",
            "mac_control", "settings", "sudo", "su", "passwd", "nmtui",
            "sqlite3", "psql", "mysql", "redis-cli", "mongosh",
            "lki", "ki-lokal", "kil"
        }
        has_interactive_pipe = any(p in cmd for p in ["| less", "| more", "| bat", "| most", "| fzf"])
        is_git_interactive = cmd.startswith("git ") and any(sub in cmd for sub in ["log", "diff", "commit", "add -p", "add -i", "rebase", "branch", "show", "stash", "blame"])
        is_standalone_stdin_tool = (first_prog in ("cat", "grep", "egrep", "fgrep", "sed", "awk", "head", "tail", "cut", "sort", "uniq", "wc")) and (len(tokens) <= 2 and not any(ch in cmd for ch in ("<", ">", "|", "/", ".")))

        is_interactive = (first_prog in interactive_tools) or has_interactive_pipe or is_git_interactive or is_standalone_stdin_tool
        self.last_cmd_interactive = is_interactive

        user_shell, env = get_shell_environment()

        if is_interactive and fd is not None and old_settings is not None:
            self.set_mouse_tracking(False)
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
            sys.stdout.write(ENABLE_AUTOWRAP + SHOW_CURSOR + "\033[?1049l")
            sys.stdout.flush()
            try:
                subprocess.run([user_shell, "-l", "-i", "-c", cmd], cwd=self.current_dir, env=env)
            except KeyboardInterrupt:
                pass
            except Exception as e:
                self.console_output_lines.append(f"Fehler: {e}")
            finally:
                tty.setcbreak(fd, termios.TCSADRAIN)
                sys.stdout.write("\033[?1049h" + HIDE_CURSOR + DISABLE_AUTOWRAP + "\033[?1007h")
                self.sync_mouse_state()
                sys.stdout.write("\033[2J\033[3J\033[H")
                sys.stdout.flush()
                self.refresh_items(force=True)
            return
        try:
            self._run_console_streaming(cmd, user_shell, env, fd)
        except KeyboardInterrupt:
            self.console_output_lines.append("^C")
        except Exception as e:
            self.console_output_lines.append(f"Fehler: {e}")
        self.refresh_items(force=True)
    def toggle_console(self):
        if self.console_always_visible:
            # Wenn Konsole immer eingeblendet ist, kann sie nicht ausgeblendet werden
            self.set_status("Konsole immer eingeblendet")
            return
        self.show_console = not self.show_console
        self.console_focused = self.show_console
        self.set_status("Konsole geöffnet" if self.show_console else "Konsole geschlossen")

    def handle_mouse_click(self, x: int, y: int) -> bool:
        if not self.last_layout:
            return False
        layout = self.last_layout
        hdr_count = layout.get("header_lines", 2)
        avail_rows = layout.get("avail_rows", 0)
        eff_cols = layout.get("eff_cols", 1)
        w_left = layout.get("w_left", 0)
        w_mid = layout.get("w_mid", 0)
        m_start = layout.get("m_start", 0)
        active_console = layout.get("active_console", False)
        console_pos = layout.get("console_pos", "unten")
        split_row = layout.get("split_row", -1)

        if y == 1:
            return True
        if active_console and console_pos == "unten" and split_row > 0:
            if y > split_row:
                self.console_focused = True
                return True
            else:
                self.console_focused = False

        file_row = (y - 1) - hdr_count
        if 0 <= file_row < avail_rows:
            col_x = x - 1
            if active_console and console_pos == "rechts" and col_x >= (w_left + w_mid + 2):
                self.console_focused = True
                return True
            elif active_console and console_pos == "links" and col_x <= w_left:
                self.console_focused = True
                return True
            self.console_focused = False
            in_left = (eff_cols >= 2 and col_x <= w_left)
            in_mid = (eff_cols == 1 and col_x <= w_mid) or (eff_cols >= 2 and (w_left + 1) <= col_x <= (w_left + 1 + w_mid))
            in_right = (eff_cols == 3 and col_x >= (w_left + w_mid + 2))
            if in_left and not (active_console and console_pos == "links"):
                self.go_parent_directory()
                return True
            elif in_mid:
                target_idx = m_start + file_row
                if 0 <= target_idx < len(self.items):
                    now = datetime.datetime.now().timestamp()
                    is_double = (now - self.last_click_time < 0.45) and (self.last_click_idx == target_idx)
                    self.selected_idx = target_idx
                    if is_double:
                        self.last_click_time = 0.0
                        self.last_click_idx = None
                        self.open_with_system(self.items[target_idx])
                    else:
                        self.last_click_time = now
                        self.last_click_idx = target_idx
                    return True
            elif in_right and not (active_console and console_pos == "rechts"):
                cur_item = layout.get("cur_item")
                if cur_item and layout.get("is_cur_dir"):
                    child_items = layout.get("child_items", [])
                    if 0 <= file_row < len(child_items):
                        self.change_directory(cur_item.path)
                        self.selected_idx = file_row
                        return True
                elif cur_item and not layout.get("is_cur_dir"):
                    self.open_with_system(cur_item)
                    return True
        return False

    def handle_mouse_right_click(self, x: int, y: int) -> bool:
        if not self.last_layout:
            return False
        layout = self.last_layout
        hdr_count = layout.get("header_lines", 2)
        avail_rows = layout.get("avail_rows", 0)
        m_start = layout.get("m_start", 0)
        file_row = (y - 1) - hdr_count
        if 0 <= file_row < avail_rows:
            target_idx = m_start + file_row
            if 0 <= target_idx < len(self.items):
                self.selected_idx = target_idx
                self.toggle_select()
                return True
        return False

    def handle_mouse_wheel(self, direction: str, x: Optional[int] = None, y: Optional[int] = None) -> bool:
        """Behandelt Mausrad-Events präzise nach Mausposition und Fokus."""
        layout = self.last_layout or {}
        active_console = layout.get("active_console", False) or self.show_console
        console_pos = layout.get("console_pos", "unten")
        split_row = layout.get("split_row", -1)
        w_left = layout.get("w_left", 0)
        w_mid = layout.get("w_mid", 0)

        is_over_console = False
        if active_console:
            if y is not None and x is not None:
                if console_pos == "unten" and split_row > 0 and y >= split_row:
                    is_over_console = True
                elif console_pos == "rechts" and x >= (w_left + w_mid + 2):
                    is_over_console = True
                elif console_pos == "links" and x <= w_left:
                    is_over_console = True
            elif self.console_focused:
                is_over_console = True

        if is_over_console or (self.show_console and self.console_focused):
            # Berechne die Gesamtzahl der Zeilen in der Konsole nach dem Umbruch
            wrapped_lines: List[str] = []
            for raw_line in self.console_output_lines:
                wrapped_lines.extend(wrap_line_to_width(raw_line, max(1, shutil.get_terminal_size((80, 24)).columns - 4)))

            # Maximale Scroll-Position berechnen
            max_scroll = max(0, len(wrapped_lines) - 1)

            if direction == "up":
                # Nach oben scrollen (Inhalt nach unten bewegen)
                self.console_scroll_offset = min(max_scroll, self.console_scroll_offset + 2)
            else:
                # Nach unten scrollen (Inhalt nach oben bewegen)
                self.console_scroll_offset = max(0, self.console_scroll_offset - 2)
            return True
        else:
            if direction == "up":
                if self.items:
                    self.selected_idx = max(0, self.selected_idx - 1)
                    self.refresh_items(force=True)
            else:
                if self.items:
                    self.selected_idx = min(len(self.items) - 1, self.selected_idx + 1)
                    self.refresh_items(force=True)
            return True

    def handle_dialog_key(self, key: str, fd: int) -> bool:
        if not self.active_dialog:
            return False

        if key in ("ESC", "CTRL_C"):
            if self.active_dialog == "overwrite_confirm":
                # Abbrechen des gesamten Einfügevorgangs
                self.active_dialog = None
                self.conflicts_to_resolve = []
                self.conflict_resolution = {}
                self.set_status("Einfügen abgebrochen", "warning")
            elif self.active_dialog == "replace_confirm":
                self.active_dialog = None
                self.pending_replace = None
                self.set_status("Ersetzen abgebrochen", "warning")
            else:
                self.active_dialog = None
                self.dialog_input = ""
                self.dialog_cursor = 0
                self.dialog_target_item = None
                self.help_scroll_offset = 0
                self.set_status("Aktion abgebrochen")
            return True

        if self.active_dialog == "help_menu":
            if key in ("ESC", "q", "Q", "h", "H", "ENTER", "SPACE", " "):
                self.active_dialog = None
                self.help_scroll_offset = 0
                self.set_status("Hilfe geschlossen")
                return True
            elif key in ("UP", "k") or key.startswith("MOUSE_WHEEL_UP"):
                self.help_scroll_offset = max(0, self.help_scroll_offset - 1)
                return True
            elif key in ("DOWN", "j") or key.startswith("MOUSE_WHEEL_DOWN"):
                self.help_scroll_offset += 1
                return True
            elif key in ("PAGE_UP",):
                self.help_scroll_offset = max(0, self.help_scroll_offset - 6)
                return True
            elif key in ("PAGE_DOWN",):
                self.help_scroll_offset += 6
                return True
            self.active_dialog = None
            self.help_scroll_offset = 0
            return True

        if self.active_dialog == "trash_confirm":
            if key in ("y", "Y", "ENTER"):
                targets = list(self.selected_paths) if self.selected_paths else ([self.items[self.selected_idx].path] if self.items else [])
                trash_dir = os.path.expanduser("~/.Trash")
                os.makedirs(trash_dir, exist_ok=True)
                moved_records = []

                for t in targets:
                    if not os.path.exists(t):
                        continue
                    base_name = os.path.basename(t)
                    dest_p = os.path.join(trash_dir, base_name)
                    c = 1
                    stem, ext = os.path.splitext(base_name)
                    while os.path.exists(dest_p):
                        dest_p = os.path.join(trash_dir, f"{stem}_{int(time.time())}_{c}{ext}")
                        c += 1
                    try:
                        shutil.move(t, dest_p)
                        moved_records.append((t, dest_p))
                    except Exception:
                        pass

                if moved_records:
                    desc = f"{len(moved_records)} Element(e) löschen" if len(moved_records) > 1 else f"Löschen von {os.path.basename(moved_records[0][0])}"
                    self.undo_stack.append(UndoAction("trash", desc, {"records": moved_records}))

                self.selected_paths.clear()
                self.clipboard_paths = [p for p in self.clipboard_paths if p not in targets]
                if not self.clipboard_paths:
                    self.clipboard_mode = None
                self.refresh_items(force=True)
                self.set_status(f"{len(moved_records)} Element(e) in Papierkorb verschoben (u = Rückgängig)", "success")
            else:
                self.set_status("Löschen abgebrochen")
            self.active_dialog = None
            return True

        if self.active_dialog == "overwrite_confirm":
            if not self.conflicts_to_resolve:
                self.active_dialog = None
                return True

            src, dest = self.conflicts_to_resolve[0]

            if key in ("y", "Y"):
                # Aktuelle Datei ersetzen
                self.conflict_resolution[dest] = "replace"
                self.conflicts_to_resolve.pop(0)
                if not self.conflicts_to_resolve:
                    # Alle Konflikte aufgelöst - Einfügen durchführen
                    sources = list(self.clipboard_paths) if self.clipboard_paths else get_macos_clipboard_files()
                    filtered_sources = []
                    for s in sources:
                        if not os.path.exists(s):
                            continue
                        name = os.path.basename(s)
                        d = os.path.join(self.current_dir, name)
                        if d in self.conflict_resolution:
                            if self.conflict_resolution[d] == "replace":
                                filtered_sources.append(s)
                        else:
                            filtered_sources.append(s)
                    self._perform_paste(filtered_sources, allow_replace=True)
                return True
            elif key in ("a", "A"):
                # Alle Dateien ersetzen
                for _, d in self.conflicts_to_resolve:
                    self.conflict_resolution[d] = "replace"
                self.conflicts_to_resolve = []
                sources = list(self.clipboard_paths) if self.clipboard_paths else get_macos_clipboard_files()
                self._perform_paste(sources, allow_replace=True)
                return True
            elif key in ("n", "N"):
                # Aktuelle Datei überspringen
                self.conflict_resolution[dest] = "skip"
                self.conflicts_to_resolve.pop(0)
                if not self.conflicts_to_resolve:
                    # Alle Konflikte aufgelöst - Einfügen durchführen
                    sources = list(self.clipboard_paths) if self.clipboard_paths else get_macos_clipboard_files()
                    filtered_sources = []
                    for s in sources:
                        if not os.path.exists(s):
                            continue
                        name = os.path.basename(s)
                        d = os.path.join(self.current_dir, name)
                        if d in self.conflict_resolution:
                            if self.conflict_resolution[d] == "replace":
                                filtered_sources.append(s)
                        else:
                            filtered_sources.append(s)
                    self._perform_paste(filtered_sources, allow_replace=True)
                return True
            else:
                # Abbrechen
                self.active_dialog = None
                self.conflicts_to_resolve = []
                self.conflict_resolution = {}
                self.set_status("Einfügen abgebrochen", "warning")
                return True

        if self.active_dialog == "replace_confirm":
            pr = self.pending_replace
            if not pr:
                self.active_dialog = None
                return True
            if key in ("y", "Y"):
                # Ersetzen bestätigen und ausführen
                self.active_dialog = None
                self.pending_replace = None
                self._perform_replace(pr)
            else:
                # n und jede andere Taste: Ersetzen abbrechen
                self.active_dialog = None
                self.pending_replace = None
                self.set_status("Ersetzen abgebrochen", "warning")
            return True

        if self.active_dialog == "goto_menu":
            c = key.lower()
            self.active_dialog = None
            if c == "d":
                self.change_directory(os.path.expanduser("~/Downloads"))
                self.set_status("Downloads", "info")
            elif c == "f":
                self.change_directory(os.path.expanduser("~/Documents"))
                self.set_status("Dokumente", "info")
            elif c in ("-", "_"):
                target = self.marked_dir or self.last_visited_dir
                if target and os.path.isdir(target):
                    self.change_directory(target)
                    quelle = "gemerkten" if self.marked_dir else "zuletzt verwendeten"
                    self.set_status(f"Gehe zu {quelle} Ordner: {self.get_short_dir(target)}", "info")
                else:
                    self.set_status("Kein gemerkter oder zuletzt verwendeter Ordner verfügbar", "warning")
            elif c in ("h", "~"):
                self.change_directory(HOME_DIR)
                self.set_status("Home (~)", "info")
            elif c == "t":
                trash_p = os.path.expanduser("~/.Trash")
                if os.path.isdir(trash_p):
                    self.change_directory(trash_p)
                    self.set_status("Papierkorb", "info")
                else:
                    self.set_status("Papierkorb nicht verfügbar", "error")
            elif c == "i":
                self.active_dialog = "goto_path"
                self.dialog_input = ""
                self.dialog_cursor = 0
            elif c == "p":
                c_files = get_macos_clipboard_files()
                target = c_files[0] if c_files else ""
                if not target:
                    try:
                        target = subprocess.check_output(["pbpaste"], text=True).strip()
                    except Exception:
                        pass
                target = os.path.expanduser(target)
                if os.path.isdir(target):
                    self.change_directory(target)
                    self.set_status(f"Gehe zu: {self.get_short_dir(target)}", "info")
                elif os.path.isfile(target):
                    self.change_directory(os.path.dirname(target))
                    self.select_filename(os.path.basename(target))
                    self.set_status(f"Gehe zu: {self.get_short_dir(target)}", "info")
                else:
                    self.set_status("Kein gültiger Pfad im Zwischenspeicher", "warning")
            return True

        if key == "ENTER":
            val = self.dialog_input.strip()
            mode = self.active_dialog
            target_it = self.dialog_target_item
            self.active_dialog = None
            self.dialog_input = ""
            self.dialog_cursor = 0
            self.dialog_target_item = None

            if mode == "rename" and target_it:
                if not val or val == target_it.name:
                    self.set_status("Umbenennen abgebrochen")
                    return True
                new_path = os.path.join(self.current_dir, val)
                # Auf case-insensitiven Dateisystemen (macOS) ist der neue Name
                # scheinbar "vorhanden", obwohl es dieselbe Datei ist (z. B. nur
                # Gross/Kleinschreibung geaendert). os.path.samefile prueft die
                # Datei-Identitaet (Inode) statt des Pfadtexts und erkennt auch
                # reine Case-Renames. Ersetzungs-Dialog nur bei einer ANDEREN Datei.
                same_file = os.path.exists(new_path) and os.path.samefile(new_path, target_it.path)
                if os.path.exists(new_path) and not same_file:
                    # Vorhandenen Eintrag ersetzen? (gleiche Bestätigung wie beim Einfügen)
                    self.active_dialog = "replace_confirm"
                    self.pending_replace = {"mode": "rename", "src": target_it.path, "dest": new_path, "name": val}
                    return True
                try:
                    os.rename(target_it.path, new_path)
                    desc = f"Umbenennen von {target_it.name} in {val}"
                    self.undo_stack.append(UndoAction("rename", desc, {"old_path": target_it.path, "new_path": new_path}))
                    self.refresh_items(force=True)
                    self.select_filename(val)
                    self.set_status(f"Umbenannt in: {val} (u = Rückgängig)", "success")
                except Exception as e:
                    self.set_status(f"Fehler beim Umbenennen: {e}", "error")
                return True

            elif mode == "new":
                if not val:
                    self.set_status("Erstellung abgebrochen")
                    return True
                is_dir_target = val.endswith("/")
                clean_name = val.rstrip("/")
                target_p = os.path.join(self.current_dir, clean_name)
                if os.path.exists(target_p):
                    # Vorhandenen Eintrag ersetzen? (gleiche Bestätigung wie beim Einfügen)
                    self.active_dialog = "replace_confirm"
                    self.pending_replace = {"mode": "new", "src": None, "dest": target_p, "name": clean_name, "is_dir_target": is_dir_target}
                    return True
                try:
                    if is_dir_target:
                        os.makedirs(target_p, exist_ok=True)
                        # Regel: Sind aktuell Dateien markiert (nur '*', ohne aktive
                        # Kopieren/Ausschneiden-Vormerkung), wandern diese nach dem
                        # Erstellen in den neuen Ordner. Nur bei Ordnern ('/' am Ende).
                        move_sel = list(self.selected_paths) if self.selected_paths and not (self.clipboard_mode or self.clipboard_paths) else []
                        if move_sel:
                            moved = []
                            move_errors = []
                            for src_p in move_sel:
                                if os.path.exists(src_p):
                                    try:
                                        shutil.move(src_p, os.path.join(target_p, os.path.basename(src_p)))
                                        moved.append((src_p, os.path.join(target_p, os.path.basename(src_p))))
                                    except Exception as me:
                                        move_errors.append(os.path.basename(src_p))
                            if moved:
                                self.selected_paths.clear()
                                self.undo_stack.append(UndoAction(
                                    "create",
                                    f"Erstellen von {clean_name} mit {len(moved)} verschobenen Elementen",
                                    {"path": target_p, "moved_records": moved},
                                ))
                                if move_errors:
                                    self.set_status(f"Ordner erstellt: {clean_name}; {len(moved)} verschoben, Fehler bei: {', '.join(move_errors[:3])}", "warning")
                                else:
                                    self.set_status(f"Ordner erstellt: {clean_name} — {len(moved)} Element(e) verschoben (u = Rückgängig)", "success")
                            else:
                                self.undo_stack.append(UndoAction("create", f"Erstellen von {clean_name}", {"path": target_p}))
                                self.set_status(f"Ordner erstellt: {clean_name} (u = Rückgängig)", "success")
                        else:
                            self.undo_stack.append(UndoAction("create", f"Erstellen von {clean_name}", {"path": target_p}))
                            self.set_status(f"Ordner erstellt: {clean_name} (u = Rückgängig)", "success")
                    else:
                        open(target_p, "a").close()
                        self.set_status(f"Datei erstellt: {clean_name} (u = Rückgängig)", "success")
                        self.undo_stack.append(UndoAction("create", f"Erstellen von {clean_name}", {"path": target_p}))
                    self.refresh_items(force=True)
                    self.select_filename(clean_name)
                except Exception as e:
                    self.set_status(f"Fehler: {e}", "error")
                return True

            elif mode == "goto_path":
                if not val:
                    self.set_status("Pfad-Navigation abgebrochen")
                    return True
                target = os.path.expanduser(val)
                if not os.path.isabs(target):
                    target = os.path.join(self.current_dir, target)
                target = os.path.abspath(target)
                if os.path.isdir(target):
                    self.change_directory(target)
                    self.set_status(f"Gehe zu: {self.get_short_dir(target)}", "info")
                elif os.path.isfile(target):
                    self.change_directory(os.path.dirname(target))
                    self.select_filename(os.path.basename(target))
                    self.set_status(f"Gehe zu: {self.get_short_dir(target)}", "info")
                else:
                    self.set_status(f"Pfad nicht gefunden: {val}", "error")
                return True

            elif mode == "search":
                self.filter_query = val
                self.refresh_items(force=True)
                self.set_status(f"Filter aktiv: „{val}“ ({len(self.items)} Treffer)" if val else "Filter aufgehoben", "info")
                return True

            return True

        if key == "BACKSPACE":
            if self.dialog_cursor > 0:
                self.dialog_input = self.dialog_input[:self.dialog_cursor - 1] + self.dialog_input[self.dialog_cursor:]
                self.dialog_cursor -= 1
                if self.active_dialog == "search":
                    self.filter_query = self.dialog_input
                    self.refresh_items(force=True)
            return True

        if key == "DELETE":
            if self.dialog_cursor < len(self.dialog_input):
                self.dialog_input = self.dialog_input[:self.dialog_cursor] + self.dialog_input[self.dialog_cursor + 1:]
                if self.active_dialog == "search":
                    self.filter_query = self.dialog_input
                    self.refresh_items(force=True)
            return True

        if key == "LEFT":
            self.dialog_cursor = max(0, self.dialog_cursor - 1)
            return True

        if key == "RIGHT":
            self.dialog_cursor = min(len(self.dialog_input), self.dialog_cursor + 1)
            return True

        if key in ("HOME", "\x01"):
            self.dialog_cursor = 0
            return True

        if key in ("END", "\x05"):
            self.dialog_cursor = len(self.dialog_input)
            return True

        if key in ("SPACE", " "):
            self.dialog_input = self.dialog_input[:self.dialog_cursor] + " " + self.dialog_input[self.dialog_cursor:]
            self.dialog_cursor += 1
            if self.active_dialog == "search":
                self.filter_query = self.dialog_input
                self.refresh_items(force=True)
            return True

        if len(key) == 1 and key.isprintable():
            self.dialog_input = self.dialog_input[:self.dialog_cursor] + key + self.dialog_input[self.dialog_cursor:]
            self.dialog_cursor += 1
            if self.active_dialog == "search":
                self.filter_query = self.dialog_input
                self.refresh_items(force=True)
            return True

        return True
