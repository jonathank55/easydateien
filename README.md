# EasyDateien

**Minimalistischer, monochromer Terminal-Dateimanager für macOS mit flüssiger Pfeiltastennavigation.**

EasyDateien ist ein extrem schlanker, reaktionsschneller und vollständig autonomer Terminal-Dateimanager ohne externe Abhängigkeiten. Er wurde entwickelt für Anwender, die blitzschnell im Terminal durch Verzeichnisse navigieren, Dateien auswählen, verschieben, kopieren oder in `nano` bearbeiten möchten — ohne visuelle Reizüberflutung, ohne farbige ANSI-Escape-Verwirrung und ohne ressourcenhungrige Hintergrundprozesse.

> [!NOTE]
> **Transparenzhinweis zur Inspiration:**  
> EasyDateien ist von der Tastatur- und Navigationsphilosophie moderner Terminal-Dateimanager wie **Yazi** inspiriert, wurde jedoch bewusst als eigenständiges, radikal vereinfachtes Werkzeug konzipiert. Es soll bewusst sehr viel einfacher, fokussierter und wartungsärmer sein. EasyDateien hat **keine offizielle Verbindung zum Yazi-Projekt** und teilt lediglich die Begeisterung für effiziente Tastaturnavigation im Terminal.

---

## Kernmerkmale

- **Monochrome Typografie (ohne ANSI-Farben):**  
  Verzichtet bewusst auf bunte ANSI-Farbcodes und setzt ausschließlich auf standardisierte typografische Auszeichnungen (Fettdruck und Kursivschrift) des jeweiligen Terminal-Farbschemas. Garantiert makellose Lesbarkeit auf sowohl hellen als auch dunklen Hintergründen.

- **Benutzeroberfläche im Yazi-Kasten-Design & vollständige Fensterfüllung:**  
  Präziser, randloser Kastenaufbau mit echten abgerundeten Ecken (`╭`, `╮`, `╰`, `╯`) und Spaltentrennlinien (`┬`, `┴`, `│`), der sich nahtlos über die gesamte Terminalbreite und -höhe erstreckt. Durch die Nutzung des Alternate-Screen-Buffers (`\033[?1049h`) und strikte Zeilenbudgetierung ist ein Verrutschen oder Scrollen des Terminalfensters technisch ausgeschlossen.

- **Volladaptive Größenanpassung (Window-Resize in Echtzeit):**  
  Reagiert unverzüglich auf jede Veränderung der Terminalfenstergröße (`SIGWINCH`). Sämtliche Spaltenbreiten, Kastenränder und Statusangaben werden in Echtzeit berechnet. Zu lange Datei- und Ordnernamen werden dynamisch berechnet und am Ende sauber mit `...` abgeschnitten — kein Zeilenumbruch, kein Bildschirmflackern, selbst auf kleinsten Fenstern (< 40 Zeichen Breite oder < 6 Zeilen Höhe).

- **Dynamische Spaltenanzahl (Miller-Columns nach Yazi-Vorbild):**  
  Die Spaltenansicht bleibt erhalten, bis das Fenster wirklich zu schmal wird:  
  - **Breite Fenster (>= 68 Zeichen):** 3 Spalten (Eltern-Ordner links + Aktueller Ordner mittig + Kindordner bzw. Datei-Details rechts)  
  - **Mittlere Fenster (38–67 Zeichen):** 2 Spalten (Eltern-Ordner links zur Orientierung + Aktueller Ordner rechts)  
  - **Kompakte Fenster (< 38 Zeichen):** 1 Spalte (Fokus auf aktuellen Ordner)  
  - Über das Konfigurationsmenü kann die Spaltendarstellung bei Bedarf ein- oder ausgeschaltet werden.

- **Vollständige Mausnavigation & Scrollen:**  
  Durch das gesamte Programm kann flüssig mit der Maus navigiert werden:  
  - **Mausrad nach oben / unten:** Flüssiges Scrollen durch die Dateiliste  
  - **Linksklick:** Element auswählen; Doppelklick öffnet die Datei bzw. betritt den Ordner  
  - **Klick auf linke Spalte:** Sofortiges Zurückwechseln in den übergeordneten Ordner  
  - **Klick auf rechte Spalte:** Kindordner betreten bzw. Datei-Details ansehen  
  - **Rechtsklick:** Element markieren bzw. Markierung umschalten (`*`)  
  - Im Konfigurationsmenü über `Maussteuerung: [Ein / Aus]` jederzeit anpassbar.

