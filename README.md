# EasyDateien

**Minimalistischer, hocheffizienter Terminal-Dateimanager für macOS mit integrierter Konsole und flüssiger Tastaturnavigation.**

EasyDateien ist ein extrem schlanker, reaktionsschneller und autonomer Terminal-Dateimanager ohne externe Python-Abhängigkeiten. Er wurde entwickelt für Anwender, die blitzschnell im Terminal durch Verzeichnisse navigieren, Dateien auswählen, verschieben, kopieren, suchen, komprimieren oder in Editoren bearbeiten möchten — kombiniert mit einem vollintegrierten Terminal-Panel für maximale Produktivität.

> [!NOTE]
> **Transparenzhinweis zur Inspiration:**  
> EasyDateien ist von der Tastatur- und Navigationsphilosophie moderner Terminal-Dateimanager wie **Yazi** inspiriert, wurde jedoch bewusst als eigenständiges, radikal vereinfachtes Werkzeug konzipiert. Es soll bewusst sehr viel einfacher, fokussierter und wartungsärmer sein. EasyDateien hat **keine offizielle Verbindung zum Yazi-Projekt** und teilt lediglich die Begeisterung für effiziente Tastaturnavigation im Terminal.

---

## Kernmerkmale

- **Integrierte Konsole & Terminal mit strikter Fokus-Isolation (`t`, `Tab`, `ESC`):**  
  EasyDateien besitzt ein vollintegriertes Terminal-Panel mit konfigurierbarer Position (`unten`, `rechts` oder `links`; Einstellung `console_position` in der Konfigurationsdatei, Standard `unten`; am unteren Rand ist das Panel 4 Zeilen hoch):
  - **Strikte Fokus-Isolation:**  
    - **Konsole im Fokus (Statusleiste „Konsole“):** Sämtliche Tastenbelegungen des Dateimanagers sind strikt inaktiv. Alle Buchstaben und Zeichen (`u`, `z`, `d`, `q`, `r`, `y`, `x`, `p`, `e`, `o`, `m`, `s`, etc.) fließen ohne Kollision direkt in die Befehlszeile.
    - **Native Textauswahl & Kopieren:** Sobald die Konsole fokussiert ist, wird das Maus-Tracking automatisch freigegeben. Textausgaben, Pfade und Befehle können direkt mit der Maus markiert und per `Cmd+C` (oder Kontextmenü) in die Zwischenablage kopiert werden.
    - **`ESC`:** Schließt die Konsole deterministisch.
    - **`Tab`:** Wechselt den Fokus zurück zum Dateimanager.
    - **Konsole geöffnet, aber nicht im Fokus:** Sämtliche Tastenkürzel des Dateimanagers sind aktiv; es wird nichts versehentlich in die Konsole eingetippt. `Tab` setzt den Fokus zurück in die Konsole.
  - **Zwei-Wege-Verzeichnissynchronisation:** Das Terminal operiert immer im aktuellen Verzeichnis des Dateimanagers. Navigiert man im Dateimanager, folgt das Terminal automatisch. Wechselt man im Terminal mit `cd ..` das Verzeichnis, folgt der Dateimanager sofort!
  - **Automatische Dateilisten-Aktualisierung:** Sobald im Terminal Befehle wie `touch datei.txt`, `mkdir ordner`, `git checkout` oder `rm bild.png` ausgeführt werden, aktualisiert der Dateimanager die Ansicht unverzüglich. Auch Änderungen von außen (z. B. laufende Downloads) werden selbstständig erkannt.
  - **Voller Terminalkomfort:** Befehlsverlauf (`↑`/`↓`), Zeilennavigation (`Pos1`/`Ende`, `Ctrl+A`/`Ctrl+E`, `Ctrl+W` zum Wortlöschen, `Ctrl+U`/`Ctrl+K` zum Zeilenlöschen mit Zwischenablage, `Ctrl+Y` zum Einfügen, `Ctrl+L` zum Leeren), Bildlauf (`BildAuf`/`BildAb` oder Mausrad) und Schließen per `exit`, `quit` oder `Ctrl+D`.
  - **Interaktive Vollbild-Programme:** Anwendungen wie `nano`, `vim`, `htop` oder `zsh` (sowie u. a. `ssh`, `less`, `python`, interaktive `git`-Befehle) werden automatisch erkannt, sauber im Vollbild ausgeführt und kehren ohne Bildartefakte zurück.
  - **Befehlsausführung:** Alle anderen Befehle laufen in der Login-Shell des Benutzers (`$SHELL`) im aktuellen Ordner; ihre Ausgabe erscheint im Konsolenpanel (Abbruch nach 60 Sekunden). `cd`, `clear`, `exit` und `quit` werden intern behandelt.

