#!/usr/bin/env python3
"""ClickUp-Export -> Projektbuch-v2-Import (JSON für Einstellungen > Daten > JSON importieren).

Folgt dem in der App beschriebenen Migrationsweg (Einstellungen > Daten > "Migration aus ClickUp"):
Tasks mit gleicher Projektnummer werden zu einem Projekt zusammengeführt, der Listenstatus
wird zum Wert des Kernfelds, Custom Fields gehen in die gleichnamigen Leistungsfelder,
Fälligkeit/Zuständigkeit/Priorität kommen aus dem jeweiligen Task, die ClickUp-Task-IDs
bleiben am Projekt.

Aufruf: python3 -I clickup_to_projektbuch.py <clickup-dir> <v2-konfig-dir> <v1-konfig-dir> <out.json> <report.md>
"""
import json, os, re, sys, glob, time, datetime as dt
from collections import defaultdict, Counter

CU, KONF2, KONF1, OUT, REPORT = sys.argv[1:6]

def load(p):
    d = json.load(open(p, encoding='utf-8'))
    return d.get('data', d) if isinstance(d, dict) and set(d.keys()) >= {'data'} and len(d) <= 3 else d

fielddefs = load(os.path.join(KONF2, 'felder.json'))['list']
FD = {f['id']: f for f in fielddefs}
# Annahmen (vom Büro übernommen): EA = Endabnahme (wie in der ClickUp-SOP); fehlende ClickUp-Werte
# kommen in den Katalog statt ersetzt zu werden; das doppelte Feld „Abnahme“ entfällt im Paket Abschluss.
ZUSATZ_OPTS = {'wsn': [('Warten auf', 'wait')], 'ble': [('Benötigt', 'open')], 'ldk': [('Pläne korrigieren', 'wait')],
               'plaene': [], 'statik': []}
for f in fielddefs:
    for v, kind in ZUSATZ_OPTS.get(f['id'], []):
        if v not in [o['v'] for o in f.get('opts', [])]:
            pos = next((i for i, o in enumerate(f['opts']) if o['kind'] in ('done', 'na')), len(f['opts']))
            f['opts'].insert(pos, {'v': v, 'kind': kind})
    if f['id'] == 'ea':
        f['label'] = 'Endabnahme'
OPTS = {f['id']: [o['v'] for o in f.get('opts', [])] for f in fielddefs}
packages = load(os.path.join(KONF2, 'pakete.json'))['list']
for pk in packages:
    if pk['id'] == 'abschluss':
        pk['fields'] = [x for x in pk['fields'] if x != 'abnahme']
def final_value(fid):
    """Erledigt-Wert eines Felds (für abgeschlossene Projekte und vorgelagerte Phasen)."""
    d = FD[fid]
    if d.get('type') == 'progress':
        return 100
    for want in ('done', 'na'):
        for o in d.get('opts', []):
            if o['kind'] == want:
                return o['v']
    return None

# ---- Mitarbeiter: echte Liste aus Projektbuch v1 (mit ClickUp-User-IDs), ohne Beispiel-Gast
emps = [e for e in load(os.path.join(KONF1, 'mitarbeiter.json'))['list'] if e.get('role') != 'extern']
CU2EMP = {str(e['clickup']): e['id'] for e in emps if e.get('clickup')}

LIST_SPACE = {
    '21477298': 'kommend', '901524929507': 'kommend',
    '10390841': 'abgeschlossen', '10390832': 'eis',
    '901505350907': 'statik', '901505350881': 'plaene', '901505350932': 'bauphy', '901505512584': 'abschluss',
    '901505542696': 'kfw', '901505542713': 'qng', '901505599051': 'em',
    '901524020540': 'pruef', '901524908509': 'extern',
    '901500366513': 'todo', '901510792882': 'todo', '901513779027': 'todo',
}

def norm(s):
    return re.sub(r'\s+', ' ', str(s or '')).strip()

