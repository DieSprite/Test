# cookidoo-mcp

MCP-Server, mit dem Claude (Desktop oder Code) auf dein **Thermomix-Cookidoo-Konto** zugreifen kann:
Rezepte suchen, Einkaufsliste pflegen, Wochenplan planen, Sammlungen verwalten, eigene Rezepte anlegen.

> Inoffizielles Projekt, nicht mit Vorwerk/Thermomix/Cookidoo verbunden. Es nutzt die
> inoffizielle Bibliothek [cookidoo-api](https://github.com/miaucl/cookidoo-api), auf der auch die
> Home-Assistant-Integration aufbaut. Ändert Vorwerk etwas an Cookidoo, kann es ausfallen.

## Was er kann

| Bereich | Werkzeuge |
|---|---|
| Lesen | `account_info`, `search_recipes`, `get_recipe`, `list_custom_recipes`, `get_custom_recipe`, `get_shopping_list`, `get_meal_plan`, `list_collections` |
| Einkaufsliste | `add_recipes_to_shopping_list`, `add_meal_plan_to_shopping_list` (ganze Woche auf einmal, ohne Doppelte), `add_shopping_items`, `set_shopping_items_owned` (abhaken), `remove_recipes_from_shopping_list`, `remove_shopping_items` |
| Wochenplan | `plan_recipes`, `move_planned_recipe`, `unplan_recipe` |
| Sammlungen | `create_collection`, `add_recipes_to_collection`, `remove_recipe_from_collection` |
| Eigene Rezepte | `copy_recipe_to_custom`, `create_custom_recipe`, `update_custom_recipe`, `preview_custom_recipe` – **mit Guided Cooking** (siehe unten) |
| Löschen (nur wenn freigeschaltet) | `clear_shopping_list`, `delete_custom_recipe`, `delete_collection` |

Offizielle Rezepte und eigene Rezepte werden automatisch an der ID erkannt (`r59322` = offiziell).

## Sicherheit

| | dieser Server | alexandrepa/mcp-cookidoo | vitaliemiron/cookidoo-mcp |
|---|---|---|---|
| TLS-Zertifikate geprüft | **ja** | nein (`verify_ssl=False`) | nein (`ssl=False`) |
| Passwort auf der Festplatte | **nein** – nur einmal beim Login eingegeben, gespeichert wird nur das Token (Dateirechte 600) | ja, Klartext in `.env` | ja, Klartext in `.env` |
| Nur-Lesen-Modus | **ja** (`COOKIDOO_READ_ONLY=1`) | nein | nein |
| Löschen | aus, bis `COOKIDOO_ALLOW_DELETE=1`, dann zusätzlich `confirm=true` je Aufruf | – | – |
| MCP-Hinweise (lesend / verändernd / löschend) | ja, Claude fragt bei Änderungen nach | nein | nein |
| IDs vor dem Senden geprüft | ja (keine Pfad-Tricks in URLs) | nein | nicht geprüft |
| Fehlermeldungen ohne Server-Antworten/Tokens | ja | nein | nicht geprüft |
| Ausgaben auf stdout (stören das MCP-Protokoll) | nein, alles auf stderr | ja | nein |
| Versionen festgeschrieben | ja, `uv.lock` mit Prüfsummen | nein | teilweise |
| Standard-Land | Deutschland (`de` / `de-DE`) | Frankreich (fest) | Rumänien/Englisch |
| Rezeptsuche | ja | nein | nein |
| Einkaufsliste schreiben | ja | nein | nein |

Außerdem weist der Server Claude an, Rezepttexte und Listeneinträge nur als Daten zu behandeln (Schutz gegen
„Prompt Injection“ über fremde Rezepte).

## Einrichtung Schritt für Schritt

### 1. uv installieren (einmalig)

`uv` installiert Python und genau die festgeschriebenen Paketversionen.

- **macOS / Linux:** `curl -LsSf https://astral.sh/uv/install.sh | sh`
- **Windows (PowerShell):** `powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"`

Danach das Terminal neu öffnen.

### 2. Code holen und installieren

```bash
git clone -b claude/cookidoo-mcp https://github.com/DieSprite/Test.git
cd Test/cookidoo-mcp
uv sync --frozen
```

Ohne Git: auf GitHub den Branch `claude/cookidoo-mcp` wählen → „Code“ → „Download ZIP“, entpacken,
im Terminal in den Ordner `cookidoo-mcp` wechseln und `uv sync --frozen` ausführen.

`--frozen` installiert exakt die Versionen aus `uv.lock` (mit Prüfsummen) – nichts Neueres, Ungeprüftes.

### 3. Einmal anmelden

```bash
uv run cookidoo-mcp login
```

E-Mail und Passwort eingeben. Das Passwort wird **nicht** gespeichert, nur das Anmelde-Token:

- macOS: `~/Library/Application Support/cookidoo-mcp/token.json`
- Windows: `%APPDATA%\cookidoo-mcp\token.json`
- Linux: `~/.config/cookidoo-mcp/token.json`

Prüfen mit `uv run cookidoo-mcp status`.

### 4. In Claude Desktop eintragen

Claude Desktop → Einstellungen → Entwickler → Konfiguration bearbeiten (`claude_desktop_config.json`):

**macOS**
```json
{
  "mcpServers": {
    "cookidoo": {
      "command": "/Users/DEINNAME/Test/cookidoo-mcp/.venv/bin/cookidoo-mcp",
      "args": ["serve"]
    }
  }
}
```

**Windows**
```json
{
  "mcpServers": {
    "cookidoo": {
      "command": "C:\\Users\\DEINNAME\\Test\\cookidoo-mcp\\.venv\\Scripts\\cookidoo-mcp.exe",
      "args": ["serve"]
    }
  }
}
```

Claude Desktop komplett beenden und neu starten. Unter dem Werkzeug-Symbol erscheint „cookidoo“.

**Claude Code** statt Desktop:
```bash
claude mcp add cookidoo -- /PFAD/ZU/Test/cookidoo-mcp/.venv/bin/cookidoo-mcp serve
```

### 5. Ausprobieren

- „Welche Rezepte stehen diese Woche in meinem Cookidoo-Plan?“
- „Setz alles aus dem Wochenplan auf die Einkaufsliste.“
- „Such mir drei vegetarische Rezepte unter 30 Minuten ohne Pilze und plane sie für Mo–Mi.“
- „Kopiere r59322 in meine Rezepte und mach es für 2 Personen.“
- „Leg mir ein Guided-Cooking-Rezept für Pizzateig an und zeig mir vorher die Schritte.“

## Einstellungen (optional)

Als `"env": { ... }` im Eintrag der Claude-Desktop-Konfiguration:

| Variable | Standard | Bedeutung |
|---|---|---|
| `COOKIDOO_COUNTRY` | `de` | Land (z. B. `at`, `ch`) |
| `COOKIDOO_LANGUAGE` | `de-DE` | Sprache (z. B. `de-AT`, `de-CH`) |
| `COOKIDOO_READ_ONLY` | aus | `1` = nur lesende Werkzeuge |
| `COOKIDOO_ALLOW_DELETE` | aus | `1` = Lösch-Werkzeuge freischalten |
| `COOKIDOO_TOKEN_FILE` | siehe oben | anderer Speicherort für das Token |
| `COOKIDOO_EMAIL` / `COOKIDOO_PASSWORD` | – | Nur falls automatischer Neu-Login gewünscht ist, wenn das Token abläuft. **Nicht empfohlen** (Passwort steht dann in der Konfiguration). Lieber bei Bedarf `cookidoo-mcp login` erneut ausführen. |

Beispiel nur lesen:
```json
"cookidoo": {
  "command": "…/cookidoo-mcp",
  "args": ["serve"],
  "env": { "COOKIDOO_READ_ONLY": "1" }
}
```

## Fehlerbehebung

- **„Not logged in“ / „rejected the stored login“** → `uv run cookidoo-mcp login`, dann Claude neu starten.
- **Abmelden / Token löschen** → `uv run cookidoo-mcp logout`
- **Logs** → Claude Desktop: Einstellungen → Entwickler → Logs öffnen (`mcp-server-cookidoo.log`).

## Guided Cooking

Eigene Rezepte können Schritte enthalten, die der Thermomix (TM6/TM7) direkt übernimmt –
wie bei offiziellen Rezepten:

| Schritt-Art | Beispiel (so übergibt Claude ihn) | Ergebnis im Rezept |
|---|---|---|
| Text | `"Zwiebel halbieren."` | normaler Schritt |
| Zutat wiegen | `{kind: "ingredient", ingredient: "200 g Mehl"}` | „200 g Mehl in den Mixtopf geben.“ – Waage zeigt 200 g |
| Einstellungen | `{kind: "settings", text: "Zwiebel {settings} zerkleinern.", time_seconds: 5, speed: "5"}` | „Zwiebel **5 Sek./Stufe 5** zerkleinern.“ – antippbar |
| mit Hitze/Linkslauf | `{kind: "settings", time_seconds: 180, temperature_c: 120, reverse: true, speed: "1"}` | „**3 Min./120°C/Linkslauf/Stufe 1**“ |
| Modus | `{kind: "mode", mode: "DOUGH", time_seconds: 120}` | „**Teig kneten 2 Min.**“ |

Modi: `DOUGH` (Teig kneten), `TURBO`, `BLEND` (Mixen), `WARM_UP` (Aufwärmen), `STEAMING` (Dampfgaren),
`BROWNING` (Anbraten), `RICE_COOKER` (Reis kochen).

Der Server schreibt die Einstellung selbst in den Text und berechnet die Markierung
(Cookidoo zählt in UTF-16-Zeichen – das ist bei anderen Servern eine häufige Fehlerquelle).
Unmögliche Kombinationen werden vorher abgelehnt (z. B. Hitze über Stufe 6, Turbo länger als 2 Sek.).
Mit `preview_custom_recipe` sieht man vorab genau, was gespeichert würde – ohne etwas zu ändern.

Das Datenformat stammt aus dem gegen Cookidoo geprüften Beispiel von
[vitaliemiron/cookidoo-mcp](https://github.com/vitaliemiron/cookidoo-mcp) (Apache-2.0); die Tests prüfen,
dass dieser Server für dieselben Texte exakt dieselben Positionen berechnet.

## Grenzen

- Nicht gegen ein echtes Konto getestet: Die automatischen Tests (`uv run pytest`) prüfen die Logik mit einem
  simulierten Cookidoo. Beim ersten Einsatz bitte mit Lesen beginnen.
- Anlegen und Bearbeiten eigener Rezepte nutzt die (undokumentierte) Schnittstelle des Cookidoo-Web-Editors
  und zwei interne Hilfsfunktionen von cookidoo-api; deshalb ist cookidoo-api auf `<0.19` begrenzt.
- Die Filterwerte `medium` und `advanced` beim Schwierigkeitsgrad sind nicht verifiziert (nur `easy`).
- Guided Cooking ist nicht mit einem echten Konto getestet. Vor allem die Modi (Teig, Dampfgaren, Anbraten …)
  und deren Texte; bitte zuerst mit einem Testrezept ausprobieren.
- Zutaten wiegen funktioniert nur mit Gramm-Angaben („200 g Mehl“), nicht mit Stück/ml/EL.
- Varoma-Temperatur und Rezept-Fotos werden nicht unterstützt. Guided Cooking ist für TM6/TM7 gedacht.
- Bestehende Guided-Einstellungen eines eigenen Rezepts werden beim Lesen nicht angezeigt
  (cookidoo-api liefert nur den Text); `update_custom_recipe` mit `steps` ersetzt alle Schritte.

## Entwicklung

```bash
uv sync --frozen --extra dev
uv run pytest
```
