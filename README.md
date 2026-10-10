# EasyDateien

**Minimalistischer, hocheffizienter Terminal-Dateimanager für macOS mit integrierter Konsole und flüssiger Tastaturnavigation.**

EasyDateien ist ein extrem schlanker, reaktionsschneller und autonomer Terminal-Dateimanager ohne externe Python-Abhängigkeiten. Er wurde entwickelt für Anwender, die blitzschnell im Terminal durch Verzeichnisse navigieren, Dateien auswählen, verschieben, kopieren, suchen, komprimieren oder in Editoren bearbeiten möchten — kombiniert mit einem vollintegrierten Terminal-Panel für maximale Produktivität.

> [!NOTE]
> **Transparenzhinweis zur Inspiration:**  
> EasyDateien ist von der Tastatur- und Navigationsphilosophie moderner Terminal-Dateimanager wie **Yazi** inspiriert, wurde jedoch bewusst als eigenständiges, radikal vereinfachtes Werkzeug konzipiert. Es soll bewusst sehr viel einfacher, fokussierter und wartungsärmer sein. EasyDateien hat **keine offizielle Verbindung zum Yazi-Projekt** und teilt lediglich die Begeisterung für effiziente Tastaturnavigation im Terminal.

---

## Kernmerkmale

- **Integrierte Konsole & Terminal mit strikter Fokus-Isolation (`t`, `Tab`, `ESC`):**  
  EasyDateien besitzt ein vollintegriertes Terminal-Panel mit konfigurierbarer Position (`[Unten]`, `[Rechts]` oder `[Links]`):
  - **Strikte Fokus-Isolation:**  
    - **Konsole im Fokus (`[KONSOLE]`):** Sämtliche Tastenbelegungen des Dateimanagers sind strikt inaktiv. Alle Buchstaben und Zeichen (`u`, `z`, `d`, `q`, `r`, `y`, `x`, `p`, `e`, `o`, `m`, `s`, etc.) fließen ohne Kollision direkt in die Befehlszeile.
    - **`ESC`:** Schließt die Konsole deterministisch.
    - **`Tab` / `Shift+Tab`:** Wechselt den Fokus zurück zum Dateimanager.
    - **Konsole geöffnet, aber nicht im Fokus:** Sämtliche Tastenkürzel des Dateimanagers sind aktiv; es wird nichts versehentlich in die Konsole eingetippt. `Tab` setzt den Fokus zurück in die Konsole.
  - **Zwei-Wege-Verzeichnissynchronisation:** Das Terminal operiert immer im aktuellen Verzeichnis des Dateimanagers. Navigiert man im Dateimanager, folgt das Terminal automatisch. Wechselt man im Terminal mit `cd ..` das Verzeichnis, folgt der Dateimanager sofort!
  - **Automatische Dateilisten-Aktualisierung:** Sobald im Terminal Befehle wie `touch datei.txt`, `mkdir ordner`, `git checkout` oder `rm bild.png` ausgeführt werden, aktualisiert der Dateimanager die Ansicht unverzüglich.
  - **Voller Terminalkomfort:** Befehlsverlauf (`↑`/`↓`), Zeilennavigation (`Pos1`/`Ende`, `Ctrl+A`/`Ctrl+E`, `Ctrl+W` zum Wortlöschen, `Ctrl+U`/`Ctrl+K` zum Zeilenlöschen, `Ctrl+L` zum Leeren), Bildlauf (`BildAuf`/`BildAb` oder Mausrad) und Schließen per `exit`, `quit` oder `Ctrl+D`.
  - **Interaktive Vollbild-Programme:** Anwendungen wie `nano`, `vim`, `htop` oder `zsh` werden sauber im Vollbild ausgeführt und kehren ohne Bildartefakte zurück.

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
  - **Linksklick:** Element auswählen; Doppelklick öffnet die Datei bzw. betritt den Ordner  
  - **Klick auf linke Spalte:** Sofortiges Zurückwechseln in den übergeordneten Ordner  
  - **Klick auf rechte Spalte:** Kindordner betreten bzw. Datei-Details ansehen  
  - **Klick in Konsolenbereich:** Setzt den Fokus direkt auf die Konsole  
  - **Rechtsklick:** Element markieren bzw. Markierung umschalten (`*`)  
  - Im Konfigurationsmenü über `Mausunterstützung: [Ein / Aus]` jederzeit anpassbar.