- **Elegantes Kasten-Design & vollständige Fensterfüllung:**  
  Präziser Kastenaufbau mit echten abgerundeten Ecken (`╭`, `╮`, `╰`, `╯`) und Spaltentrennlinien (`┬`, `┴`, `│`), der sich nahtlos über die gesamte Terminalbreite und -höhe erstreckt. Durch die Nutzung des Alternate-Screen-Buffers (`\033[?1049h`) und strikte Zeilenbudgetierung ist ein Verrutschen oder Scrollen des Terminalfensters technisch ausgeschlossen.
  - Trennlinienstile: `[Alle]`, `[Vertikal]`, `[Außen]`, `[Horizontal]` oder `[Keine]`.

- **Volladaptive Größenanpassung (Window-Resize in Echtzeit):**  
  Reagiert unverzüglich auf jede Veränderung der Terminalfenstergröße (`SIGWINCH`). Sämtliche Spaltenbreiten, Kastenränder und Statusangaben werden in Echtzeit berechnet. Zu lange Datei- und Ordnernamen werden dynamisch berechnet und am Ende sauber mit `…` abgeschnitten — kein Zeilenumbruch, kein Bildschirmflackern.

- **Dynamische Spaltenanzahl (Miller-Columns nach Yazi-Vorbild):**  
  - **Breite Fenster (>= 70 Zeichen):** 3 Spalten (Eltern-Ordner links + Aktueller Ordner mittig + Kindordner bzw. Datei-Details & Vorschau rechts)  
  - **Mittlere Fenster (40–69 Zeichen):** 2 Spalten (Eltern-Ordner links + Aktueller Ordner rechts)  
  - **Kompakte Fenster (< 40 Zeichen):** 1 Spalte (Fokus auf aktuellen Ordner)  
  - Die Spaltendarstellung kann über das Menü (`m`) jederzeit ein- oder ausgeschaltet werden.

- **Vollständige Mausnavigation & Scrollen:**  
  - **Mausrad nach oben / unten:** Flüssiges Scrollen durch die Dateiliste (bzw. Konsolenausgabe im Konsolenfokus)  
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
  - **Papierkorb (`d`):** Sicheres Verschieben in den macOS-Papierkorb (`~/.Trash`) mit Sicherheitsabfrage.  
  - **Rückgängig (`u`):** Mehrstufiges Undo-System für Erstellen, Umbenennen, Löschen, Einfügen sowie ZIP-Erstellen und -Entpacken.  
  - **ZIP-Komprimierung (`z`):** Ausgewählte Dateien und Ordner direkt als ZIP-Archiv komprimieren; der Cursor springt auf das neue Archiv.  
  - **ZIP-Entpacken (`e`):** Markierte bzw. ausgewählte ZIP-Archive in einen neuen Ordner entpacken.  
  - **Editor-Integration (`o`):** Dateien im konfigurierten Texteditor bearbeiten (Standard `nano`; im Konfigurationsmenü wählbar).  
  - **Systemweites Öffnen (`Enter`):** Öffnet Dateien mit der macOS-Standard-App oder Ordner direkt im Finder (Befehl über `opener` konfigurierbar).  