- **Tastaturnavigation wie bei Yazi:**  
  Flüssige Steuerung über Standard-Pfeiltasten (`↑`, `↓`, `←`, `→`) oder klassische Vim-Keys (`h`, `j`, `k`, `l`).  
  - `↑` / `k`: Nach oben navigieren  
  - `↓` / `j`: Nach unten navigieren  
  - `Enter`: Datei oder Ordner mit macOS-Standardbefehl (`open`) öffnen (bei Ordnern öffnet sich der Finder)  
  - `→` / `l`: In Ordner hineingehen (Navigation innerhalb von EasyDateien)  
  - `e`: Datei direkt im Terminal-Editor `nano` bearbeiten  
  - `o`: Datei direkt im Terminal-Editor `vim` bearbeiten  
  - `←` / `h`: Zum übergeordneten Ordner zurückkehren  
  - `g d`: Direkt zu `~/Downloads` springen  
  - `g f`: Direkt zu `~/Documents` springen  
  - `g h` / `~`: Direkt zum Benutzerordner (`~`) springen  
  - `g i`: Interaktive Pfadeingabe mit Eingabezeile  
  - `g p`: Zu im Zwischenspeicher liegendem Pfad navigieren  

- **Editor-Integration (`nano` mit `e`, `vim` mit `o`):**  
  Dateien können blitzschnell im gewünschten Editor geöffnet werden: Drücken der Taste `e` öffnet die markierte Datei sofort in `nano`, Taste `o` öffnet sie in `vim`. Nach Beenden des Editors kehrt man nahtlos ohne Flackern zurück.

- **Vorschau bewusst deaktiviert:**  
  Für maximale Darstellungsgeschwindigkeit und minimale Ablenkung ist die Dateivorschau dauerhaft deaktiviert; bei markierten Dateien werden in der rechten Spalte übersichtliche Metadaten (Größe, Datum, Zugriffsrechte) angezeigt.

- **Auswahldarstellung & macOS-Systemzwischenablage:**  
  - Auswahl: `*` (z. B. `▸ * datei.txt`)  
  - Ausschneiden (Cut): `×` (z. B. `  × datei.txt`)  
  - Kopieren: `+` (z. B. `  + datei.txt`)  
  - `Space` / `v`: Datei oder Ordner markieren / abwählen (`*`) und Cursor eine Zeile weiterrücken  
  - `V` / `a`: Alle sichtbaren Dateien auf einmal markieren oder abwählen  
  - `x`: Markierte Dateien (oder aktuelle Datei) zum **Ausschneiden** vormerken (`×`)  
  - `y` / `c y`: Markierte Dateien zum **Kopieren** vormerken. **Echte macOS-Systemzwischenablage-Integration:** Die Dateien werden als native macOS-Dateireferenzen (`NSFilenamesPboardType` / `public.file-url`) registriert und können sofort systemweit im Finder (Cmd+V), in Mail, WhatsApp, Slack oder Notes eingesetzt werden!  
  - `p`: Vormerkung im aktuellen Verzeichnis **einsetzen / einfügen** (erkennt nahtlos auch zuvor im macOS Finder mit Cmd+C kopierte Dateien und verhindert Namenskollisionen automatisch)  
  - `Y` / `X`: Zwischenspeicher leeren / Unyank (wie in Yazi)  
  - `c z`: Ausgewählte Dateien direkt als ZIP-Archiv komprimieren (wie in Yazi via Zip-Plugin)  
  - `c c`: Absoluten Pfad des Elements in die Zwischenablage kopieren  
  - `c f`: Dateinamen in die Zwischenablage kopieren  
  - `c d`: Ordnerpfad in die Zwischenablage kopieren  
  - `d`: Datei(en) mit Sicherheitsabfrage `(y/N)` in den **macOS-Papierkorb** verschieben (`trash`)  
  - `g g` / `G`: Blitzschnell an den Anfang (`g g`) oder ans Ende (`G`) der Liste springen  
  - `.` / `z`: Versteckte Dateien ein- oder ausblenden  
  - `e`: Datei direkt in nano öffnen / bearbeiten  
  - `o`: Datei direkt in vim öffnen / bearbeiten  
  - `r`: Datei / Ordner umbenennen  

