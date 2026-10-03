import json, math, os, subprocess, sys
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "wohnmobil.mp4")
W, H = 1920, 1080
FPS = 30
PREVIEW = os.environ.get("PREVIEW")  # e.g. "0,100,300" -> write PNGs only

# ---------- projection ----------
LON0, LON1, LAT0, LAT1 = 3.0, 14.0, 50.7, 56.0
S = 1000.0                      # px per degree latitude on base map
KX = math.cos(math.radians(53.4))
BW = int((LON1 - LON0) * KX * S)
BH = int((LAT1 - LAT0) * S)

def proj(lon, lat):
    return ((lon - LON0) * KX * S, (LAT1 - lat) * S)

# ---------- colours ----------
INK = (20, 18, 24)
PAPER = (250, 238, 200)
SEA = (110, 196, 230)
SEA_DOT = (80, 165, 210)
DE = (255, 214, 102)
DE_DOT = (240, 180, 60)
OTHER = (190, 225, 150)
OTHER_DOT = (160, 200, 120)
RED = (230, 40, 50)
RIVER = (60, 140, 215)

FONT = os.path.join(HERE, "Bangers.ttf")
def font(sz): return ImageFont.truetype(FONT, sz)

# ---------- geo data ----------
def rings(geom):
    if geom["type"] == "Polygon":
        return [geom["coordinates"][0]]
    if geom["type"] == "MultiPolygon":
        return [p[0] for p in geom["coordinates"]]
    return []

def lines(geom):
    if geom["type"] == "LineString":
        return [geom["coordinates"]]
    if geom["type"] == "MultiLineString":
        return geom["coordinates"]
    return []

def in_box(coords, pad=1.0):
    xs = [c[0] for c in coords]; ys = [c[1] for c in coords]
    return not (max(xs) < LON0 - pad or min(xs) > LON1 + pad or max(ys) < LAT0 - pad or min(ys) > LAT1 + pad)

countries = json.load(open(os.path.join(HERE, "countries.geojson")))
land = []
for f in countries["features"]:
    iso = f["properties"].get("ADM0_A3")
    if iso not in ("DEU", "DNK", "NLD", "POL", "SWE", "BEL"):
        continue
    for r in rings(f["geometry"]):
        if in_box(r):
            land.append((iso, [proj(*c) for c in r]))

states = json.load(open(os.path.join(HERE, "states.geojson")))
state_lines = []
for f in states["features"]:
    if f["properties"].get("adm0_a3") != "DEU":
        continue
    for l in lines(f["geometry"]):
        if in_box(l, 0.2):
            state_lines.append([proj(*c) for c in l])

rivers = json.load(open(os.path.join(HERE, "lakes.geojson")))
river_lines = []
for f in rivers["features"]:
    nm = (f["properties"].get("name") or "")
    if nm not in ("Elbe", "Weser", "Aller", "Leine", "Ems", "Eider"):
        continue
    for l in lines(f["geometry"]):
        if in_box(l, 0.2):
            river_lines.append([proj(*c) for c in l])

# ---------- base map ----------
SS = 1  # base map is already high-res
def halftone(size, color, bg, step, r):
    img = Image.new("RGB", size, bg)
    d = ImageDraw.Draw(img)
    for j, y in enumerate(range(0, size[1] + step, step)):
        off = step // 2 if j % 2 else 0
        for x in range(-step, size[0] + step, step):
            d.ellipse((x + off - r, y - r, x + off + r, y + r), fill=color)
    return img

print("base map", BW, BH)
base = halftone((BW, BH), SEA_DOT, SEA, 22, 3)
# wave strokes in the sea
wd = ImageDraw.Draw(base)
rng = np.random.default_rng(7)
for _ in range(260):
    x, y = rng.uniform(0, BW), rng.uniform(0, BH)
    for k in range(2):
        wd.arc((x + k * 34, y, x + 34 + k * 34, y + 22), 200, 340, fill=(240, 250, 255), width=5)

mask_de = Image.new("L", (BW, BH), 0)
mask_ot = Image.new("L", (BW, BH), 0)
md, mo = ImageDraw.Draw(mask_de), ImageDraw.Draw(mask_ot)
for iso, pts in land:
    (md if iso == "DEU" else mo).polygon(pts, fill=255)