- **Details & Vorschau (rechte Spalte):**  
  Bei Dateien zeigt die rechte Spalte Typ, Größe, Datum und Rechte (bei Symlinks zusätzlich das Ziel) sowie – bei ausreichender Fensterhöhe – eine Textvorschau bzw. den Inhalt von ZIP-Archiven. Bei Ordnern wird deren Inhalt angezeigt. Symlinks erscheinen als `name @ ziel`.

- **Auswahldarstellung & macOS-Systemzwischenablage:**  
  - Auswahl: `*` (z. B. ` ▸*datei.txt`)  
  - Ausschneiden (Cut): `×` (z. B. `  ×datei.txt`)  
  - Kopieren: `+` (z. B. `  +datei.txt`)  
  - `Space`: Datei oder Ordner markieren / abwählen (`*`)  
  - `a`: Alle sichtbaren Dateien auf einmal markieren oder abwählen  
  - `x`: Markierte Dateien zum **Ausschneiden** vormerken (`×`)  
  - `c`: Markierte Dateien zum **Kopieren** vormerken. **Echte macOS-Systemzwischenablage-Integration:** Dateien werden als native macOS-Dateireferenzen (`NSFilenamesPboardType` / `public.file-url`) registriert und können sofort systemweit im Finder (Cmd+V), in Mail, WhatsApp, Slack oder Notizen eingefügt werden!  
  - `p`: Vormerkung im aktuellen Verzeichnis **einfügen** (erkennt auch im Finder kopierte Dateien). Existiert der Name bereits, erscheint eine Rückfrage (`y` ersetzen, `n` überspringen, `a` alle ersetzen; bei Kopien erhalten Duplikate bei Bedarf eine Nummerierung `(1)`).  
  - `c c`: Absoluten Dateipfad in die Zwischenablage kopieren  
  - `c f`: Dateinamen in die Zwischenablage kopieren  
  - `c d`: Ordnerpfad in die Zwischenablage kopieren  

- **Gehe-zu-Schnellnavigation (`g`):**  
  - `g d`: Downloads (`~/Downloads`)  
  - `g f`: Dokumente (`~/Documents`)  
  - `g -`: Gemerkter Ordner — zuvor mit `-` gemerkt und gültig, bis ein neuer Ordner mit `-` gemerkt wird. Ohne gemerkten Ordner springt `g -` zum zuletzt verwendeten Ordner (der Ordner der letzten Aktion, z. B. Auswahl, Kopieren, Ausschneiden, Einfügen, ZIP, Entpacken, Konsole; reine Navigation zählt nicht)  
  - `g h` / `~`: Benutzerordner (`~`)  
  - `g t`: Papierkorb (`~/.Trash`)  
  - `g i`: Pfad manuell eingeben  
  - `g p`: Zu Pfad aus Zwischenablage springen  

- **Interaktives Konfigurationsmenü (`m`):**  
  Interaktiver Konfigurator (Navigation mit `↑`/`↓`, Ändern mit `Enter`/`Space`/`←`/`→`, Zurück mit `ESC`/`q`; Änderungen werden sofort gespeichert):
  - Trennungslinien sind immer vollständig aktiviert (alle Rahmen- und Spaltenlinien)
  - Spalten-Layout (Miller-Columns, stets aktiviert)
  - Mausunterstützung (`Ein` / `Aus`)
  - Versteckte Dateien anzeigen (`Ein` / `Aus`)
  - Datei- und Ordneranordnung (Untermenü): Sortierkriterium, Sortierreihenfolge, Ordnerposition
  - Editor für die Taste `o` (`nano`, `vim`, `nvim`, `micro`, `hx`, `emacs -nw`)
  - Tastenbelegungen (Untermenü zum Ansehen und Bearbeiten)
  - Auf Standardwerte zurücksetzen (mit Sicherheitsabfrage)