def pick(field, value, unmapped):
    """Wert auf eine Option des Leistungsfelds abbilden (Groß/Klein, Leerzeichen, Synonyme)."""
    if value is None or value == '':
        return None
    v = norm(value)
    syn = {
        'complete': None, 'vollständig': None,  # werden je Feld unten aufgelöst
        'klärung frank': 'Klärung GF', 'offen aber warten': 'Warten auf', 'warten auf': 'Warten auf',
        'nicht raus': 'Nicht raus', 'raus': 'Raus', 'angefordert': 'Angefordert',
        'bnd & doku': 'BnD & Doku', 'korrektur': 'Korrektur Statik',
        'angebot ist raus': 'Angebot raus', 'to do': 'Offen', 'open': 'Offen',
    }
    opts = OPTS.get(field, [])
    for o in opts:
        if o.lower() == v.lower():
            return o
    s = syn.get(v.lower())
    if s and s in opts:
        return s
    if v.lower() in ('complete', 'vollständig', 'closed', 'erledigt'):
        for cand in ('Complete', 'Fertig', 'Zertifiziert', 'Durchgeführt', 'Raus', 'Bezahlt', 'Vollständig', 'Beauftragt'):
            if cand in opts:
                return cand
    unmapped[(field, v)] += 1
    return None

def optKindOf(fid, v):
    for o in FD[fid].get('opts', []):
        if o['v'] == v:
            return o['kind']
    return 'open'

def ms2iso(x):
    if x in (None, '', 0):
        return None
    try:
        return dt.datetime.fromtimestamp(int(x) / 1000, dt.timezone.utc).astimezone().date().isoformat()
    except Exception:
        return None

def cf_value(cf):
    """Custom-Field-Wert lesbar machen (Dropdown -> Optionsname)."""
    if 'value_name' in cf:
        return cf['value_name']
    v = cf.get('value')
    t = cf.get('type')
    if v is None:
        return None
    if t == 'drop_down':
        opts = (cf.get('type_config') or {}).get('options') or cf.get('options') or []
        for o in opts:
            if str(o.get('id')) == str(v) or str(o.get('orderindex')) == str(v):
                return norm(o.get('name'))
        return norm(v) if isinstance(v, str) and not re.fullmatch(r'[0-9a-f-]{36}|\d+', v) else None
    if t == 'date':
        return ms2iso(v)
    if t == 'location':
        return v if isinstance(v, dict) else {'formatted_address': str(v)}
    if t == 'labels':
        return v
    return v

# ClickUp-Custom-Field-Name -> Leistungsfeld
CF2FIELD = {
    'bodengutachten': 'bodengutachten', 'dxf': 'dxf', 'zeichendatei': 'dxf', 'ausführungsp': 'ausfP',
    'ble': 'ble', 'bew.abn': 'bewAbn', 'wsn': 'wsn', 'wbn': 'wbn', 'ldk': 'ldk', 'heizlast': 'heizlast',
    'schall': 'schall', 'barrierefreiheit': 'barrierefrei', 'lca': 'lca', 'ea': 'ea',
    'abnahmeschein raus': 'abnahmeschein', 'abnahmeschein': 'abnahmeschein',
    'rechnung ea': 'rechnungEA', 'rechnung bew': 'rechnungBew', 'rechnung kfw': 'schlussrechnung',
    'statik': 'statik', 'blower-door': 'blowerDoor', 'blower door': 'blowerDoor',
    'kfw unterlagen': 'kfwUnterlagen', 'unterlagen': 'kfwUnterlagen', 'qng unterlagen': 'qngUnterlagen',
    'unterlagen raus': 'unterlagenRaus', 'gebäudehandbuch': 'gebaeudehandbuch', 'ressourcenpass': 'ressourcenpass',
    'lcc': 'lcc', 'steckbriefe': 'steckbriefe', 'pläne': 'plaene',
}
DATEFIELDS = {'vot': 'vot', 'nachfragen ab': 'nachfragen'}

# Liste -> Kernfeld, das den Listenstatus trägt; vorgelagerte Felder gelten als erledigt
CORE = {'statik': 'statik', 'plaene': 'plaene', 'bauphy': 'wsn', 'abschluss': None,
        'kfw': 'foerderphase', 'qng': 'qngProzess', 'em': 'emProzess', 'kommend': 'angebot'}
BEFORE = {'plaene': ['statik'], 'bauphy': ['statik', 'plaene'], 'abschluss': ['statik', 'plaene', 'wsn']}
PAKETE = {'statik': ['statik', 'bauphysik', 'abschluss'], 'plaene': ['statik', 'bauphysik', 'abschluss'],
          'bauphy': ['statik', 'bauphysik', 'abschluss'], 'abschluss': ['statik', 'bauphysik', 'abschluss'],
          'kfw': ['kfw'], 'qng': ['kfw', 'qng'], 'em': ['em'], 'kommend': ['anfrage']}
