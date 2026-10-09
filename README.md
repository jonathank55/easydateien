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

- **Benutzeroberfläche im SCHNELLSTART-Design:**  
  Strukturierter, vertikal austarierter Aufbau mit dezenten Trennlinien, präzisem Cursor (`▸`), klaren Spalten für Dateigröße und Änderungsdatum sowie reaktiver Status- und Befehlszeile.

- **Volladaptive Größenanpassung (Window-Resize in Echtzeit):**  
  Reagiert unverzüglich auf jede Veränderung der Terminalfenstergröße (`SIGWINCH`). Sämtliche Spaltenbreiten, Pfadkürzungen (`...`) und Fenstergrenzen werden in Echtzeit mathematisch exakt neu berechnet — kein Zeilenumbruch, kein Bildschirmflackern.

- **Dynamische Spaltenanzahl (Miller-Columns nach Yazi-Vorbild):**  
  Passt die Anzahl der angezeigten Spalten vollautomatisch und flüssig an die Breite des Terminalfensters an:  
  - **Schmale Fenster (< 70 Zeichen):** 1 Spalte (Fokus auf aktuellen Ordner mit maximaler Zeichenbreite für Dateinamen, Größe und Datum)  
  - **Mittlere Fenster (70–110 Zeichen):** 2 Spalten (Eltern-Ordner links zur Orientierung + Aktueller Ordner rechts)  
  - **Breite Fenster (> 110 Zeichen):** 3 Spalten (Eltern-Ordner links + Aktueller Ordner mittig + Kindordner-Inhalt bzw. Datei-Details rechts)  
  - Über das Konfigurationsmenü kann die Spaltenanzahl bei Bedarf auch dauerhaft auf 1, 2 oder 3 Spalten festgelegt werden.

- **Tastaturnavigation wie bei Yazi:**  
  Flüssige Steuerung über Standard-Pfeiltasten (`↑`, `↓`, `←`, `→`) oder klassische Vim-Keys (`h`, `j`, `k`, `l`).  
  - `↑` / `k`: Nach oben navigieren  
  - `↓` / `j`: Nach unten navigieren  
  - `→` / `l` / `Enter`: In Ordner hineingehen bzw. Datei öffnen  
  - `←` / `h`: Zum übergeordneten Ordner zurückkehren  
  - `g d`: Direkt zu `~/Downloads` springen  
  - `g f`: Direkt zu `~/Documents` springen  
  - `g h` / `~`: Direkt zum Benutzerordner (`~`) springen  
  - `g i`: Interaktive Pfadeingabe mit Eingabezeile  
  - `g p`: Zu im Zwischenspeicher liegendem Pfad navigieren  

- **Standard-Editor `nano` für Text, Markdown & Code:**  
  Sämtliche Text-, Markdown- und Quellcodedateien (`.txt`, `.md`, `.py`, `.sh`, `.json`, `.toml`, `.yaml`, `.c`, `.js`, `.html`, `.css`, `Makefile`, etc.) öffnen sich per `Enter` direkt und nahtlos im Terminal-Editor `nano`. Nach dem Beenden (`Ctrl+X`) kehren Sie ohne Flackern sofort in EasyDateien zurück. Medien- und Binärdateien (Bilder, PDFs, Videos) öffnen sich über macOS `open`.

- **Vorschau bewusst deaktiviert:**  
  Für maximale Darstellungsgeschwindigkeit und minimale Ablenkung ist die Dateivorschau dauerhaft deaktiviert.

- **Auswahldarstellung & Dateioperationen:**  
  - `Space` / `v`: Datei oder Ordner markieren / abwählen (visuelle Markierung `[✓]`) und Cursor eine Zeile weiterrücken  
  - `V` / `a`: Alle sichtbaren Dateien auf einmal markieren oder abwählen  
  - `x`: Markierte Dateien (oder aktuelle Datei) zum **Ausschneiden** vormerken (`[X]`)  
  - `c`: Markierte Dateien (oder aktuelle Datei) zum **Kopieren** vormerken (`[C]`)  
  - `p`: Vormerkung im aktuellen Verzeichnis **einsetzen / einfügen** (inkl. automatischer Erkennung und Umbenennung bei Namenskollisionen)  
  - `d`: Datei(en) mit Sicherheitsabfrage `(y/N)` in den **macOS-Papierkorb** verschieben (`trash`)  
  - `c z`: Ausgewählte Dateien als ZIP-Archiv komprimieren  
  - `.` / `z`: Versteckte Dateien ein- oder ausblenden  
  - `o`: Datei explizit mit der macOS-Standardanwendung öffnen  
  - `e`: Datei in TextEdit öffnen  
  - `r`: Datei im Finder anzeigen (`reveal`)  

- **Interaktives Konfigurationsmenü (Taste `m`):**  
  Wie bei SCHNELLSTART verfügt EasyDateien über einen vollwertigen interaktiven Konfigurator:
  - **Tastenbelegungen bearbeiten:** Jede Aktion kann interaktiv auf eine neue Taste umbelegt oder mit Alternativtasten belegt werden.
  - **Spaltenanzahl & Layout:** `[Dynamisch (Auto)]`, `[1 Spalte]`, `[2 Spalten]` oder `[3 Spalten]` frei konfigurierbar.
  - **Versteckte Dateien anzeigen:** `[Ein]` / `[Aus]` umschalten.
  - **Text- & Code-Editor festlegen:** z. B. `nano %s`, `vim %s`, `micro %s` oder `code %s`.
  - **Standard-Öffner anpassen:** z. B. `open %s`.
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
    "copy": ["c"],
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
    "quit": ["q", "ESC"]
  }
}
```

---

## Tastatur-Referenz

| Taste | Aktion |
| :--- | :--- |
| `↑` / `k` | Cursor nach oben bewegen |
| `↓` / `j` | Cursor nach unten bewegen |
| `→` / `l` / `Enter` | In Verzeichnis wechseln bzw. Datei in `nano` / Standard-App öffnen |
| `←` / `h` | In übergeordneten Ordner wechseln |
| `Space` / `v` | Aktuelle Datei markieren / Markierung aufheben |
| `V` / `a` | Alle Dateien markieren bzw. Auswahl aufheben |
| `x` | Auswahl ausschneiden |
| `c` | Auswahl kopieren |
| `p` | Zwischenspeicher im aktuellen Ordner einfügen |
| `d` | In macOS-Papierkorb verschieben mit Bestätigung `(y/N)` |
| `c z` | ZIP-Archiv aus Auswahl erstellen |
| `.` / `z` | Versteckte Dateien ein- oder ausblenden |
| `g d` | Gehe zu `~/Downloads` |
| `g f` | Gehe zu `~/Documents` |
| `g h` / `~` | Gehe zu `~` (Home) |
| `g i` | Pfad manuell über Tastatur eingeben |
| `g p` | Zu Pfad aus Zwischenablage springen |
| `m` | Konfigurationsmenü öffnen |
| `o` | Datei mit macOS-Standard-App öffnen |
| `e` | Datei mit TextEdit öffnen |
| `r` | Datei im Finder anzeigen |
| `q` / `ESC` | Programm beenden (bzw. Auswahl aufheben) |

---

## Lizenz

Veröffentlicht unter der [MIT-Lizenz](LICENSE).  
Copyright (c) 2026 Jonathan Klatchko.
