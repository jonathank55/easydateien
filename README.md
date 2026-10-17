# EasyDateien

**Minimalistischer, hocheffizienter Terminal-Dateimanager für macOS mit integrierter Konsole und flüssiger Tastaturnavigation.**

EasyDateien ist ein extrem schlanker, reaktionsschneller und autonomer Terminal-Dateimanager ohne externe Python-Abhängigkeiten. Er wurde entwickelt für Anwender, die blitzschnell im Terminal durch Verzeichnisse navigieren, Dateien auswählen, verschieben, kopieren, suchen, komprimieren oder in Editoren bearbeiten möchten, kombiniert mit einem vollintegrierten Terminal-Panel für maximale Produktivität.

> [!NOTE]
> **Transparenzhinweis zur Inspiration:**  
Ich schätze und liebe [Yazi](https://yazi-rs.github.io) sehr. Dieses Projekt ist stark von Yazi inspiriert, soll jedoch eine eigenständige, deutschsprachige, minimalistische und fokussierte Alternative mit integrierter Konsole bieten (und hat technisch nichts direkt mit Yazi zu tun).

- Offizielle Website von Yazi: [https://yazi-rs.github.io](https://yazi-rs.github.io)
- Yazi GitHub Repository: [https://github.com/sxyazi/yazi](https://github.com/sxyazi/yazi)

---

## Kernmerkmale

- **Integrierte Konsole & Terminal mit strikter Fokus-Isolation (`t`, `Tab`, `ESC`):**  
  EasyDateien besitzt ein vollintegriertes Terminal-Panel am unteren Rand (Position fest `unten`; die Höhe passt sich dynamisch an die Fenstergröße an — bis zu 30% der verfügbaren Höhe, mindestens 2 und höchstens 16 Zeilen):
  - **Strikte Fokus-Isolation:**  
    - **Konsole im Fokus (Statusleiste „Konsole“):** Sämtliche Tastenbelegungen des Dateimanagers sind strikt inaktiv. Alle Buchstaben und Zeichen (`u`, `z`, `d`, `q`, `r`, `y`, `x`, `p`, `e`, `o`, `m`, `s`, etc.) fließen ohne Kollision direkt in die Befehlszeile.
    - **Native Textauswahl & Kopieren:** Sobald die Konsole fokussiert ist, wird das Maus-Tracking automatisch freigegeben. Textausgaben, Pfade und Befehle können direkt mit der Maus markiert und per `Cmd+C` (oder Kontextmenü) in die Zwischenablage kopiert werden.
    - **`ESC`:** Entzieht der Konsole den Fokus (bei `Konsole immer eingeblendet` = Aus schließt `ESC` die Konsole stattdessen).
    - **`Tab`:** Wechselt den Fokus zurück zum Dateimanager.
    - **Konsole geöffnet, aber nicht im Fokus:** Sämtliche Tastenkürzel des Dateimanagers sind aktiv; es wird nichts versehentlich in die Konsole eingetippt. `Tab` setzt den Fokus zurück in die Konsole.    - **Hilfeleiste (Statusleiste unten):** Zeigt `[←↑↓→] Navigieren`, `[h] Hilfe`, `[m] Menü`, `[q] Beenden` sowie kontextabhängig `[t] Konsole` (wenn die Konsole nicht dauerhaft eingeblendet ist) bzw. `[Tab] Fokus` (wenn `Konsole immer eingeblendet` = Ein, da `t` dann wirkungslos ist).
  - **Zwei-Wege-Verzeichnissynchronisation:** Das Terminal operiert immer im aktuellen Verzeichnis des Dateimanagers. Navigiert man im Dateimanager, folgt das Terminal automatisch. Wechselt man im Terminal mit `cd ..` das Verzeichnis, folgt der Dateimanager sofort!
  - **Automatische Dateilisten-Aktualisierung:** Sobald im Terminal Befehle wie `touch datei.txt`, `mkdir ordner`, `git checkout` oder `rm bild.png` ausgeführt werden, aktualisiert der Dateimanager die Ansicht unverzüglich. Auch Änderungen von außen (z. B. laufende Downloads) werden selbstständig erkannt.
  - **Voller Terminalkomfort:** Befehlsverlauf (`↑`/`↓`), Zeilennavigation (`Pos1`/`Ende`, `Ctrl+A`/`Ctrl+E`, `Ctrl+W` zum Wortlöschen, `Ctrl+U`/`Ctrl+K` zum Zeilenlöschen mit Zwischenablage, `Ctrl+Y` zum Einfügen, `Ctrl+L` zum Leeren), Bildlauf (`BildAuf`/`BildAb` oder Mausrad) und Schließen per `exit`, `quit` oder `Ctrl+D`.
  - **Interaktive Vollbild-Programme:** Anwendungen wie `nano`, `vim`, `htop` oder `zsh` (sowie u. a. `ssh`, `less`, `python`, interaktive `git`-Befehle) werden automatisch erkannt, sauber im Vollbild ausgeführt und kehren ohne Bildartefakte zurück.
  - **Befehlsausführung:** Alle anderen Befehle laufen in der Login-Shell des Benutzers (`$SHELL`) im aktuellen Ordner; ihre Ausgabe streamt live ins Konsolenpanel (es gibt kein hartes Zeitlimit; `Strg+C` beendet laufende Befehle). `cd`, `clear`, `exit` und `quit` werden intern behandelt.

- **Elegantes Kasten-Design & vollständige Fensterfüllung:**  
  Präziser Kastenaufbau mit echten abgerundeten Ecken (`╭`, `╮`, `╰`, `╯`) und Spaltentrennlinien (`┬`, `┴`, `│`), der sich nahtlos über die gesamte Terminalbreite und -höhe erstreckt. Durch die Nutzung des Alternate-Screen-Buffers (`\033[?1049h`) und strikte Zeilenbudgetierung ist ein Verrutschen oder Scrollen des Terminalfensters technisch ausgeschlossen.
  - Trennlinien (Rahmen und Spaltenlinien) sind immer vollständig aktiviert; ein Stil-Menü gibt es nicht.

- **Volladaptive Größenanpassung (Window-Resize in Echtzeit):**  
  Reagiert unverzüglich auf jede Veränderung der Terminalfenstergröße (`SIGWINCH`). Sämtliche Spaltenbreiten, Kastenränder und Statusangaben werden in Echtzeit berechnet. Zu lange Datei- und Ordnernamen werden dynamisch berechnet und am Ende sauber mit `…` abgeschnitten — kein Zeilenumbruch, kein Bildschirmflackern.

- **Dynamische Spaltenanzahl (Miller-Columns nach Yazi-Vorbild):**  
  - **Breite Fenster (ab 40 Zeichen):** 3 Spalten (Eltern-Ordner links + Aktueller Ordner mittig + Kindordner bzw. Datei-Details & Vorschau rechts)  
  - **Schmale Fenster (24–39 Zeichen):** 2 Spalten (Eltern-Ordner links + Aktueller Ordner rechts)  
  - **Sehr schmale Fenster (unter 24 Zeichen):** 1 Spalte (Fokus auf aktuellen Ordner)  
  - Die Spaltenanzahl ist fest an die Fensterbreite gekoppelt (Miller-Columns, stets aktiviert); sie kann nicht manuell umgeschaltet werden.

- **Vollständige Mausnavigation & Scrollen:**  
  - **Mausrad nach oben / unten:** Bewegt den Cursor in der Dateiliste (bzw. scrollt die Konsolenausgabe, wenn der Mauszeiger über der Konsole steht oder die Konsole fokussiert ist)  
  - **Linksklick:** Element auswählen; Doppelklick öffnet es mit dem konfigurierten Opener (Standard `open`: Dateien in der Standard-App, Ordner im Finder)  
  - **Klick auf linke Spalte:** Sofortiges Zurückwechseln in den übergeordneten Ordner  
  - **Klick auf rechte Spalte:** Ordner betreten bzw. Datei im Standardprogramm öffnen  
  - **Klick in Konsolenbereich:** Setzt den Fokus direkt auf die Konsole (Mausauswahl sofort aktiv)  
  - **Rechtsklick:** Element markieren bzw. Markierung umschalten (`*`)  
  - Im Konfigurationsmenü über `Mausunterstützung: [Ein / Aus]` jederzeit anpassbar.

- **Umfassende Dateioperationen & Undo-System:**  
  - **Suchen & Schnellfilter (`/`):** Interaktiver Live-Filter für die Dateiliste.  
  - **Neu erstellen (`n`):** Neue Dateien oder Verzeichnisse anlegen (Ordner mit `/` am Ende).  
  - **Umbenennen (`r`):** Inline-Umbenennen mit Sofort-Feedback.  
  - **Papierkorb (`Entfernen` oder `Rücktaste`):** Sicheres Verschieben in den macOS-Papierkorb (`~/.Trash`) mit Sicherheitsabfrage.  
  - **Rückgängig (`u`):** Mehrstufiges Undo-System für Erstellen, Umbenennen, Löschen, Einfügen sowie ZIP-Erstellen und -Entpacken.  
  - **ZIP-Komprimierung (`z`):** Ausgewählte Dateien und Ordner direkt als ZIP-Archiv komprimieren; der Cursor springt auf das neue Archiv.  
  - **ZIP-Entpacken (`e`):** Markierte bzw. ausgewählte ZIP-Archive in einen neuen Ordner entpacken.  
  - **Editor-Integration (`o`):** Dateien im konfigurierten Texteditor bearbeiten (Standard `nano`; im Konfigurationsmenü wählbar).  
  - **Systemweites Öffnen (`Enter`):** Öffnet Dateien mit der macOS-Standard-App oder Ordner direkt im Finder (Befehl über `opener` konfigurierbar).  

- **Details & Vorschau (rechte Spalte):**  
  Bei Dateien zeigt die rechte Spalte Typ, Größe, Datum und Rechte (bei Symlinks zusätzlich das Ziel) sowie – bei ausreichender Fensterhöhe – eine Textvorschau bzw. den Inhalt von ZIP-Archiven. Bei Ordnern wird deren Inhalt angezeigt. Symlinks erscheinen als `name @ ziel`.

- **Auswahldarstellung & macOS-Systemzwischenablage:**  
  - Auswahl: `*` vor dem Namen; der aktuell ausgewählte Eintrag (Cursor) wird invertiert hervorgehoben  
  - Ausschneiden (Cut): `×` (z. B. `  ×datei.txt`)  
  - Kopieren: Kurzzeitiges Feedback `+` (fett, ca. 1 Sekunde nach dem Kopieren; Vorrang vor `*`; kehrt danach automatisch zum vorherigen Zustand zurück)  
  - `Space`: Datei oder Ordner markieren / abwählen (`*`)  
  - `a`: Alle sichtbaren Dateien auf einmal markieren oder abwählen  
  - `x`: Auswahl (oder der Eintrag unter dem Cursor) zum **Ausschneiden** vormerken (`×`); erneutes `x` auf einer ausgeschnittenen Datei nimmt die Vormerkung zurück  
  - `c`: **Kopier-Menü** öffnen (invertiertes Menü wie bei `g`/`h`):  
    - `c` im Menü: Markierte Dateien zum **Kopieren** vormerken. **Echte macOS-Systemzwischenablage-Integration:** Dateien werden als native macOS-Dateireferenzen (`NSFilenamesPboardType` / `public.file-url`) registriert und können sofort systemweit im Finder (Cmd+V), in Mail, WhatsApp, Slack oder Notizen eingefügt werden! Die Auswahl bleibt dabei erhalten.  
    - `p` im Menü: Absoluten Dateipfad des Eintrags unter dem Cursor als Text in die Zwischenablage kopieren  
    - `f` im Menü: Dateinamen in die Zwischenablage kopieren  
    - `d` im Menü: Ordnerpfad in die Zwischenablage kopieren    - `v`: **Verknüpfung erstellen** — öffnet einen Eingabedialog für den Link-Namen; leer lassen für den automatischen Vorschlag `<Zielname> - Link`. Die Verknüpfung zeigt auf die Auswahl (ein einzelnes Element) bzw. den Eintrag unter dem Cursor und wird im aktuellen Ordner erstellt (bei Namenskollision automatisch `<Name> (1)`, `<Name> (2)`, …). Rückgängig mit `u`.    - `p`: Vormerkung im aktuellen Verzeichnis **einfügen** (erkennt auch im Finder kopierte Dateien). Existiert der Name bereits, erscheint eine Rückfrage (`y` ersetzen, `n` überspringen, `a` alle ersetzen; bei Kopien erhalten Duplikate bei Bedarf eine Nummerierung `(1)`).  

- **Gehe-zu-Schnellnavigation (`g`):**  
  - `g d`: Downloads (`~/Downloads`)  
  - `g f`: Dokumente (`~/Documents`)  
  - `g -`: Gemerkter Ordner — zuvor mit `-` gemerkt und gültig, bis ein neuer Ordner mit `-` gemerkt wird. Ohne gemerkten Ordner springt `g -` zum zuletzt verwendeten Ordner (der Ordner der letzten Aktion, z. B. Auswahl, Kopieren, Ausschneiden, Einfügen, ZIP, Entpacken, Konsole; reine Navigation zählt nicht)  
- **Schnellstartmenü (`i`):** Apps und Befehle per Tastendruck starten (Safari, iMessage, VPN-Profile u. a.; Einträge sind als `[1]`, `[2]`, … nummeriert; Pfeiltasten navigieren, `Enter` führt aus, Ziffern `1`–`9` wählen direkt, `ESC`/`q` schließt, in Untermenüs geht `ESC` eine Ebene zurück). Einträge — auch verschachtelte Untermenüs — werden zentral in der Konfiguration (`schnellstart_eintraege`) verwaltet und im Konfigurator (`m` → Schnellstart-Einträge) hinzugefügt, gelöscht oder auf Standard zurückgesetzt. GUI-Befehle (`open -a`, `osascript`) starten entkoppelt; CLI-Befehle laufen in der integrierten Konsole.
  - `g h` / `~`: Benutzerordner (`~`)  
  - `g t`: Papierkorb (`~/.Trash`)  
  - `g i`: Pfad manuell eingeben  
  - `g p`: Zu Pfad aus Zwischenablage springen  

- **Interaktives Konfigurationsmenü (`m`):**  
  Interaktiver Konfigurator (Navigation mit `↑`/`↓`, Ändern mit `Enter`/`Space`/`←`/`→`, Zurück mit `ESC`/`q`; Änderungen werden sofort gespeichert):
  - Mausunterstützung (`Ein` / `Aus`)
  - Versteckte Dateien anzeigen (`Ein` / `Aus`)
  - Konsole immer eingeblendet (`Ein` / `Aus`)
  - Vorschau-Umbruch (`Ein` / `Aus`)
  - Datei- und Ordneranordnung (Untermenü): Sortierkriterium (Name, Änderungsdatum, Zugangsdatum, Größe, Endung), Sortierreihenfolge, Ordnerposition
  - Editor für die Taste `o` (`nano`, `vim`, `nvim`, `micro`, `hx`, `emacs -nw`)
  - Tastenbelegungen (Untermenü zum Ansehen und Bearbeiten)
  - Schnellstart-Einträge (Untermenü zum Hinzufügen, Löschen und Zurücksetzen)
  - Auf Standardwerte zurücksetzen

> [!NOTE]
> **Tastenbelegungen:** Der Dateimanager lädt die Belegungen aus der Konfigurationsdatei (Single Source of Truth). Im Menü gespeicherte, abweichende Belegungen werden übernommen und wirken unmittelbar — auch nach einem Neustart. Tastenkonflikte werden beim Laden automatisch aufgelöst (u. a. fallen Doppelbelegungen auf den Standard der betroffenen Aktion zurück).

---

## Installation

### Option 1: Ein-Zeilen-Installation (ohne Klon)

Das Installationsskript kann direkt von GitHub ausgeführt werden — kein `git clone` nötig:

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/jonathank55/easydateien/main/install.sh)
```

Das Skript lädt die Programmdateien selbstständig von GitHub herunter und installiert sie fest nach `~/.config/easydateien/`. Ein Repository-Ordner, der nach der Installation bestehen bleiben muss, entfällt bei dieser Variante.

### Option 2: Installation aus dem geklonten Repository

1. **Repository klonen:**
   ```bash
   git clone https://github.com/jonathank55/easydateien.git
   cd easydateien
   ```

2. **Installationsskript ausführen:**
   ```bash
   chmod +x install.sh easydateien
   ./install.sh
   ```

Das Skript

- installiert die Programmdateien (`easydateien`, `easydateien_ui.py`, `easydateien_actions.py`, `easydateien_view.py`, `easydateien_common.py`, `easydateien_symlink.py`, `easydateien_konfigurator.py`) nach `~/.config/easydateien/` (bei Option 1 fest kopiert, bei Option 2 als Symlinks auf das Repository),
- kompiliert (sofern `clang` vorhanden ist) das native macOS-Clipboard-Modul `easydateien_clip` nach `~/.config/easydateien/`,
- legt `~/.config/easydateien/config.json` an, falls noch keine Konfiguration existiert (eine vorhandene gültige bleibt unberührt; eine korrupte wird durch gültige Standardwerte ersetzt),
- erstellt die Symlinks `easydateien` und `ed` in `~/.local/bin/` und/oder `~/bin/` (je nachdem, welches Verzeichnis existiert; `~/.local/bin/` wird bei Bedarf angelegt und sollte im `PATH` liegen),
- entfernt tote Symlinks und verwaiste Altreste (`config.example.json`) aus früheren Installationen,
- prüft am Ende die Installation (Dateien vorhanden, gültige Python-Syntax, Module importierbar, gültige `config.json`) und bricht bei Fehlern laut ab.

> [!NOTE]
> Bei der Installation aus dem geklonten Repository (Option 2) werden die Programmdateien in `~/.config/easydateien/` als Symlinks auf das Repository angelegt — der Repository-Ordner muss daher nach der Installation bestehen bleiben. Bei der Ein-Zeilen-Installation (Option 1) werden die Dateien dagegen fest nach `~/.config/easydateien/` kopiert; ein Repository-Ordner ist nicht nötig.

### Voraussetzungen

- macOS mit Python 3 (nur Standardbibliothek, keine externen Python-Abhängigkeiten)
- Optional: `clang` (Xcode Command Line Tools) für das native Clipboard-Modul (wird bei Bedarf auch beim ersten Start kompiliert); ohne `clang` nutzt EasyDateien AppleScript zum Kopieren und `pbpaste` zum Einfügen
- Ein UTF-8-fähiges Terminal mit ANSI-/SGR-Maus-Unterstützung

---

## Verwendung

Starten Sie EasyDateien einfach im aktuellen Verzeichnis:

```bash
easydateien
```

Oder über das praktische Kurzkürzel:

```bash
ed
```

Sie können auch direkt ein bestimmtes Verzeichnis öffnen:

```bash
ed ~/Downloads
```

### Konfigurationsmenü aufrufen

Innerhalb des Programms genügt das Drücken der Taste `m`. Alternativ kann der Konfigurator direkt über das Terminal gestartet werden:

```bash
easydateien --config
```

### Kommandozeilenoptionen

| Option | Funktion |
| :--- | :--- |
| `pfad` | Startverzeichnis (optional; Standard: aktuelles Verzeichnis) |
| `-c`, `--config` | Konfigurationsmenü öffnen |
| `-v`, `--version` | Programmversion anzeigen |
| `-h` | Hilfe anzeigen |

---

## Konfigurationsdatei (`~/.config/easydateien/config.json`)

Die Konfiguration wird im standardisierten JSON-Format gespeichert. Fehlende Schlüssel werden mit den hier gezeigten Standardwerten ergänzt (Vorlage: `DEFAULT_CONFIG` in [`easydateien_common.py`](easydateien_common.py); das Installationsskript erzeugt daraus bei Bedarf die Datei, eine korrupte `config.json` wird automatisch durch gültige Standardwerte ersetzt):

```json
{
  "esc_to_quit": false,
  "mouse_support": false,
  "show_console": false,
  "console_always_visible": true,
  "preview_wrap": true,
  "text_editor": "nano %s",
  "opener": "open %s",
  "sort_by": "name",
  "sort_reverse": true,
  "sort_dir_first": true,
  "show_hidden": false,
  "schnellstart_eintraege": [ /* ... Standard-Einträge, siehe DEFAULT_CONFIG ... */ ]
}
```

| Schlüssel | Standard | Bedeutung |
| :--- | :--- | :--- |
| `esc_to_quit` | `false` | Reserviert; wird von der aktuellen Version nicht ausgewertet (Beenden: `q`) |
| `mouse_support` | `false` | Mausunterstützung ein/aus |
| `show_console` | `false` | Integrierte Konsole beim Start geöffnet |
| `console_always_visible` | `true` | Konsole ist immer eingeblendet (kann dann nicht geschlossen werden) |
| `preview_wrap` | `true` | Lange Vorschauzeilen werden umgebrochen (statt abgeschnitten) |
| `text_editor` | `"nano %s"` | Editor für `o`; `%s` steht für den Dateipfad (im Menü wählbar: `nano`, `vim`, `nvim`, `micro`, `hx`, `emacs -nw`) |
| `opener` | `"open %s"` | Befehl für `Enter` und Doppelklick |
| `sort_by` | `"name"` | Sortierung: `name`, `mtime` (Änderungsdatum), `atime` (Zugangsdatum), `size` (Größe), `ext` (Endung/Typ) |
| `sort_reverse` | `true` | Bei Datum, Zugangsdatum und Größe: Neueste bzw. größte zuerst (Name und Endung immer aufsteigend A–Z) |
| `sort_dir_first` | `true` | Ordner vor Dateien anzeigen |
| `show_hidden` | `false` | Versteckte Dateien anzeigen |
| `schnellstart_eintraege` | (Liste) | Einträge des Schnellstartmenüs (`i`); verschachtelte Untermenüs über `untermenu` |
| `keybindings` | – | Optional; vom Tastenbelegungs-Editor des Konfigurators geschriebene Belegungsliste |

Das Konfigurationsmenü speichert Änderungen sofort. Die Tasten `.` (versteckte Dateien) und `s` (Sortierung) wirken dagegen nur für die laufende Sitzung.

---

## Code-Struktur (Modulares Design)

Der Dateimanager ist in klar getrennte Module zerlegt; die Logik ist dabei unverändert:

| Datei | Rolle |
| :--- | :--- |
| `easydateien` | Einstiegspunkt: Kern (`__init__`, Hauptschleife `run`), komponiert die App aus den Mixins |
| `easydateien_ui.py` | Konstanten, Terminal-/Tastatur-Helfer, reine Rendering-Funktionen |
| `easydateien_actions.py` | Alle Methoden mit Seiteneffekten: Dateioperationen, Navigation, Konsole, Dialoge, Maus |
| `easydateien_view.py` | Bildschirmaufbau (`build_screen`, Statusleiste) |
| `easydateien_common.py` | Zentrale Tastenbelegungen (Single Source of Truth), Konfiguration, gemeinsame Helfer |
| `easydateien_symlink.py` | Kernfunktion zum Erstellen/Entfernen symbolischer Verknüpfungen (isoliert testbar) |
| `easydateien_konfigurator.py` | Einstellungsmenü (eigenständig lauffähig) |
| `test_eazydateien_kern.py` | Regressionstests der Kernfunktionen |
| `test_konsole.py` | Konsolen-Tests (Ausgabe, Verlauf, PTY-Echtests) |
| `test_terminal_reset.py` | Terminal-Reset-Regressionstests (termios nach Beenden bit-identisch, Reset-Sequenzen) |
| `test_rendering_golden.py` | Goldene Rendering-Tests: frieren das exakte Bildschirmverhalten ein; jede Refaktorierung muss die Hashes unverändert lassen |
| `test_symlink.py` | Verknüpfungs-Tests: Kernfunktion (Erstellen, Überschreiben, Fehlerfälle) und App-Integration (Dialog, Kollision, Undo) |
| `run_tests.py` | Test-Runner (alle Tests) |

## Tastatur-Referenz

### Dateimanager-Modus

| Taste | Aktion |
| :--- | :--- |
| `↑` | Cursor nach oben bewegen |
| `↓` | Cursor nach unten bewegen |
| `→` | In Verzeichnis wechseln |
| `←` | In übergeordneten Ordner wechseln |
| `Enter` | Element mit dem konfigurierten Opener öffnen (Standard `open`; Ordner öffnen im Finder) |
| `Space` | Aktuelle Datei markieren / Markierung aufheben (`*`); der Cursor rückt eine Zeile weiter |
| `a` | Alle sichtbaren Elemente markieren bzw. Auswahl aufheben |
| `n` | Neue Datei oder neuen Ordner erstellen (Ordner mit `/` am Ende). Sind Dateien markiert (`*`, ohne aktive Kopieren/Ausschneiden-Vormerkung) und es wird ein **Ordner** erstellt, wandern die markierten Dateien automatisch in den neuen Ordner |
| `r` | Datei / Ordner umbenennen |
| `/` | Such- und Schnellfilter aktivieren (Live-Filter nach Namensteil) |
| `s` | Sortierkriterium umschalten (Änderungsdatum, Name, Größe, Typ); gilt für die laufende Sitzung (über das Menü `m` ist zusätzlich Zugangsdatum wählbar) |
| `u` | Letzte Dateiaktion rückgängig machen (Erstellen, Umbenennen, Papierkorb, Einfügen, ZIP erstellen/entpacken, Verknüpfung erstellen) |
| `z` | ZIP-Archiv aus Auswahl (bzw. Eintrag unter dem Cursor) erstellen; der Cursor springt auf das neue Archiv |
| `e` | Markierte bzw. das ausgewählte ZIP-Archiv in jeweils einen neuen Ordner entpacken |
| `c` | Kopier-Menü öffnen: `c` = Auswahl in die macOS-Zwischenablage kopieren (Finder-kompatibel, Auswahl bleibt erhalten), `p` = absoluter Pfad, `f` = Dateiname, `d` = Ordnerpfad |
| `v` | Verknüpfung auf die Auswahl (ein Element) bzw. den Eintrag unter dem Cursor erstellen; Name eingeben (leer = automatischer Vorschlag `<Zielname> - Link`); rückgängig mit `u` |
| `x` | Auswahl ausschneiden (`×`-Markierung) |
| `p` | Zwischenablage im aktuellen Ordner einfügen |
| `Entfernen` / `Rücktaste` | In macOS-Papierkorb verschieben (Bestätigung mit `y` oder `Enter`, alles andere bricht ab) |
| `o` | Datei im konfigurierten Texteditor bearbeiten (Standard `nano`, im Menü `m` änderbar) |
| `.` | Versteckte Dateien ein- oder ausblenden; gilt für die laufende Sitzung |
| `g` | Gehe-zu-Menü öffnen (`d` Downloads, `f` Dokumente, `-` gemerkter Ordner, `h`/`~` Home, `t` Papierkorb, `i` Pfadeingabe, `p` Zwischenablage) |
| `-` | Aktuellen Ordner merken; `g-` springt immer dorthin (bis ein neuer Ordner mit `-` gemerkt wird). Ohne gemerkten Ordner springt `g-` zum zuletzt verwendeten Ordner (letzter Ordner mit einer Aktion wie Auswahl, Kopieren, Ausschneiden, Einfügen, ZIP, Entpacken, Konsole oder Rückgängig; reine Navigation zählt nicht) |
| `~` | Direkt zum Benutzerordner (`~`) springen |
| `j` | An den Anfang der Dateiliste springen |
| `k` | An das Ende der Dateiliste springen |
| `BildAuf` / `BildAb` | Datei-Vorschau scrollen (wenn eine geöffnet ist und der Dateimanager fokussiert ist); in der Konsole: Konsolenverlauf scrollen |
| `t` | Integrierte Konsole öffnen / schließen |
| `Tab` | Fokus auf integrierte Konsole setzen (oder Konsole öffnen) |
| `h` | Hilfe mit Tastenübersicht öffnen |
| `m` | Konfigurationsmenü öffnen |
| `ESC` | Konsole schließen, Filter aufheben, Auswahl aufheben, Ausschneiden-Vormerkung aufheben (in dieser Reihenfolge) |
| `Strg C` | Im Dateimanager-Modus: Filter aufheben, dann Auswahl aufheben, dann Ausschneiden-Vormerkung aufheben. In der Konsole: Eingabezeile leeren (`^C`); laufende Konsolen-Befehle werden per Signal beendet |
| `q` | EasyDateien beenden |

### Konsolen-Modus (Konsole im Fokus)

| Taste | Aktion |
| :--- | :--- |
| **Alle Zeichen** | Direkte Befehlseingabe (alle Dateimanager-Kürzel sind isoliert deaktiviert) |
| `Enter` | Eingegebenen Befehl im aktuellen Verzeichnis ausführen (`cd`, `clear`, `exit` / `quit` werden intern behandelt) |
| `Tab` | Fokus zurück auf Dateimanager wechseln |
| `ESC` | Fokus der Konsole entziehen (bei `Konsole immer eingeblendet` = Aus: Konsole schließen) |
| `↑` / `↓` | Befehlsverlauf durchblättern (ohne Verlauf: Ausgabe scrollen) |
| `←` / `→` | Cursor in der Befehlszeile nach links / rechts bewegen |
| `Pos1` / `Ctrl+A` | Cursor an den Anfang der Zeile setzen |
| `Ende` / `Ctrl+E` | Cursor an das Ende der Zeile setzen |
| `Backspace` | Zeichen vor dem Cursor löschen |
| `Delete` | Zeichen unter dem Cursor löschen |
| `Ctrl+W` | Vorheriges Wort löschen (landet in der macOS-Zwischenablage) |
| `Ctrl+U` | Zeile bis zum Cursor löschen (landet in der macOS-Zwischenablage) |
| `Ctrl+K` | Zeile ab Cursor bis zum Ende löschen (landet in der macOS-Zwischenablage) |
| `Ctrl+Y` | Text aus der macOS-Zwischenablage einfügen |
| `Ctrl+L` | Terminal-Ausgabepuffer leeren (`clear`) |
| `BildAuf` / `BildAb` (auch mit `Shift` / `Ctrl` / `Alt` + `↑` / `↓`) | Konsolenausgabe nach oben / unten scrollen |
| `Ctrl+D` | Zeichen unter dem Cursor löschen; bei leerer Eingabezeile Fokus der Konsole entziehen (bei `Konsole immer eingeblendet` = Aus: Konsole schließen) |

> [!NOTE]
> `Strg+C` wird von EasyDateien selbst behandelt: In der Konsole wird eine laufende Befehlsausgabe mit `Strg+C` beendet (erst `SIGINT`, dann `SIGKILL` — wie in einem echten Terminal) bzw. die Eingabezeile geleert (`^C`); interaktive Vollbild-Programme (z. B. `vim`) erhalten das Signal direkt. `Strg+C` beendet EasyDateien nicht. Zum Verwerfen einer Eingabezeile dient `Ctrl+U`.

---

## Maus-Referenz

Die Maus ist standardmäßig deaktiviert (`mouse_support: false`) und im Konfigurationsmenü einschaltbar. Solange die Konsole im Fokus ist, wird das Maus-Tracking automatisch freigegeben (native Textauswahl des Terminals).

| Maus-Aktion | Funktion |
| :--- | :--- |
| **Mausrad nach oben / unten** | Cursor in der Dateiliste bewegen bzw. Konsolenausgabe scrollen (über der Konsole) |
| **Linksklick auf Eintrag** | Element auswählen |
| **Doppelklick auf Eintrag** | Element mit dem konfigurierten Opener öffnen (Standard `open`: Dateien in der Standard-App, Ordner im Finder) |
| **Linksklick auf linke Spalte** | Zum übergeordneten Ordner zurückkehren |
| **Linksklick auf rechte Spalte** | Bei Ordnern: Ordner betreten und angeklickten Eintrag auswählen; bei Dateien: Datei mit dem Opener öffnen |
| **Linksklick in Konsolenbereich** | Fokus direkt auf die Konsole setzen (Klick außerhalb setzt den Fokus zurück auf den Dateimanager) |
| **Rechtsklick auf Eintrag** | Element-Auswahl umschalten (`*`) |

---

## Lizenz

Veröffentlicht unter der [MIT-Lizenz](LICENSE).  
Copyright (c) 2026 Jonathan Klatchko.