base.paste(halftone((BW, BH), OTHER_DOT, OTHER, 18, 4), (0, 0), mask_ot)
base.paste(halftone((BW, BH), DE_DOT, DE, 16, 3), (0, 0), mask_de)

bd = ImageDraw.Draw(base)
for pts in river_lines:
    bd.line(pts, fill=INK, width=11, joint="curve")
for pts in river_lines:
    bd.line(pts, fill=RIVER, width=6, joint="curve")
for pts in state_lines:  # dashed state borders
    acc = 0
    for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
        seg = math.hypot(x1 - x0, y1 - y0)
        if (acc // 26) % 2 == 0:
            bd.line((x0, y0, x1, y1), fill=(150, 110, 60), width=4)
        acc += seg
# heavy comic outlines around land (drop shadow + line)
shadow = Image.new("L", (BW, BH), 0)
sd = ImageDraw.Draw(shadow)
for iso, pts in land:
    sd.line(pts + [pts[0]], fill=255, width=9, joint="curve")
base.paste(INK, (0, 0), shadow)
print("base done")

# ---------- route (A7 -> Hannover -> B217 -> Hameln -> Bad Pyrmont) ----------
WAY = [
    (9.330, 54.766), (9.40, 54.66), (9.50, 54.50), (9.62, 54.36), (9.70, 54.25),
    (9.86, 54.13), (9.97, 54.00), (9.97, 53.80), (9.93, 53.65), (9.93, 53.55),
    (9.97, 53.44), (9.93, 53.25), (9.85, 53.02), (9.70, 52.88), (9.72, 52.65),
    (9.73, 52.45), (9.70, 52.33), (9.55, 52.22), (9.43, 52.14), (9.36, 52.10),
    (9.29, 52.04), (9.257, 51.986),
]

def catmull(pts, n=40):
    out = []
    P = [pts[0]] + pts + [pts[-1]]
    for i in range(1, len(P) - 2):
        p0, p1, p2, p3 = map(np.array, (P[i - 1], P[i], P[i + 1], P[i + 2]))
        for t in np.linspace(0, 1, n, endpoint=False):
            out.append(0.5 * ((2 * p1) + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t * t
                              + (-p0 + 3 * p1 - 3 * p2 + p3) * t ** 3))
    out.append(np.array(pts[-1]))
    return np.array(out)

geo_path = catmull(WAY)
path = np.array([proj(*p) for p in geo_path])
seg = np.hypot(*np.diff(path, axis=0).T)
cum = np.concatenate([[0], np.cumsum(seg)])
TOTAL = cum[-1]

def hav(a, b):
    R = 6371
    la1, la2 = math.radians(a[1]), math.radians(b[1])
    dla, dlo = la2 - la1, math.radians(b[0] - a[0])
    h = math.sin(dla / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin(dlo / 2) ** 2
    return 2 * R * math.asin(math.sqrt(h))
KM_REAL = 395.0  # Strassenkilometer Handewitt -> Bad Pyrmont (ca.)
geo_cum = np.concatenate([[0], np.cumsum([hav(a, b) for a, b in zip(geo_path, geo_path[1:])])])
geo_cum *= KM_REAL / geo_cum[-1]

def at(u):
    """position, heading, km at fraction u of route"""
    d = max(0.0, min(1.0, u)) * TOTAL
    i = int(np.searchsorted(cum, d, side="right") - 1)
    i = min(i, len(path) - 2)
    t = (d - cum[i]) / max(seg[i], 1e-9)
    p = path[i] + (path[i + 1] - path[i]) * t
    j0, j1 = max(0, i - 6), min(len(path) - 1, i + 6)
    dv = path[j1] - path[j0]
    km = geo_cum[i] + (geo_cum[i + 1] - geo_cum[i]) * t
    return p, math.atan2(dv[1], dv[0]), km, i

CITIES = [  # name, lon, lat, size, label offset
    ("Handewitt", 9.330, 54.766, 2, (-30, -10), "r"),
    ("Flensburg", 9.437, 54.79, 1, (24, -28), "l"),
    ("Schleswig", 9.57, 54.52, 1, (26, -18), "l"),
    ("Kiel", 10.13, 54.32, 1, (24, -18), "l"),
    ("Rendsburg", 9.67, 54.30, 1, (-24, -18), "r"),
    ("Neumünster", 9.98, 54.07, 1, (26, -18), "l"),
    ("Lübeck", 10.69, 53.87, 1, (24, -18), "l"),
    ("Hamburg", 10.00, 53.55, 3, (34, -30), "l"),
    ("Bremen", 8.80, 53.08, 2, (-30, -26), "r"),
    ("Soltau", 9.84, 52.99, 1, (26, -18), "l"),
    ("Celle", 10.08, 52.62, 1, (26, -18), "l"),
    ("Hannover", 9.73, 52.375, 3, (36, -30), "l"),
    ("Hameln", 9.36, 52.10, 1, (-26, -22), "r"),
    ("Bad Pyrmont", 9.257, 51.986, 2, (30, 44), "l"),
]
for c in CITIES:
    x, y = proj(c[1], c[2])
    r = {1: 9, 2: 13, 3: 17}[c[3]]
    bd.ellipse((x - r - 4, y - r - 4, x + r + 4, y + r + 4), fill=INK)
    bd.ellipse((x - r, y - r, x + r, y + r), fill=(255, 255, 255) if c[3] < 3 else RED)

# Labels: drawn in comic boxes on base map
def label_box(d, x, y, text, sz, anchor="l", bg=(255, 255, 255), fg=INK, tilt_shadow=6):
    f = font(sz)
    tw, th = d.textbbox((0, 0), text, font=f)[2:]
    pad = sz * 0.28
    if anchor == "l":
        x0 = x
    else:
        x0 = x - tw - 2 * pad
    y0 = y - th / 2 - pad
    box = (x0, y0, x0 + tw + 2 * pad, y0 + th + 2 * pad)
    d.rectangle((box[0] + tilt_shadow, box[1] + tilt_shadow, box[2] + tilt_shadow, box[3] + tilt_shadow), fill=INK)
    d.rectangle(box, fill=bg, outline=INK, width=4)
    d.text((x0 + pad, y0 + pad * 0.9), text, font=f, fill=fg)

for name, lon, lat, size, off, anc in CITIES:
    x, y = proj(lon, lat)
    sz = {1: 40, 2: 50, 3: 62}[size]
    bg = (255, 255, 255)
    if name in ("Handewitt", "Bad Pyrmont"):
        bg = (255, 120, 170)
    label_box(bd, x + off[0], y + off[1], name.upper(), sz, anc, bg=bg)

def sea_label(text, lon, lat, sz, ang=0):
    f = font(sz)
    tw, th = bd.textbbox((0, 0), text, font=f)[2:]
    im = Image.new("RGBA", (tw + 30, th + 30), (0, 0, 0, 0))
    dd = ImageDraw.Draw(im)
    dd.text((15, 10), text, font=f, fill=(255, 255, 255), stroke_width=5, stroke_fill=(30, 90, 150))
    im = im.rotate(ang, expand=True, resample=Image.BICUBIC)
    x, y = proj(lon, lat)
    base.paste(im, (int(x - im.width / 2), int(y - im.height / 2)), im)

sea_label("NORDSEE", 8.15, 54.45, 110, 12)
sea_label("OSTSEE", 11.1, 54.55, 100, -8)
sea_label("DÄNEMARK", 9.5, 55.10, 70)

base_np = np.array(base)
print("labels done")

# ---------- camper van sprite ----------
VS = 2  # supersample
def camper_sprite(wheel_angle, facing_right=True):
    w, h = 300 * VS, 190 * VS
    im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    s = VS
    lw = 7 * s
    # shadow
    d.ellipse((30 * s, 165 * s, 270 * s, 185 * s), fill=(0, 0, 0, 90))
    # body (living box) + alcove + cab
    body = [(20 * s, 150 * s), (20 * s, 40 * s), (40 * s, 25 * s), (230 * s, 25 * s),
            (245 * s, 40 * s), (245 * s, 75 * s), (285 * s, 95 * s), (290 * s, 150 * s)]
    d.polygon(body, fill=(255, 255, 255), outline=INK)
    d.line(body + [body[0]], fill=INK, width=lw, joint="curve")
    # stripes
    d.rectangle((24 * s, 112 * s, 287 * s, 124 * s), fill=RED)
    d.rectangle((24 * s, 126 * s, 288 * s, 132 * s), fill=(255, 190, 40))
    # windscreen / cab window
    d.polygon([(248 * s, 82 * s), (280 * s, 99 * s), (282 * s, 108 * s), (248 * s, 108 * s)],
              fill=(150, 215, 245), outline=INK, width=5 * s)
    # side windows
    for x0 in (50, 120):
        d.rounded_rectangle((x0 * s, 50 * s, (x0 + 50) * s, 90 * s), radius=8 * s,
                            fill=(150, 215, 245), outline=INK, width=5 * s)
        d.line(((x0 + 10) * s, 58 * s, (x0 + 22) * s, 58 * s), fill=(255, 255, 255), width=4 * s)
    # door
    d.rounded_rectangle((185 * s, 50 * s, 220 * s, 140 * s), radius=6 * s, fill=(255, 245, 225), outline=INK, width=5 * s)
    d.ellipse((211 * s, 95 * s, 217 * s, 101 * s), fill=INK)
    # roof box + bike
    d.rounded_rectangle((70 * s, 8 * s, 160 * s, 27 * s), radius=8 * s, fill=(255, 190, 40), outline=INK, width=5 * s)
    # headlight / bumper
    d.ellipse((276 * s, 118 * s, 290 * s, 132 * s), fill=(255, 245, 140), outline=INK, width=3 * s)
    d.rectangle((20 * s, 145 * s, 292 * s, 155 * s), fill=(120, 120, 130), outline=INK, width=4 * s)
    # wheels
    for cx in (75, 235):
        cx *= s; cy = 152 * s; R = 26 * s
        d.ellipse((cx - R, cy - R, cx + R, cy + R), fill=INK)
        d.ellipse((cx - 13 * s, cy - 13 * s, cx + 13 * s, cy + 13 * s), fill=(210, 210, 215))
        for k in range(3):
            a = wheel_angle + k * 2 * math.pi / 3
            d.line((cx, cy, cx + 12 * s * math.cos(a), cy + 12 * s * math.sin(a)), fill=INK, width=4 * s)
    im = im.resize((w // VS, h // VS), Image.LANCZOS)
    if not facing_right:
        im = im.transpose(Image.FLIP_LEFT_RIGHT)
    return im

# ---------- timeline ----------
T_INTRO = 3.0
T_ZOOMIN = 1.5
T_DRIVE = 15.0
T_ARRIVE = 2.0
T_OUTRO = 3.5
DUR = T_INTRO + T_ZOOMIN + T_DRIVE + T_ARRIVE + T_OUTRO
N = int(DUR * FPS)

def ease(t): return t * t * (3 - 2 * t)
def ease_io(t): return 0.5 - 0.5 * math.cos(math.pi * max(0, min(1, t)))

p_start = at(0)[0]
p_end = at(1)[0]
rmin, rmax = path.min(0), path.max(0)
OV_C = (rmin + rmax) / 2 + np.array([0, 0])
OV_Z = H / (rmax[1] - rmin[1] + 560)
OV_C = OV_C - np.array([0.12 * W / OV_Z, -20 / OV_Z])  # screen px per base px
FOLLOW_Z = 0.62

def drive_u(t):
    # accelerate / constant / brake (trapezoid speed profile)
    x = max(0, min(1, t / T_DRIVE))
    a = 0.12
    if x < a:
        v = x * x / (2 * a)
    elif x <= 1 - a:
        v = a / 2 + (x - a)
    else:
        y = x - (1 - a)
        v = a / 2 + (1 - 2 * a) + (y - y * y / (2 * a))
    return v / (1 - a)

def camera(t):
    if t < T_INTRO:
        return OV_C, OV_Z
    t -= T_INTRO
    if t < T_ZOOMIN:
        k = ease_io(t / T_ZOOMIN)
        c = OV_C + (p_start - OV_C) * k
        return c, OV_Z + (FOLLOW_Z - OV_Z) * k
    t -= T_ZOOMIN
    if t < T_DRIVE:
        return at(drive_u(t))[0], FOLLOW_Z
    t -= T_DRIVE
    if t < T_ARRIVE:
        return p_end, FOLLOW_Z + 0.08 * math.sin(math.pi * min(1, t / 0.5)) * (t < 0.5)
    t -= T_ARRIVE
    k = ease_io(t / 1.6)
    return p_end + (OV_C - p_end) * k, FOLLOW_Z + (OV_Z - FOLLOW_Z) * k

def van_u(t):
    if t < T_INTRO + T_ZOOMIN:
        return 0.0
    t -= T_INTRO + T_ZOOMIN
    if t < T_DRIVE:
        return drive_u(t)
    return 1.0

# Speech bubbles (route fraction where they pop, text)
def frac_of(lon, lat):
    p = np.array(proj(lon, lat))
    return float(cum[np.argmin(np.hypot(*(path - p).T))] / TOTAL)

BUBBLES = [
    (frac_of(9.40, 54.66), 0.13, "LOS GEHT'S!"),
    (frac_of(9.70, 54.25), 0.10, "MOIN, RENDSBURG!"),
    (frac_of(9.93, 53.55), 0.12, "AB DURCH DEN ELBTUNNEL!"),
    (frac_of(9.85, 53.02), 0.10, "HEIDE IN SICHT ..."),
    (frac_of(9.73, 52.40), 0.11, "HALLO HANNOVER!"),
    (frac_of(9.36, 52.10), 0.10, "RATTENFÄNGER WINKT!"),
]

# ---------- drawing helpers on screen ----------
def to_screen(p, c, z):
    return ((p[0] - c[0]) * z + W / 2, (p[1] - c[1]) * z + H / 2)

def crop_view(c, z):
    vw, vh = W / z, H / z
    x0, y0 = c[0] - vw / 2, c[1] - vh / 2
    # affine transform from output to base coordinates
    img = Image.fromarray(base_np)
    return img.transform((W, H), Image.AFFINE, (1 / z, 0, x0, 0, 1 / z, y0),
                         resample=Image.BILINEAR, fillcolor=SEA)

def burst(d, cx, cy, r_out, r_in, n, fill, rot=0):
    pts = []
    for k in range(2 * n):
        r = r_out if k % 2 == 0 else r_in
        a = rot + k * math.pi / n
        pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    d.polygon([(x + 10, y + 10) for x, y in pts], fill=INK)
    d.polygon(pts, fill=fill, outline=INK)
    d.line(pts + [pts[0]], fill=INK, width=8, joint="curve")

def text_c(d, cx, cy, text, sz, fill=(255, 255, 255), stroke=INK, sw=8):
    if sz < 4: return
    f = font(sz)
    b = d.textbbox((0, 0), text, font=f, stroke_width=sw)
    d.text((cx - (b[2] - b[0]) / 2 - b[0], cy - (b[3] - b[1]) / 2 - b[1]), text, font=f,
           fill=fill, stroke_width=sw, stroke_fill=stroke)

def speech(d, ax, ay, text, scale=1.0, side=1):
    f = font(int(52 * scale))
    tw, th = d.textbbox((0, 0), text, font=f)[2:]
    pw, ph = tw + 70 * scale, th + 50 * scale
    bx = ax + side * 60 * scale - (pw if side < 0 else 0)
    by = ay - 150 * scale - ph
    tail = [(ax + side * 20, ay - 70 * scale), (bx + pw * (0.3 if side > 0 else 0.7), by + ph - 8),
            (bx + pw * (0.3 if side > 0 else 0.7) + side * 50 * scale, by + ph - 8)]
    d.ellipse((bx + 8, by + 8, bx + pw + 8, by + ph + 8), fill=INK)
    d.ellipse((bx, by, bx + pw, by + ph), fill=(255, 255, 255), outline=INK, width=6)
    d.polygon(tail, fill=(255, 255, 255))
    d.line([tail[1], tail[0], tail[2]], fill=INK, width=6)
    d.text((bx + (pw - tw) / 2, by + (ph - th) / 2 - 4 * scale), text, font=f, fill=INK)

def panel_frame(d):
    m = 18
    d.rectangle((0, 0, W, m), fill=(255, 255, 255)); d.rectangle((0, H - m, W, H), fill=(255, 255, 255))
    d.rectangle((0, 0, m, H), fill=(255, 255, 255)); d.rectangle((W - m, 0, W, H), fill=(255, 255, 255))
    d.rectangle((m, m, W - m, H - m), outline=INK, width=10)

def caption(d, x, y, text, sz=46, bg=(255, 230, 90)):
    f = font(sz)
    tw, th = d.textbbox((0, 0), text, font=f)[2:]
    box = (x, y, x + tw + 44, y + th + 30)
    d.rectangle((box[0] + 8, box[1] + 8, box[2] + 8, box[3] + 8), fill=INK)
    d.rectangle(box, fill=bg, outline=INK, width=6)
    d.text((x + 22, y + 13), text, font=f, fill=INK)
    return box

def pop(t, t0, dur=0.35):
    """overshoot pop-in scale"""
    x = (t - t0) / dur
    if x <= 0: return 0.0
    if x >= 1: return 1.0
    return 1 + 0.25 * math.sin(x * math.pi) * (1 - x) * 2 - (1 - x) ** 3

# ---------- render ----------
FR = os.path.join(HERE, "frames")
os.makedirs(FR, exist_ok=True)
frames = range(N) if not PREVIEW else [int(v) for v in PREVIEW.split(",")]
facing = True
sprites = {}

for fi in frames:
    t = fi / FPS
    c, z = camera(t)
    # small camera shake on arrival
    if T_INTRO + T_ZOOMIN + T_DRIVE < t < T_INTRO + T_ZOOMIN + T_DRIVE + 0.4:
        c = c + np.array([math.sin(t * 90) * 6, math.cos(t * 77) * 6]) / z
    img = crop_view(c, z)
    d = ImageDraw.Draw(img)

    u = van_u(t)
    pos, head, km, idx = at(u)
    # full route as dashed preview
    full = [to_screen(p, c, z) for p in path[::2]]
    for k in range(0, len(full) - 1, 2):
        d.line((full[k], full[k + 1]), fill=INK, width=max(4, int(12 * z)))
    # driven route: thick red with black outline
    if u > 0:
        drv = [to_screen(p, c, z) for p in path[:idx + 1]] + [to_screen(pos, c, z)]
        if len(drv) > 1:
            d.line(drv, fill=INK, width=max(10, int(34 * z)), joint="curve")
            d.line(drv, fill=RED, width=max(5, int(20 * z)), joint="curve")

    # van
    sx, sy = to_screen(pos, c, z)
    moving = (T_INTRO + T_ZOOMIN) < t < (T_INTRO + T_ZOOMIN + T_DRIVE)
    dx = math.cos(head)
    if dx > 0.25: facing = True
    elif dx < -0.25: facing = False
    vscale = 0.78 * max(0.5, min(1.0, z / FOLLOW_Z))
    wheel = -t * 14 if moving else 0
    spr = camper_sprite(wheel if facing else -wheel, facing)
    # tilt toward heading (clamped), bobbing
    dy = math.sin(head)
    tilt = -math.degrees(math.atan2(dy, abs(dx) + 0.6)) * 0.35
    tilt = tilt if facing else -tilt
    bob = math.sin(t * 22) * 4 if moving else 0
    spr = spr.resize((int(spr.width * vscale), int(spr.height * vscale)), Image.LANCZOS)
    spr = spr.rotate(tilt, expand=True, resample=Image.BICUBIC)
    # speed lines
    if moving:
        for k in range(4):
            ly = sy - 40 * vscale + k * 26 * vscale + bob
            ln = (60 + 40 * ((fi + k * 3) % 5) / 5) * vscale
            back = -1 if facing else 1
            x0 = sx + back * 160 * vscale
            d.line((x0, ly, x0 + back * ln, ly), fill=INK, width=max(3, int(7 * vscale)))
        # exhaust puffs
        for k in range(3):
            ph = ((t * 2.5 + k / 3) % 1)
            back = -1 if facing else 1
            px = sx + back * (150 + ph * 90) * vscale
            py = sy + (45 - ph * 40) * vscale
            r = (8 + ph * 18) * vscale
            d.ellipse((px - r, py - r, px + r, py + r), fill=(240, 240, 240), outline=INK, width=3)
    img.paste(spr, (int(sx - spr.width / 2), int(sy - spr.height * 0.62 + bob)), spr)

    # speech bubbles while driving
    if moving:
        for f0, length, txt in BUBBLES:
            if f0 <= u <= f0 + length:
                sc = pop(u, f0, 0.02)
                if sc > 0.05:
                    speech(d, sx, sy - 40 * vscale, txt, scale=0.9 * sc, side=1 if sx < W * 0.6 else -1)

    # ---- overlays ----
    panel_frame(d)
    tl = t
    if t < T_INTRO + 0.4:
        s1 = pop(tl, 0.15, 0.45)
        if s1 > 0:
            burst(d, W * 0.26, H * 0.40, 330 * s1, 230 * s1, 16, (255, 220, 60), rot=tl * 0.3)
            text_c(d, W * 0.26, H * 0.34, "ROADTRIP!", int(120 * s1), fill=RED, sw=10)
        s2 = pop(tl, 0.75, 0.4)
        if s2 > 0:
            text_c(d, W * 0.26, H * 0.45, "HANDEWITT", int(60 * s2), fill=(255, 255, 255), sw=7)
        s3 = pop(tl, 1.05, 0.35)
        if s3 > 0:
            text_c(d, W * 0.26, H * 0.505, "NACH", int(36 * s3), fill=(255, 255, 255), sw=5)
        s4 = pop(tl, 1.3, 0.4)
        if s4 > 0:
            text_c(d, W * 0.26, H * 0.56, "BAD PYRMONT", int(60 * s4), fill=(255, 255, 255), sw=7)

    if T_INTRO <= t < T_INTRO + T_ZOOMIN + T_DRIVE + T_ARRIVE + 0.6:
        # caption top-left + km counter
        caption(d, 44, 40, "UNTERWEGS MIT DEM WOHNMOBIL")
        kmtxt = f"{int(km):3d} KM"
        f = font(64)
        tw = d.textbbox((0, 0), kmtxt, font=f)[2]
        caption(d, W - tw - 44 - 50, H - 140, kmtxt, sz=64, bg=(255, 255, 255))
        # progress bar
        bx0, by0, bx1 = 50, H - 90, 700
        d.rectangle((bx0 + 6, by0 + 6, bx1 + 6, by0 + 40), fill=INK)
        d.rectangle((bx0, by0, bx1, by0 + 34), fill=(255, 255, 255), outline=INK, width=5)
        d.rectangle((bx0 + 5, by0 + 5, bx0 + 5 + (bx1 - bx0 - 10) * u, by0 + 29), fill=RED)
        d.text((bx0, by0 - 52), "HANDEWITT", font=font(40), fill=INK, stroke_width=4, stroke_fill=(255, 255, 255))
        ftxt = "BAD PYRMONT"
        fw = d.textbbox((0, 0), ftxt, font=font(40))[2]
        d.text((bx1 - fw, by0 - 52), ftxt, font=font(40), fill=INK, stroke_width=4, stroke_fill=(255, 255, 255))

    ta = T_INTRO + T_ZOOMIN + T_DRIVE
    if ta <= t < ta + T_ARRIVE + 1.2:
        s = pop(t, ta + 0.05, 0.4)
        burst(d, sx - 420, sy - 130, 260 * s, 180 * s, 14, (255, 120, 170), rot=t * 0.4)
        text_c(d, sx - 420, sy - 140, "ANGEKOMMEN!", int(74 * s), fill=(255, 255, 255), sw=9)
    if t >= ta + T_ARRIVE + 1.0:
        s = pop(t, ta + T_ARRIVE + 1.0, 0.45)
        cx, cy = W * 0.27, H * 0.40
        box_w, box_h = 760 * s, 300 * s
        d.rectangle((cx - box_w / 2 + 12, cy - box_h / 2 + 12, cx + box_w / 2 + 12, cy + box_h / 2 + 12), fill=INK)
        d.rectangle((cx - box_w / 2, cy - box_h / 2, cx + box_w / 2, cy + box_h / 2), fill=(255, 230, 90), outline=INK, width=8)
        if s > 0.3:
            text_c(d, cx, cy - 70 * s, "HANDEWITT", int(70 * s), fill=(255, 255, 255), sw=8)
            text_c(d, cx, cy + 0 * s, "BIS", int(40 * s), fill=RED, sw=5)
            text_c(d, cx, cy + 70 * s, "BAD PYRMONT", int(70 * s), fill=(255, 255, 255), sw=8)
            text_c(d, cx, cy + 128 * s, f"CA. {int(KM_REAL)} KM - ENDE!", int(34 * s), fill=INK, stroke=(255, 255, 255), sw=3)

    img.save(os.path.join(FR, f"f{fi:04d}.png"), compress_level=1)
    if fi % 60 == 0:
        print("frame", fi, "/", N, flush=True)

if not PREVIEW:
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-framerate", str(FPS), "-i", os.path.join(FR, "f%04d.png"),
                    "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "20", "-preset", "medium",
                    "-movflags", "+faststart", OUT], check=True)
    print("wrote", OUT)
