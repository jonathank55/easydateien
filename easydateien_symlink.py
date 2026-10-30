"""Kernfunktion zum Erstellen von symbolischen Verknuepfungen (isoliert testbar)."""
import os


class SymlinkError(Exception):
    """Fehler beim Erstellen einer Verknuepfung."""


def create_symlink(target: str, link_path: str, overwrite: bool = False) -> str:
    """Erstellt eine symbolische Verknuepfung `link_path` -> `target`.

    Rueckgabe: der tatsaechlich verwendete (absolute) Linkpfad.

    Regeln:
    - Ziel wird immer als absoluter Pfad im Link hinterlegt (portabel, robust).
    - Existiert link_path bereits:
        - overwrite=False -> SymlinkError("exists")
        - overwrite=True  -> nur wenn bestehender Eintrag selbst ein Symlink ist,
                             wird er ersetzt; Dateien/Ordner werden nie geloescht.
    - Ziel muss existieren (sonst SymlinkError("target_missing")).
    - Linkverzeichnis muss existieren (sonst SymlinkError("dir_missing")).
    - Name darf keine Pfadtrenner enthalten (sonst SymlinkError("bad_name")).
    """
    if not target:
        raise SymlinkError("empty_target")
    if not link_path or not link_path.strip():
        raise SymlinkError("empty_link")
    # Rohname vor jeglicher Pfadaufloesung pruefen: Der letzte Bestandteil
    # (ohne abschliessenden Slash) darf kein Trenner und kein Sondername sein.
    raw_name = link_path.rstrip("/").rsplit("/", 1)[-1]
    if (not raw_name or raw_name in (".", "..") or "\x00" in raw_name):
        raise SymlinkError("bad_name")
    abs_link = os.path.abspath(link_path)
    link_dir = os.path.dirname(abs_link)
    if link_dir == abs_link:
        raise SymlinkError("bad_name")
    abs_target = os.path.abspath(os.path.expanduser(target))
    if not os.path.exists(abs_target):
        raise SymlinkError("target_missing")
    if not os.path.isdir(link_dir):
        raise SymlinkError("dir_missing")
    if os.path.lexists(abs_link):
        if not overwrite:
            raise SymlinkError("exists")
        if not os.path.islink(abs_link):
            raise SymlinkError("not_a_symlink")
        os.remove(abs_link)
    os.symlink(abs_target, abs_link)
    return abs_link


def remove_symlink(link_path: str) -> None:
    """Entfernt eine Verknuepfung (nur Symlinks, nie Dateien/Ordner)."""
    abs_link = os.path.abspath(link_path)
    if os.path.islink(abs_link):
        os.remove(abs_link)