> [!NOTE]
> **Tastenbelegungen:** Der Dateimanager verwendet derzeit die fest eingebauten Standardbelegungen aus der [Tastatur-Referenz](#tastatur-referenz). Im Menü gespeicherte, abweichende Belegungen werden in der Konfigurationsdatei abgelegt, aber von der Tastensteuerung noch nicht angewendet.

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

- verlinkt `easydateien` und `easydateien_konfigurator.py` nach `~/.config/easydateien/`,
- kompiliert (sofern `clang` vorhanden ist) das native macOS-Clipboard-Modul `easydateien_clip` nach `~/.config/easydateien/`,
- legt `~/.config/easydateien/config.json` aus [`config.json`](config.json) an, falls noch keine Konfiguration existiert (eine vorhandene bleibt unberührt),
- erstellt die Symlinks `easydateien` und `ed` in `~/.local/bin/` bzw. `~/bin/` (je nachdem, welches Verzeichnis existiert; `~/.local/bin/` wird bei Bedarf angelegt und sollte im `PATH` liegen).

> [!NOTE]
> Bei der Installation aus dem geklonten Repository (Option 2) muss der Repository-Ordner nach der Installation bestehen bleiben, da die Symlinks darauf zeigen. Bei der Ein-Zeilen-Installation (Option 1) entfällt diese Einschränkung, da die Dateien fest nach `~/.config/easydateien/` kopiert werden.

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

Die Konfiguration wird im standardisierten JSON-Format gespeichert. Fehlende Schlüssel werden mit den hier gezeigten Standardwerten ergänzt (Vorlage: [`config.json`](config.json)):

```json
{


  "esc_to_quit": false,
  "mouse_support": true,
  "show_console": false,
  "console_position": "unten",
  "text_editor": "nano %s",
  "opener": "open %s",
  "sort_by": "mtime",
  "sort_reverse": true,
  "sort_dir_first": true,
  "show_hidden": false
}
```

| Schlüssel | Standard | Bedeutung |
| :--- | :--- | :--- |


| `esc_to_quit` | `false` | Reserviert; wird von der aktuellen Version nicht ausgewertet (Beenden: `q`) |
| `mouse_support` | `true` | Mausunterstützung ein/aus |
| `show_console` | `false` | Integrierte Konsole beim Start geöffnet |
| `console_position` | `"unten"` | Position der Konsole: `unten`, `rechts`, `links` (bei Terminalbreite unter 60 Zeichen immer unten); nur in der Datei einstellbar, Konsolenhöhe unten: 4 Zeilen |
| `text_editor` | `"nano %s"` | Editor für `o`; `%s` steht für den Dateipfad (im Menü wählbar: `nano`, `vim`, `nvim`, `micro`, `hx`, `emacs -nw`) |
| `opener` | `"open %s"` | Befehl für `Enter` und Doppelklick |
| `sort_by` | `"mtime"` | Sortierung: `mtime` (Datum), `name`, `size` (Größe), `ext` (Typ) |
| `sort_reverse` | `true` | Bei Datum und Größe: Neueste bzw. größte zuerst (Name und Typ immer aufsteigend A–Z) |
| `sort_dir_first` | `true` | Ordner vor Dateien anzeigen |
| `show_hidden` | `false` | Versteckte Dateien anzeigen |
| `keybindings` | – | Optional; vom Tastenbelegungs-Editor des Konfigurators geschriebene Belegungsliste |

Das Konfigurationsmenü speichert Änderungen sofort. Die Tasten `.` (versteckte Dateien) und `s` (Sortierung) wirken dagegen nur für die laufende Sitzung.

---

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
| `n` | Neue Datei oder neuen Ordner erstellen (Ordner mit `/` am Ende) |
| `r` | Datei / Ordner umbenennen |
| `/` | Such- und Schnellfilter aktivieren (Live-Filter nach Namensteil) |
| `s` | Sortierkriterium umschalten (Datum, Name, Größe, Typ); gilt für die laufende Sitzung |
| `u` | Letzte Dateiaktion rückgängig machen (Erstellen, Umbenennen, Papierkorb, Einfügen, ZIP erstellen/entpacken) |
| `z` | ZIP-Archiv aus Auswahl (bzw. Eintrag unter dem Cursor) erstellen |
| `e` | Markiertes bzw. ausgewähltes ZIP-Archiv in einen neuen Ordner entpacken |
| `c` | Auswahl in macOS-Zwischenablage kopieren (Finder-kompatibel) |
| `x` | Auswahl ausschneiden (`×`-Markierung) |
| `p` | Zwischenablage im aktuellen Ordner einfügen |
| `c c` | Absoluten Dateipfad in die Zwischenablage kopieren |
| `c f` | Dateinamen in die Zwischenablage kopieren |
| `c d` | Ordnerpfad in die Zwischenablage kopieren |
| `d` | In macOS-Papierkorb verschieben (Bestätigung mit `y` oder `Enter`, alles andere bricht ab) |
| `o` | Datei im konfigurierten Texteditor bearbeiten (Standard `nano`, im Menü `m` änderbar) |
| `.` | Versteckte Dateien ein- oder ausblenden; gilt für die laufende Sitzung |
| `g` | Gehe-zu-Menü öffnen (`d` Downloads, `f` Dokumente, `-` gemerkter Ordner, `h`/`~` Home, `t` Papierkorb, `i` Pfadeingabe, `p` Zwischenablage) |
| `-` | Aktuellen Ordner merken; `g-` springt immer dorthin (bis ein neuer Ordner mit `-` gemerkt wird). Ohne gemerkten Ordner springt `g-` zum zuletzt verwendeten Ordner (letzter Ordner mit einer Aktion wie Auswahl, Kopieren, Ausschneiden, Einfügen, ZIP, Entpacken, Konsole oder Rückgängig; reine Navigation zählt nicht) |
| `~` | Direkt zum Benutzerordner (`~`) springen |
| `j` | An den Anfang der Dateiliste springen |
| `k` | An das Ende der Dateiliste springen |
| `BildAuf` / `BildAb` | 10 Einträge nach oben / unten blättern |
| `t` | Integrierte Konsole öffnen / schließen |
| `Tab` | Fokus auf integrierte Konsole setzen (oder Konsole öffnen) |
| `h` | Hilfe mit Tastenübersicht öffnen |
| `m` | Konfigurationsmenü öffnen |
| `ESC` / `Strg + C` | Konsole schließen, Filter aufheben oder Auswahl/Zwischenspeicher leeren (in dieser Reihenfolge) |
| `q` | EasyDateien beenden |

### Konsolen-Modus (Konsole im Fokus)

| Taste | Aktion |
| :--- | :--- |
| **Alle Zeichen** | Direkte Befehlseingabe (alle Dateimanager-Kürzel sind isoliert deaktiviert) |
| `Enter` | Eingegebenen Befehl im aktuellen Verzeichnis ausführen (`cd`, `clear`, `exit` / `quit` werden intern behandelt) |
| `Tab` | Fokus zurück auf Dateimanager wechseln |
| `ESC` | Konsole schließen |
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
| `Ctrl+D` | Zeichen unter dem Cursor löschen; bei leerer Eingabezeile Konsole schließen |

> [!NOTE]
> `Ctrl+C` wird vom Terminal als Signal behandelt und beendet EasyDateien auch bei fokussierter Konsole sofort (Terminal wird sauber wiederhergestellt). Zum Verwerfen einer Eingabezeile dient `Ctrl+U`.

---

## Maus-Referenz

Die Maus ist standardmäßig aktiv (`mouse_support`) und im Konfigurationsmenü abschaltbar. Solange die Konsole im Fokus ist, wird das Maus-Tracking automatisch freigegeben (native Textauswahl des Terminals).

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

---

## Note / Danksagung

Ich schätze und liebe [Yazi](https://yazi-rs.github.io) sehr. Dieses Projekt ist stark von Yazi inspiriert, soll jedoch eine eigenständige, deutschsprachige, minimalistische und fokussierte Alternative mit integrierter Konsole bieten (und hat technisch nichts direkt mit Yazi zu tun).

- Offizielle Website von Yazi: [https://yazi-rs.github.io](https://yazi-rs.github.io)
- Yazi GitHub Repository: [https://github.com/sxyazi/yazi](https://github.com/sxyazi/yazi)
