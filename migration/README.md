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

## Vollständige Felddaten und Katalog-Ausbau (21.10.2026)

- Custom Fields aller offenen Projekt-Tasks werden über `task.get_many` gelesen (`raw/enr2_*.json`, Format
  `[id, date_created, start_date, parent, [[field_id, wert], …], [adresse, lat, lng]]`); abgeschlossene Tasks
  gelten als erledigt. `fields_master.json` enthält auch die listeneigenen Felder (KfW, QNG, EM, Abschluss).
- Neue Leistungsfelder: TPN (EM), AFP (Statik), Energieausweis und Bildnachweis (Abschluss), Vorzertifikat,
  Termine QS, Abrechnung Zertifizierung (QNG); BNK-Version als eigenes Kopffeld `k_bnk`; „Info Klaus“ in die Projektnotiz.
- LP-Codes: Endabnahme (`ea`) = S5, Energieausweis = E14.
- In der Liste „Abnahme & Bescheinigung“ bedeutet ein leeres Blower-Door/Energieausweis „nicht erforderlich“ (NE),
  außer bei geförderten Projekten.

## Nur aktuelle Projekte (23.10.2026)

Optionales 6. Argument begrenzt auf Projektnummern-Anfänge, z. B. `25,26`. Die älteren Projekte werden erst beim
Wechsel auf die Server-Version nachgeladen.

    python3 -I clickup_to_projektbuch.py <clickup> <v2-konfig> <v1-konfig> out.json pruefbericht.md 25,26

## Zeiteinträge (23.10.2026)

Liest `clickup/zeit/zeit_JJJJ-MM-TT.json` (`[id, user_id, task_id, nr, start, end, duration_ms, [tags], beschreibung]`).
Projekt über die Nummer am Anfang des Task-Namens, Person über die ClickUp-ID in `konfig/mitarbeiter`,
Leistung über den Tag laut „SOP – ClickUp-Pflege für die Leistungsprämie“ (TAG2FIELD im Skript).
Einträge ohne Projektbezug werden gezählt, aber nicht übernommen; die Original-Tags stehen in der Notiz.

Hinweise zum Abruf über den ClickUp-Konnektor: höchstens 50 Einträge je Abfrage; der Datumsfilter liefert nur
Einträge, die vollständig im Zeitfenster liegen (Europe/Berlin) – also tageweise abfragen und bei mehr als 50
nach Personen statt nach Uhrzeit aufteilen. Einträge auf Tasks ohne Lesezugriff lassen sich nicht abrufen.