- **Umfassende Dateioperationen & Undo-System:**  
  - **Suchen & Schnellfilter (`/`):** Interaktiver Live-Filter für die Dateiliste.  
  - **Neu erstellen (`n`):** Neue Dateien oder Verzeichnisse anlegen (Ordner mit `/` am Ende).  
  - **Umbenennen (`r`):** Inline-Umbenennen mit Sofort-Feedback.  
  - **Papierkorb (`d`):** Sicheres Verschieben in den macOS-Papierkorb (`~/.Trash`) mit Sicherheitsabfrage.  
  - **Rückgängig (`u`):** Mehrstufiges Undo-System für Erstellen, Umbenennen und Löschen.  
  - **ZIP-Komprimierung (`z`):** Ausgewählte Dateien direkt als ZIP-Archiv komprimieren.  
  - **Editor-Integration (`e` für Nano, `o` für Vim):** Dateien blitzschnell im gewünschten Editor bearbeiten.  
  - **Systemweites Öffnen (`Enter`):** Öffnet Dateien mit der macOS-Standard-App oder Ordner direkt im Finder.

- **Auswahldarstellung & macOS-Systemzwischenablage:**  
  - Auswahl: `*` (z. B. `▸ * datei.txt`)  
  - Ausschneiden (Cut): `×` (z. B. `  × datei.txt`)  
  - Kopieren: `+` (z. B. `  + datei.txt`)  
  - `Space` / `v`: Datei oder Ordner markieren / abwählen (`*`)  
  - `V` / `a`: Alle sichtbaren Dateien auf einmal markieren oder abwählen  
  - `x`: Markierte Dateien zum **Ausschneiden** vormerken (`×`)  
  - `y` / `c`: Markierte Dateien zum **Kopieren** vormerken. **Echte macOS-Systemzwischenablage-Integration:** Dateien werden als native macOS-Dateireferenzen (`NSFilenamesPboardType` / `public.file-url`) registriert und können sofort systemweit im Finder (Cmd+V), in Mail, WhatsApp, Slack oder Notizen eingefügt werden!  
  - `p`: Vormerkung im aktuellen Verzeichnis **einfügen** (erkennt auch im Finder kopierte Dateien und verhindert Namenskollisionen automatisch)  
  - `Y` / `X`: Zwischenspeicher leeren  
  - `c c`: Absoluten Dateipfad in die Zwischenablage kopieren  
  - `c f`: Dateinamen in die Zwischenablage kopieren  
  - `c d`: Ordnerpfad in die Zwischenablage kopieren  

- **Gehe-zu-Schnellnavigation (`g`):**  
  - `g d`: Downloads (`~/Downloads`)  
  - `g f`: Dokumente (`~/Documents`)  
  - `g h` / `~`: Benutzerordner (`~`)  
  - `g t`: Papierkorb (`~/.Trash`)  
  - `g i`: Pfad manuell eingeben  
  - `g p`: Zu Pfad aus Zwischenablage springen  

- **Interaktives Konfigurationsmenü (`m`):**  
  Vollwertiger interaktiver Konfigurator mit direktem In-Place-Toggeln ohne störende Untermenüs:
  - Trennungslinien-Stil (`alle`, `vertikal`, `außen`, `horizontal`, `keine`)
  - Spalten-Layout (`Ein` / `Aus`)
  - Mausunterstützung (`Ein` / `Aus`)
  - Versteckte Dateien anzeigen (`Ein` / `Aus`)
  - Tastenbelegungen ansehen und anpassen
  - Auf Standardwerte zurücksetzen

---

## Installation

### Automatische Installation

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

Das Skript richtet das Konfigurationsverzeichnis unter `~/.config/easydateien/` ein, kompiliert das native macOS-Clipboard-Modul und erstellt die Symlinks `easydateien` und `ed` in `~/.local/bin/`.

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

---

## Konfigurationsdatei (`~/.config/easydateien/config.json`)

Die Konfiguration wird im standardisierten JSON-Format gespeichert:

