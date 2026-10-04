# Zeit-Overlay

Ein kleines Timer-Fenster, das immer über allen Programmen liegt. Es zeigt das laufende
Projekt, die Aktivität und die Dauer. Im Ruhezustand ist es zu 70 % durchsichtig und lässt
alle Mausklicks an das Programm darunter durch.

**Strg gedrückt halten:** Das Overlay wird voll sichtbar und lässt sich anklicken.

## Bedienung

| Was | Wie |
| --- | --- |
| Overlay anklickbar machen | **Strg** gedrückt halten. Wer Strg über dem Overlay loslässt, kann weiterklicken, bis die Maus das Overlay verlässt. |
| Dauerhaft anklickbar (anheften) | **Strg+Alt+T**, erneut drücken löst es wieder. Alternativ ein Klick auf das Symbol im Infobereich. |
| Timer stoppen | Stopp-Knopf (schwarzes Quadrat). Die Zeit wird sofort gebucht. |
| Timer starten | Start-Knopf setzt das zuletzt genutzte Projekt fort. Für etwas anderes den Pfeil daneben nutzen. |
| Projekt wechseln | Pfeil-Knopf → Projekt suchen → Aktivität wählen. Ein laufender Timer wird dabei gebucht und der neue gestartet. |
| Verschieben | Bei anklickbarem Overlay an der gepunkteten Leiste links ziehen. Die Position bleibt gespeichert. |
| Einstellungen, Beenden | Rechtsklick auf das Uhr-Symbol im Infobereich der Taskleiste. |

Strg+C, Strg+V und andere Kombinationen lösen das Overlay **nicht** aus. Nur Strg allein zählt.

## Einrichtung mit ClickUp

1. In ClickUp: Avatar unten links → **Einstellungen** → **Apps** → **API-Token generieren**.
   Das Token beginnt mit `pk_`.
2. Im Zeit-Overlay: Rechtsklick auf das Uhr-Symbol → **Einstellungen**.
3. Anbieter **ClickUp** wählen, Token einfügen, **Workspaces laden**, Workspace wählen.
4. Optional die Spaces ankreuzen, in denen die Projekte liegen. Ohne Auswahl werden alle angezeigt.
5. **Speichern**.

Zuordnung in ClickUp:

- **Projekt** = ClickUp-Liste (in der Auswahl nach Space und Ordner gruppiert)
- **Aktivität** = Aufgabe in dieser Liste
- Gebucht wird als normaler ClickUp-Zeiteintrag auf die Aufgabe. Die Notiz landet in der Beschreibung.

Ein Timer, der in ClickUp im Browser gestartet wird, erscheint nach spätestens 30 Sekunden
auch im Overlay, und umgekehrt.

Das Token wird mit der Windows-Kontoverschlüsselung gespeichert, nicht im Klartext.

## Installation

Die fertige Windows-Datei baut GitHub automatisch bei jeder Änderung
(Reiter **Actions** → „Zeit-Overlay Windows-Build“ → Artefakt **Zeit-Overlay-Windows**).
Darin liegen zwei Dateien:

- `Zeit-Overlay x.y.z.exe`: portable Version, läuft ohne Installation.
- `Zeit-Overlay Setup x.y.z.exe`: Installer mit Startmenü-Eintrag.

Die Dateien sind nicht signiert. Windows SmartScreen fragt deshalb beim ersten Start nach:
„Weitere Informationen“ → „Trotzdem ausführen“.

Selbst bauen (Node.js 22 nötig):

```
cd zeit-overlay
npm install
npm start          # direkt starten
npm test           # Tests
npm run dist       # Windows-.exe nach dist/ (unter Windows ausführen)
```

## Aufbau

```
src/main.js              Fenster, Klick-Durchlass, Strg-Erkennung, Infobereich
src/interaction.js       Regeln, wann das Overlay anklickbar ist (getestet)
src/config.js            Einstellungen, verschlüsseltes Token
src/providers/clickup.js ClickUp-API (getestet)
src/providers/demo.js    Demo-Daten zum Ausprobieren
src/renderer/            Oberfläche Overlay und Einstellungen (Corporate Design)
```

## Wechsel zum Projektbuch

Das Overlay spricht nur über eine schmale Anbieter-Schnittstelle mit der Zeiterfassung
(`src/providers/index.js`): Projekte holen, Aktivitäten holen, laufenden Timer lesen,
starten, stoppen. Für das Projektbuch kommt ein weiterer Anbieter dazu, Oberfläche und
Bedienung bleiben gleich.

Das Projektbuch kennt bereits dieselben Begriffe: Timer mit Projekt, Leistung (= Aktivität),
Notiz und Startzeit. Offen ist nur der Zugriffsweg: Das Overlay braucht eine Schnittstelle,
über die es die Projekte lesen und Timer setzen kann.
