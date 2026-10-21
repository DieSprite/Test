# ClickUp → Projektbuch Büro-Plattform

`clickup_to_projektbuch.py` erzeugt aus einem ClickUp-Export eine Importdatei für das Projektbuch
(Einstellungen → Daten → JSON importieren). Die Datei folgt dem in der App beschriebenen Weg
(„Migration aus ClickUp“): Tasks mit gleicher Projektnummer werden zu einem Projekt zusammengeführt,
der Listenstatus wird zum Wert des Kernfelds (Statik, Pläne, WSN, Förderphase, QNG-Prozess, BEG-EM-Prozess),
Custom Fields gehen in die gleichnamigen Leistungsfelder, Zuständige über die ClickUp-User-ID der
Mitarbeiterliste. Die ClickUp-Task-IDs und -Links bleiben am Projekt (`clickup`, `notizen`).

Aufruf:

    python3 -I clickup_to_projektbuch.py <clickup-export-dir> <v2-konfig-dir> <v1-konfig-dir> out.json pruefbericht.md

- `<clickup-export-dir>`: je Liste `<list_id>.json` (Array von Tasks), dazu `fields_master.json`
  und optional `raw/enr_*.json` mit Custom-Field-Werten.
- `<v2-konfig-dir>`: `konfig`-Dokumente der Team-DB des Projektbuchs (Leistungskatalog, Pakete, Listen …).
- `<v1-konfig-dir>`: `konfig/mitarbeiter.json` mit den echten Mitarbeitenden und ihren ClickUp-IDs.

Exporte und erzeugte Importdateien enthalten Kundendaten und gehören nicht ins Repository.

## Übernommene Annahmen (21.10.2026)

- ClickUp-Feld „EA“ = Endabnahme (wie in der ClickUp-SOP). Das Feld `ea` heißt im Katalog „Endabnahme“,
  das doppelte Feld `abnahme` entfällt im Paket „Abschluss“.
- ClickUp-Werte ohne Gegenstück kommen in den Katalog: WSN „Warten auf“, BLE „Benötigt“, LDK „Pläne korrigieren“.
  „Offen aber warten“ → „Warten auf“, „Klärung Frank“ → „Klärung GF“.
- Tasks mit gleicher Projektnummer werden ein Projekt (auch bei abweichendem Namen, siehe Prüfbericht).
- To-Do-Listen und Unteraufgaben ohne Projektnummer werden nicht übernommen.
- Felder erledigter Phasen gelten als erledigt; abgeschlossene Projekte haben keine offenen Leistungen.
  Aktive Projekte ohne Custom-Field-Daten tragen das Schlagwort „ClickUp-Felder prüfen“.

## Bestätigte Korrekturen (21.10.2026)

- 26265: Bauort Wobbenbüll.
- 24142: zwei Aufträge, ein Projekt (Dan Concept – Jannek Schumacher – Heist, Teilprojekte Wohnhaus/Garage).
- 20455 und 22355 (mehrere Häuser unter einer Nummer) sowie 20392: als Teilprojekte; Stand je Haus in der Projektnotiz.