```json
{
  "divider_style": "alle",
  "columns_enabled": true,
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

---

## Tastatur-Referenz

### Dateimanager-Modus

| Taste | Aktion |
| :--- | :--- |
| `↑` / `k` | Cursor nach oben bewegen |
| `↓` / `j` | Cursor nach unten bewegen |
| `→` / `l` | In Verzeichnis wechseln |
| `←` | In übergeordneten Ordner wechseln |
| `Enter` | Element systemweit öffnen via `open` (Ordner öffnen im Finder) |
| `Space` / `v` | Aktuelle Datei markieren / Markierung aufheben (`*`) |
| `V` / `a` | Alle Dateien markieren bzw. Auswahl aufheben |
| `n` | Neue Datei oder neuen Ordner erstellen (Ordner mit `/` am Ende) |
| `r` | Datei / Ordner umbenennen |
| `/` | Such- und Schnellfilter aktivieren |
| `s` | Sortierkriterium umschalten (Datum, Name, Größe, Typ) |
| `u` | Letzte Dateiaktion rückgängig machen (Undo für Erstellen, Umbenennen, Papierkorb) |
| `z` | ZIP-Archiv aus Auswahl erstellen |
| `y` / `c` | Auswahl in macOS-Zwischenablage kopieren (Finder-kompatibel) |
| `x` | Auswahl ausschneiden (`×`) |
| `p` | Zwischenablage im aktuellen Ordner einfügen |
| `Y` / `X` | Zwischenspeicher leeren |
| `c c` | Absoluten Dateipfad in die Zwischenablage kopieren |
| `c f` | Dateinamen in die Zwischenablage kopieren |
| `c d` | Ordnerpfad in die Zwischenablage kopieren |
| `d` | In macOS-Papierkorb verschieben (mit Bestätigung) |
| `e` | Datei in `nano` bearbeiten |
| `o` | Datei in `vim` bearbeiten |
| `.` | Versteckte Dateien ein- oder ausblenden |
| `g` | Gehe-zu-Menü öffnen (`d` Downloads, `f` Dokumente, `h`/`~` Home, `t` Papierkorb, `i` Pfadeingabe, `p` Zwischenablage) |
| `~` | Direkt zum Benutzerordner (`~`) springen |
| `Home` | An den Anfang der Dateiliste springen |
| `End` / `G` | An das Ende der Dateiliste springen |
| `BildAuf` / `BildAb` | 10 Einträge nach oben / unten blättern |
| `t` | Integrierte Konsole öffnen / schließen |
| `Tab` | Fokus auf integrierte Konsole setzen (oder Konsole öffnen) |
| `m` | Konfigurationsmenü öffnen |
| `ESC` | Konsole schließen, Filter aufheben oder Auswahl/Zwischenspeicher leeren |
| `q` | EasyDateien beenden |

### Konsolen-Modus (Konsole im Fokus)

| Taste | Aktion |
| :--- | :--- |
| **Alle Zeichen** | Direkte Befehlseingabe (alle Dateimanager-Kürzel sind isoliert deaktiviert) |
| `Enter` | Eingegebenen Befehl im aktuellen Verzeichnis ausführen |
| `Tab` / `Shift+Tab` | Fokus zurück auf Dateimanager wechseln |
| `ESC` | Konsole schließen und Fokus auf Dateimanager setzen |
| `↑` / `↓` | Befehlsverlauf durchblättern |
| `←` / `→` | Cursor in der Befehlszeile nach links / rechts bewegen |
| `Pos1` / `Ctrl+A` | Cursor an den Anfang der Zeile setzen |
| `Ende` / `Ctrl+E` | Cursor an das Ende der Zeile setzen |
| `Backspace` | Zeichen vor dem Cursor löschen |
| `Delete` | Zeichen unter dem Cursor löschen |
| `Ctrl+W` | Vorheriges Wort löschen |
| `Ctrl+U` | Zeile bis zum Cursor löschen |
| `Ctrl+K` | Zeile ab Cursor bis zum Ende löschen |
| `Ctrl+L` | Terminal-Ausgabepuffer leeren (`clear`) |
| `BildAuf` / `BildAb` | Konsolenausgabe nach oben / unten scrollen |
| `Ctrl+C` / `Ctrl+D` | Aktuelle Eingabezeile verwerfen |

---

## Maus-Referenz

| Maus-Aktion | Funktion |
| :--- | :--- |
| **Mausrad nach oben / unten** | Cursor in der Dateiliste bewegen bzw. Konsolenausgabe scrollen |
| **Linksklick auf Eintrag** | Element auswählen |
| **Doppelklick auf Eintrag** | Datei öffnen bzw. Ordner betreten |
| **Linksklick auf linke Spalte** | Zum übergeordneten Ordner zurückkehren |
| **Linksklick auf rechte Spalte** | Kindordner betreten bzw. Datei-Details öffnen |
| **Linksklick in Konsole** | Fokus direkt auf die Konsole setzen |
| **Rechtsklick auf Eintrag** | Element-Auswahl umschalten (`*`) |

---

## Lizenz

Veröffentlicht unter der [MIT-Lizenz](LICENSE).  
Copyright (c) 2026 Jonathan Klatchko.

---

## Note / Danksagung

Ich schätze und liebe [Yazi](https://yazi-rs.github.io) sehr. Dieses Projekt ist stark von Yazi inspiriert, soll jedoch eine eigenständige, minimalistische und fokussierte Alternative bieten (und hat technisch nichts direkt mit Yazi zu tun).

- Offizielle Website von Yazi: [https://yazi-rs.github.io](https://yazi-rs.github.io)
- Yazi GitHub Repository: [https://github.com/sxyazi/yazi](https://github.com/sxyazi/yazi)