- **Integrierte Konsole & Terminal (Taste `t`):**  
  EasyDateien besitzt ein vollständig integriertes Terminal-Panel:
  - **Umschalten mit `t`:** Blendet die Konsole blitzschnell ein oder aus.
  - **Konfigurierbare Position:** `[Unten]`, `[Rechts]` oder `[Links]` — über das Menü (`m`) anpassbar.
  - **Zwei-Wege-Verzeichnissynchronisation:** Das Terminal operiert immer im aktuellen Verzeichnis des Dateimanagers. Navigiert man im Dateimanager, folgt das Terminal automatisch. Wechselt man im Terminal mit `cd ..` das Verzeichnis, folgt der Dateimanager sofort!
  - **Automatische Dateilisten-Aktualisierung:** Sobald im Terminal Befehle wie `touch datei.txt`, `mkdir ordner`, `git checkout` oder `rm bild.png` ausgeführt werden, aktualisiert der Dateimanager die Ansicht unverzüglich.
  - **Fokus-Umschaltung:** Mit `Tab` oder `ESC` wechselt man bequem zwischen Dateimanager und Konsole hin und her. Ein Klick mit der Maus in den Konsolenbereich setzt den Fokus ebenfalls direkt auf die Konsole.
  - **Voller Terminalkomfort:** Befehlsverlauf (`↑`/`↓`), Zeilennavigation (`Pos1`/`Ende`, `Ctrl+A`/`Ctrl+E`, `Ctrl+W`, `Ctrl+U`, `Ctrl+K`), Bildschirm leeren (`clear` / `Ctrl+L`) und Schließen per `exit`, `quit` oder `Ctrl+D`.
  - **Interaktive Programme:** Vollbildanwendungen wie `nano`, `vim`, `htop` oder `zsh` werden sauber im Vollbild ausgeführt und kehren ohne Bildartefakte zurück.

- **Interaktives Konfigurationsmenü (Taste `m`):**  
  Wie bei SCHNELLSTART verfügt EasyDateien über einen vollwertigen interaktiven Konfigurator mit direktem In-Place-Toggeln ohne störende Untermenüs:
  - **Tastenbelegungen bearbeiten:** Jede Aktion kann interaktiv auf eine neue Taste umbelegt oder mit Alternativtasten belegt werden.
  - **Steuerung in Statusleiste:** `[Ein]` / `[Aus]` (zeigt die Tastensteuerung im Yazi-Badge-Design oder klassische Dateimetadaten).
  - **Spaltendarstellung:** `[Ein]` / `[Aus]` (Ein = mehrspaltiges Miller-Layout, Aus = klassische 1-Spalten-Ansicht).
  - **Maussteuerung:** `[Ein]` / `[Aus]` umschalten.
  - **Trennungslinien:** `[Vertikal]`, `[Horizontal]`, `[Außen]` oder `[Keine]` direkt durchschalten.
  - **Mit ESC beenden:** `[Ein]` / `[Aus]` (standardmäßig deaktiviert; ESC hebt stattdessen Auswahlen/Zwischenspeicher auf).
  - **Versteckte Dateien anzeigen:** `[Ein]` / `[Aus]` umschalten.
  - **Text- & Code-Editor festlegen:** z. B. `nano %s`, `vim %s`, `micro %s` oder `code %s`.
  - **Standard-Öffner anpassen:** z. B. `open %s`.
  - **Sortierkriterium & Sortierrichtung:** Direktes Durchschalten der Kriterien und Sortierreihenfolge.
  - **Sortierkriterien anpassen:** Sortieren nach Änderungsdatum (`mtime`), Dateiname (`name`), Dateigröße (`size`) oder Dateiendung (`ext`).
  - **Sortierrichtung:** `[Neueste/Z-A zuerst]` oder `[Älteste/A-Z zuerst]`.
  - **Ordner immer zuerst anzeigen:** `[Ein]` / `[Aus]`.
  - **Zurücksetzen auf Standardwerte:** Stellt die exakte Yazi-Referenzkonfiguration mit einem Klick wieder her.

---

## Installation

### Manuelle Installation

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

Das Skript richtet das Konfigurationsverzeichnis unter `~/.config/easydateien/` ein und erstellt die Symlinks `easydateien` und `ed` in `~/.local/bin/`.

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

CLI-Optionen des Konfigurators:
- `easydateien --config` : Interaktives Menü starten
- `python3 ~/.config/easydateien/easydateien_konfigurator.py --list` : Aktuelle Konfiguration als JSON anzeigen
- `python3 ~/.config/easydateien/easydateien_konfigurator.py --toggle-hidden` : Versteckte Dateien umschalten
- `python3 ~/.config/easydateien/easydateien_konfigurator.py --reset` : Auf Werkseinstellungen zurücksetzen

---

## Konfigurationsdatei (`~/.config/easydateien/config.json`)

Die Konfiguration wird in einem transparenten, sauberen JSON-Format gespeichert:

```json
{
  "sort_by": "mtime",
  "sort_reverse": true,
  "sort_dir_first": true,
  "show_hidden": false,
  "preview": false,
  "columns_enabled": true,
  "divider_style": "horizontal",
  "esc_to_quit": false,
  "text_editor": "nano %s",
  "opener": "open %s",
  "edit_opener": "open -e %s",
  "finder_opener": "open -R %s",
  "keybindings": {
    "up": ["UP", "k"],
    "down": ["DOWN", "j"],
    "left": ["LEFT", "h"],
    "right": ["RIGHT", "l"],
    "open": ["ENTER"],
    "select": ["SPACE", "v"],
    "select_all": ["V", "a"],
    "cut": ["x"],
    "copy": ["y", "c"],
    "paste": ["p"],
    "trash": ["d"],
    "toggle_hidden": [".", "z"],
    "config_menu": ["m", "C"],
    "goto_downloads": ["gd"],
    "goto_documents": ["gf"],
    "goto_home": ["gh", "~"],
    "goto_interactive": ["gi"],
    "goto_clipboard": ["gp"],
    "zip": ["cz"],
    "quit": ["q"]
  }
}
```

---

## Tastatur-Referenz

| Taste | Aktion |
| :--- | :--- |
| `↑` / `k` | Cursor nach oben bewegen |
| `↓` / `j` | Cursor nach unten bewegen |
| `→` / `l` | In Verzeichnis wechseln |
| `←` / `h` | In übergeordneten Ordner wechseln |
| `Enter` | Element systemweit öffnen via `open` (Ordner öffnen im Finder) |
| `Space` / `v` | Aktuelle Datei markieren / Markierung aufheben (`*`) |
| `V` / `a` | Alle Dateien markieren bzw. Auswahl aufheben |
| `y` / `c y` | Auswahl kopieren / yank (synchronisiert mit macOS-Clipboard für Finder/Mail/WhatsApp) |
| `x` | Auswahl ausschneiden / cut (`×`) |
| `p` | Zwischenspeicher im aktuellen Ordner einfügen (auch im Finder kopierte Dateien) |
| `Y` / `X` | Zwischenspeicher leeren / Unyank |
| `c z` | ZIP-Archiv aus markierten Dateien erstellen |
| `c c` | Absoluten Dateipfad in die Zwischenablage kopieren |
| `c f` | Dateinamen in die Zwischenablage kopieren |
| `c d` | Ordnerpfad in die Zwischenablage kopieren |
| `d` | In macOS-Papierkorb verschieben mit Bestätigung `(y/N)` |
| `g g` / `Home` | An den Anfang der Dateiliste springen |
| `G` / `End` | An das Ende der Dateiliste springen |
| `.` / `z` | Versteckte Dateien ein- oder ausblenden |
| `g d` | Gehe zu `~/Downloads` |
| `g f` | Gehe zu `~/Documents` |
| `g h` / `~` | Gehe zu `~` (Home) |
| `g i` | Pfad manuell über Tastatur eingeben |
| `g p` | Zu Pfad aus Zwischenablage springen |
| `t` | Integrierte Konsole / Terminal anzeigen / ausblenden |
| `Tab` | Fokus zwischen Dateimanager und Konsole wechseln |
| `m` | Konfigurationsmenü öffnen |
| `e` | Datei in nano bearbeiten |
| `o` | Datei in vim bearbeiten |
| `r` | Datei / Ordner umbenennen |
| `q` / `ESC` | Programm beenden (bzw. Auswahl aufheben) |

---

## Maus-Referenz

| Maus-Aktion | Funktion |
| :--- | :--- |
| **Mausrad nach oben / unten** | Cursor in der aktuellen Spalte nach oben / unten bewegen |
| **Linksklick auf Eintrag** | Element auswählen |
| **Linksklick auf ausgewähltes Element / Doppelklick** | Datei öffnen (Text/Code in `nano`, Medien via `open`) bzw. Ordner betreten |
| **Linksklick auf linke Spalte** | Zum übergeordneten Ordner zurückkehren |
| **Linksklick auf rechte Spalte** | Kindordner betreten bzw. Datei-Details öffnen |
| **Linksklick auf Pfadzeile (oben)** | Interaktive Pfadeingabe (`goto`) starten |
| **Rechtsklick auf Eintrag** | Element-Auswahl umschalten (`*`) |

---

## Lizenz

Veröffentlicht unter der [MIT-Lizenz](LICENSE).  
Copyright (c) 2026 Jonathan Klatchko.


---

## Note / Danksagung

Ich schätze und liebe [Yazi](https://yazi-rs.github.io) sehr. Dieses Projekt ist stark von Yazi inspiriert, soll jedoch eine wesentlich simplere, minimalistische und monochrome Alternative bieten (und hat technisch nichts direkt mit Yazi zu tun).

- Offizielle Website von Yazi: [https://yazi-rs.github.io](https://yazi-rs.github.io)
- Yazi GitHub Repository: [https://github.com/sxyazi/yazi](https://github.com/sxyazi/yazi)