PRIO = {'urgent': 'dringend', 'high': 'hoch', 'normal': 'normal', 'low': 'niedrig', 1: 'dringend', 2: 'hoch', 3: 'normal', 4: 'niedrig'}

def parse_name(name):
    m = re.match(r'\s*(\d{4,6}(?:[-/.]\d+)?)\s*(.*)$', name or '')
    if not m:
        return None, {}
    nr, rest = m.group(1), m.group(2)
    info = ''
    mi = re.search(r'\(([^)]*)\)\s*$', rest)
    if mi:
        info = mi.group(1).strip(); rest = rest[:mi.start()].strip()
    parts = [p.strip() for p in re.split(r'\s+-\s+', rest) if p.strip()]
    firma = bauherr = ort = ''
    if len(parts) >= 3:
        firma, bauherr, ort = parts[0], parts[1], ' - '.join(parts[2:])
    elif len(parts) == 2:
        firma, ort = parts
        bauherr = firma
    elif len(parts) == 1:
        firma = bauherr = parts[0]
    for x in ('Bauherr', 'Bh', 'BH'):
        if firma.startswith(x + ' ') or firma == x:
            bauherr = firma[len(x):].strip() or bauherr
            firma = 'Bauherr' if firma == x else bauherr
    return nr, {'firma': firma, 'bauherr': bauherr, 'ort': ort, 'info': info}

def task_status(t):
    s = t.get('status')
    if isinstance(s, dict):
        return norm(s.get('status')), s.get('type')
    return norm(s), None

def assignees(t):
    out = []
    for a in t.get('assignees') or []:
        e = CU2EMP.get(str(a.get('id')))
        if e and e not in out:
            out.append(e)
    return out

# ---- Tasks laden
tasks = []
for f in sorted(glob.glob(os.path.join(CU, '*.json'))):
    base = os.path.basename(f)
    if not re.fullmatch(r'\d+\.json', base):
        continue
    data = json.load(open(f, encoding='utf-8'))
    if isinstance(data, dict):
        data = data.get('tasks') or data.get('items') or []
    for t in data:
        if isinstance(t, dict) and 'data' in t and isinstance(t['data'], dict):
            t = t['data']
        t.setdefault('list', {}).setdefault('id', base[:-5])
        tasks.append(t)

# Custom Fields aus der Anreicherung (kompakt: [id, date_created, start, ?, ?, [[cf_id, wert], …]])
master = json.load(open(os.path.join(CU, 'fields_master.json'), encoding='utf-8'))
enr = {}
for f in glob.glob(os.path.join(CU, 'raw', 'enr_*.json')):
    d = json.load(open(f, encoding='utf-8'))
    if not isinstance(d, list):
        continue
    for row in d:
        if not (isinstance(row, list) and row):
            continue
        cfs = []
        for pair in (row[5] if len(row) > 5 and row[5] else []):
            m = master.get(pair[0])
            if not m:
                continue
            v = pair[1]
            if m.get('type') == 'drop_down':
                v = (m.get('options') or {}).get(str(v))
                cfs.append({'name': m['name'], 'type': 'text', 'value': v})
            else:
                cfs.append({'name': m['name'], 'type': m.get('type'), 'value': v})
        enr[row[0]] = {'date_created': row[1], 'custom_fields': cfs}
for t in tasks:
    e = enr.get(t.get('id'))
    if e:
        t.setdefault('date_created', e['date_created'])
        t['custom_fields'] = e['custom_fields']
ENRICHED = sum(1 for t in tasks if t.get('custom_fields') is not None)

unmapped = Counter()
skipped = []
groups = defaultdict(list)
for t in tasks:
    lid = str((t.get('list') or {}).get('id') or '')
    kind = LIST_SPACE.get(lid, 'unbekannt')
    if kind == 'todo':
        skipped.append((t.get('name'), 'To-Do-Liste (keine Projektliste)'))
        continue
    if t.get('parent'):
        skipped.append((t.get('name'), 'Unteraufgabe'))
        continue
    nr, head = parse_name(t.get('name'))
    if not nr:
        skipped.append((t.get('name'), 'keine Projektnummer im Namen'))
        continue
    if kind in ('pruef', 'extern'):
        t.setdefault('tags', []).append({'name': 'Prüfprojekt' if kind == 'pruef' else 'Externer Energieberater'})
    groups[nr].append((kind, t, head))

