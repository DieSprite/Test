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