TODAY = dt.date.today().isoformat()
projects = []
notes_report = []

def empty_field(fid):
    d = FD[fid]
    f = {'value': None, 'due': None, 'start': None, 'prio': 'normal', 'assignee': None, 'note': '', 'done': False,
         'updatedAt': int(time.time() * 1000)}
    if d.get('type') in ('number', 'progress'):
        f['value'] = 0
    elif d.get('type') == 'select' and d.get('opts'):
        f['value'] = d['opts'][0]['v']
    return f

DONE_VAL = {'statik': 'Fertig', 'plaene': 'Fertig', 'wsn': 'Fertig'}

for nr, items in sorted(groups.items()):
    # Kopf: bevorzugt Standard-/Förder-Task (aktuellster) für Namen
    items.sort(key=lambda x: int(x[1].get('date_updated') or 0), reverse=True)
    kinds = {k for k, _, _ in items}
    head = items[0][2]
    p = {'id': 'p' + re.sub(r'[^A-Za-z0-9_\-.~:@+]', '-', nr), 'nr': nr,
         'firma': head['firma'], 'bauherr': head['bauherr'], 'ort': head['ort'], 'adresse': '',
         'typ': 'qng' if 'qng' in kinds else 'foerderung' if 'kfw' in kinds else 'einzelmassnahme' if 'em' in kinds else 'standard',
         'kfw': '', 'we': 0, 'kompl': 'B', 'leiter': None, 'status': 'aktiv', 'pakete': [], 'fields': {},
         'tags': [], 'teile': [], 'createdAt': None, 'closedAt': None, 'plancraftId': '', 'ordner': '',
         'email': '', 'telefon': '', 'notizen': '', 'kopf': {}, 'vorlage': '', 'beteiligte': [], 'gewerke': [],
         'clickup': []}
    if head.get('info'):
        p['tags'].append(head['info'][:40])
    created = []
    open_tasks = 0
    for kind, t, h in items:
        st, stype = task_status(t)
        closed = bool(t.get('date_closed')) or stype in ('closed', 'done')
        if not closed:
            open_tasks += 1
        p['clickup'].append({'id': t.get('id'), 'liste': (t.get('list') or {}).get('name'), 'status': st, 'url': t.get('url')})
        if t.get('date_created'):
            created.append(ms2iso(t['date_created']))
        for pk in PAKETE.get(kind, []):
            if pk not in p['pakete']:
                p['pakete'].append(pk)
        for tg in t.get('tags') or []:
            n = tg.get('name') if isinstance(tg, dict) else str(tg)
            if n and n not in p['tags']:
                p['tags'].append(n)
        ass = assignees(t)
        if ass and not p['leiter']:
            p['leiter'] = ass[0]
        # Felder der Pakete anlegen
        for pk in PAKETE.get(kind, []):
            pack = next((x for x in packages if x['id'] == pk), None)
            for fid in (pack or {}).get('fields', []):
                if fid in FD and fid not in p['fields']:
                    p['fields'][fid] = empty_field(fid)
        # vorgelagerte Phasen erledigt
        for fid in BEFORE.get(kind, []):
            if fid in p['fields']:
                p['fields'][fid]['value'] = DONE_VAL[fid]
        # Kernfeld aus dem Listenstatus
        core = CORE.get(kind)
        if core and core in p['fields']:
            raw = 'complete' if closed else st
            if kind == 'qng' and raw.lower() not in [o.lower() for o in OPTS['qngProzess']] and 'foerderphase' in p['fields']:
                core = 'foerderphase'   # QNG-Liste nutzt dieselben Phasen wie KfW (Stand?, Unterlagen, BnD & Doku …)
            val = pick(core, raw, Counter())
            f = p['fields'][core]
            if val:
                f['value'] = val
            else:
                f['note'] = ('ClickUp-Status: ' + raw)[:120]   # z. B. „Warten auf“ in Bauphy – Wert bleibt sichtbar
                unmapped[(core + ' (als Info übernommen)', raw)] += 1
            f['due'] = ms2iso(t.get('due_date'))
            f['start'] = ms2iso(t.get('start_date'))
            f['assignee'] = ass[0] if ass else None
            f['prio'] = PRIO.get((t.get('priority') or {}).get('priority') if isinstance(t.get('priority'), dict) else t.get('priority'), 'normal')
        elif kind == 'abschluss':
            # Liste "Abnahme & Bescheinigung": Status steckt in EA / Abnahmeschein / Blower-Door
            ab = {'offen': {}, 'abnahme': {'ea': 'Stand?'},
                  'abnahmeschein bearbeitung': {'ea': 'Durchgeführt', 'abnahmeschein': 'In Bearbeitung'},
                  'energieausweis': {'ea': 'Durchgeführt', 'abnahmeschein': 'Raus'},
                  'blower-door': {'ea': 'Durchgeführt', 'abnahmeschein': 'Raus', 'blowerDoor': 'Eingeplant'}}
            st_l = 'complete' if closed else st.lower()
            werte = ab.get(st_l)
            if werte is None:
                werte = {'bewAbn': 'Durchgeführt', 'ea': 'Durchgeführt', 'abnahmeschein': 'Raus', 'blowerDoor': 'Bestanden', 'rechnungBew': 'Bezahlt', 'rechnungEA': 'Bezahlt'}
                if st_l != 'complete':
                    unmapped[('Abschluss-Status', st)] += 1
            for fid, v in werte.items():
                if fid in p['fields']:
                    p['fields'][fid]['value'] = v
            focus = next((fid for fid in ('blowerDoor', 'abnahmeschein', 'ea') if fid in werte), 'ea')
            if focus in p['fields'] and not closed:
                p['fields'][focus]['due'] = ms2iso(t.get('due_date'))
                p['fields'][focus]['assignee'] = ass[0] if ass else None
        # Custom Fields
        for cf in t.get('custom_fields') or []:
            name = norm(cf.get('name')).lower()
            val = cf_value(cf)
            if val in (None, '', []):
                continue
            if name == 'we':
                try: p['we'] = max(p['we'], int(float(val)))
                except Exception: pass
            elif name == 'kfw':
                p['kfw'] = norm(val)
            elif name in ('bauort', 'adresse'):
                if isinstance(val, dict):
                    p['adresse'] = val.get('formatted_address') or p['adresse']
                    loc = val.get('location') or {}
                    if loc.get('lat') is not None:
                        p['lat'], p['lng'] = loc.get('lat'), loc.get('lng')
                else:
                    p['adresse'] = norm(val)
            elif name in ('e-mail', 'email'):
                p['email'] = norm(val)
            elif name == 'abrechnung bb':
                try: p['fields'].setdefault('abrechnungBB', empty_field('abrechnungBB'))['value'] = float(val)
                except Exception: pass
            elif name == 'schlussrechnung':
                v = pick('schlussrechnung', val, unmapped)
                if v: p['fields'].setdefault('schlussrechnung', empty_field('schlussrechnung'))['value'] = v
            elif name in DATEFIELDS:
                fid = DATEFIELDS[name]
                p['fields'].setdefault(fid, empty_field(fid))['value'] = val if isinstance(val, str) else ms2iso(val)
            elif name in CF2FIELD:
                fid = CF2FIELD[name]
                if FD[fid].get('type') == 'number':
                    try: p['fields'].setdefault(fid, empty_field(fid))['value'] = float(val)
                    except Exception: pass
                    continue
                v = pick(fid, val, unmapped)
                if v:
                    p['fields'].setdefault(fid, empty_field(fid))['value'] = v
            else:
                unmapped[('custom field', norm(cf.get('name')))] += 1
    p['createdAt'] = min([c for c in created if c] or [TODAY])
    p['fields'].pop('abnahme', None)
    known = set()   # Felder, deren Wert wirklich aus ClickUp stammt
    for kind, t, h in items:
        known |= {CF2FIELD.get(norm(cf.get('name')).lower()) for cf in (t.get('custom_fields') or []) if cf.get('value') not in (None, '')}
    reihenfolge = ['kommend', 'statik', 'plaene', 'bauphy', 'abschluss']
    stufe = max([reihenfolge.index(k) for k in kinds if k in reihenfolge] or [-1])
    erledigt_gruppen = set()
    if stufe >= 2: erledigt_gruppen |= {'bodengutachten', 'dxf'}           # Statik ist gerechnet
    if stufe >= 4: erledigt_gruppen |= {'wsn', 'wbn', 'ldk', 'heizlast', 'schall', 'barrierefrei', 'plaene', 'statik'}
    for fid in erledigt_gruppen:
        if fid in p['fields'] and fid not in known:
            p['fields'][fid]['value'] = final_value(fid)
    hat_cf = any(t.get('custom_fields') is not None for _, t, _ in items)
    if 'abgeschlossen' in kinds or (open_tasks == 0 and items):
        p['status'] = 'abgeschlossen'
        for fid, f in p['fields'].items():
            if fid not in known and FD[fid].get('type') in ('select', 'progress'):
                v = final_value(fid)
                if v is not None and optKindOf(fid, f['value']) not in ('done', 'na'):
                    f['value'] = v
        closed_dates = [ms2iso(t.get('date_closed')) for _, t, _ in items if t.get('date_closed')]
        p['closedAt'] = max([c for c in closed_dates if c] or [TODAY])
    elif 'eis' in kinds:
        p['status'] = 'eis'
    elif kinds <= {'kommend'}:
        p['status'] = 'anfrage'
    if not p['pakete']:
        p['pakete'] = []
    if p['status'] in ('aktiv', 'wartend') and not hat_cf:
        p['tags'].append('ClickUp-Felder prüfen')
    p['leiter'] = p['leiter'] or 'dennis'
    for fid, f in p['fields'].items():
        if f['assignee'] is None and FD[fid].get('role') == 'gf':
            f['assignee'] = p['leiter']
    p['notizen'] = 'Aus ClickUp übernommen am ' + TODAY + ':\n' + '\n'.join(
        '- ' + (c['liste'] or '') + ' · ' + (c['status'] or '') + ' · ' + (c['url'] or '') for c in p['clickup'])
    if p['bauherr']:
        p['beteiligte'].append({'id': 'bh_' + p['id'], 'rolle': 'Bauherr', 'name': p['bauherr'], 'firma': '', 'telefon': '', 'email': '', 'notiz': ''})
    if len(items) > 1 and len({h['ort'] for _, _, h in items}) > 1:
        notes_report.append(nr + ': unterschiedliche Namen in ClickUp – ' + ' | '.join(t.get('name') for _, t, _ in items))
    projects.append(p)

state = {
    'meta': {'version': 5, 'created': int(time.time() * 1000), 'updated': int(time.time() * 1000), 'seeded': None,
             'quelle': 'ClickUp-Übernahme ' + TODAY},
    'employees': emps,
    'fieldDefs': fielddefs,
    'packages': packages,
    'templates': load(os.path.join(KONF2, 'vorlagen.json'))['list'],
    'plankopf': load(os.path.join(KONF2, 'plankopf.json'))['list'],
    'views': load(os.path.join(KONF2, 'listen.json'))['list'],
    'dashboardsCustom': [],
    'settings': load(os.path.join(KONF2, 'einstellungen.json')),
    'projects': projects, 'timeEntries': [], 'activity': [], 'comments': [],
    'timers': {}, 'dashboards': {}, 'notes': {}, 'events': [],
    'currentUserId': 'dennis', 'theme': None,
}
json.dump(state, open(OUT, 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))

st = Counter(p['status'] for p in projects)
ty = Counter(p['typ'] for p in projects)
with open(REPORT, 'w', encoding='utf-8') as r:
    r.write('# ClickUp-Übernahme – Prüfbericht\n\n')
    r.write(f'- Tasks mit Zusatzfeldern (Custom Fields): {ENRICHED} von {len(tasks)}\n')
    r.write(f'- Tasks gelesen: {len(tasks)}\n- Projekte erzeugt: {len(projects)}\n')
    r.write('- Status: ' + ', '.join(f'{k} {v}' for k, v in st.most_common()) + '\n')
    r.write('- Typ: ' + ', '.join(f'{k} {v}' for k, v in ty.most_common()) + '\n')
    r.write(f'- Übersprungen: {len(skipped)}\n\n## Nicht zuordenbare Werte\n\n')
    for (f, v), n in unmapped.most_common():
        r.write(f'- {f}: „{v}“ ({n}×)\n')
    r.write('\n## Übersprungene Tasks\n\n')
    for n, why in skipped:
        r.write(f'- {n} – {why}\n')
    r.write('\n## Hinweise\n\n')
    for n in notes_report:
        r.write(f'- {n}\n')
print(len(tasks), 'tasks ->', len(projects), 'projects;', len(skipped), 'skipped;', sum(unmapped.values()), 'unmapped values')
