#!/usr/bin/env python3
"""news-image-20261120 v4 — sums up Friday 20 November 2026 in one image.

Stdlib only. Draws the whole front page (masthead, numbers row, region
bar, 3 big lead panels, 10 medium panels, world map, ALSO list, DATE CHECK)
with a small vector rasteriser and a bitmap font baked into fontdata.txt
(DejaVu / Liberation glyphs rasterised at build time by build_font.py).
Writes entry.png to $MAKEFUN_OUTPUT_DIR (or ./entry.png). Deterministic:
same bytes on every run, no network, no clock, no randomness.
"""
import base64
import os
import struct
import sys
import zlib

W, H = 1024, 1024


# ---------------------------------------------------------------- PNG out
def write_png(img, path):
    """img: bytes-like RGB, W*H*3. Deterministic: filter 0, zlib level 9."""
    raw = bytearray()
    stride = W * 3
    for y in range(H):
        raw.append(0)
        raw += img[y * stride:(y + 1) * stride]
    comp = zlib.compress(bytes(raw), 9)

    def chunk(tag, data):
        c = struct.pack(">I", len(data)) + tag + data
        return c + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)

    ihdr = struct.pack(">IIBBBBB", W, H, 8, 2, 0, 0, 0)
    png = b"\x89PNG\r\n\x1a\n"
    png += chunk(b"IHDR", ihdr)
    png += chunk(b"IDAT", comp)
    png += chunk(b"IEND", b"")
    with open(path, "wb") as f:
        f.write(png)
    return len(png)


# ---------------------------------------------------------------- canvas
class Img:
    def __init__(self, w=W, h=H, fill=(247, 240, 221)):
        self.w, self.h = w, h
        self.px = bytearray(fill * (w * h))

    def set(self, x, y, c):
        if 0 <= x < self.w and 0 <= y < self.h:
            i = (y * self.w + x) * 3
            self.px[i] = c[0]
            self.px[i + 1] = c[1]
            self.px[i + 2] = c[2]

    def fill_rect(self, x, y, w, h, c):
        x0 = max(0, x)
        y0 = max(0, y)
        x1 = min(self.w, x + w)
        y1 = min(self.h, y + h)
        if x1 <= x0 or y1 <= y0:
            return
        row = bytes(c) * (x1 - x0)
        for yy in range(y0, y1):
            i = (yy * self.w + x0) * 3
            self.px[i:i + len(row)] = row

    def hline(self, x0, x1, y, c):
        if x0 > x1:
            x0, x1 = x1, x0
        self.fill_rect(x0, y, x1 - x0 + 1, 1, c)

    def vline(self, x, y0, y1, c):
        if y0 > y1:
            y0, y1 = y1, y0
        self.fill_rect(x, y0, 1, y1 - y0 + 1, c)

    def line(self, x0, y0, x1, y1, c):
        dx = abs(x1 - x0)
        dy = -abs(y1 - y0)
        sx = 1 if x0 < x1 else -1
        sy = 1 if y0 < y1 else -1
        err = dx + dy
        while True:
            self.set(x0, y0, c)
            if x0 == x1 and y0 == y1:
                return
            e2 = 2 * err
            if e2 >= dy:
                err += dy
                x0 += sx
            if e2 <= dx:
                err += dx
                y0 += sy

    def dashed_line(self, x0, y0, x1, y1, c, dash=7, gap=5):
        dx = x1 - x0
        dy = y1 - y0
        n = max(abs(dx), abs(dy))
        if n == 0:
            return
        on = True
        count = 0
        px, py = float(x0), float(y0)
        for _ in range(n + 1):
            if on:
                self.set(int(px), int(py), c)
            count += 1
            if on and count >= dash:
                on = False
                count = 0
            elif not on and count >= gap:
                on = True
                count = 0
            px += dx / n
            py += dy / n

    def circle(self, cx, cy, r, c, fill=True):
        for dy in range(-r, r + 1):
            dx = int((r * r - dy * dy) ** 0.5)
            if fill:
                self.hline(cx - dx, cx + dx, cy + dy, c)
            else:
                self.set(cx - dx, cy + dy, c)
                self.set(cx + dx, cy + dy, c)

    def ellipse(self, cx, cy, rx, ry, c, fill=True):
        for dy in range(-ry, ry + 1):
            t = 1.0 - (dy * dy) / float(ry * ry)
            dx = int(rx * (t ** 0.5)) if t > 0 else 0
            if fill:
                self.hline(cx - dx, cx + dx, cy + dy, c)
            else:
                self.set(cx - dx, cy + dy, c)
                self.set(cx + dx, cy + dy, c)

    def ring(self, cx, cy, r, c, thick=2):
        for rr in range(r - thick + 1, r + 1):
            self.circle(cx, cy, rr, c, fill=False)

    def poly(self, pts, c):
        """Scanline fill of a simple polygon (list of (x, y))."""
        if len(pts) < 3:
            return
        ys = [p[1] for p in pts]
        y0, y1 = max(0, min(ys)), min(self.h - 1, max(ys))
        n = len(pts)
        for y in range(y0, y1 + 1):
            xs = []
            for i in range(n):
                x0, ya = pts[i]
                x1, yb = pts[(i + 1) % n]
                if ya == yb:
                    continue
                if (ya <= y < yb) or (yb <= y < ya):
                    xs.append(x0 + (y - ya) * (x1 - x0) / (yb - ya))
            xs.sort()
            for k in range(0, len(xs) - 1, 2):
                self.hline(int(xs[k]), int(xs[k + 1]), y, c)

    def border(self, x, y, w, h, c, t=1):
        self.fill_rect(x, y, w, t, c)
        self.fill_rect(x, y + h - t, w, t, c)
        self.fill_rect(x, y, t, h, c)
        self.fill_rect(x + w - t, y, t, h, c)


# ---------------------------------------------------------------- font
def _bits_get(data, w, x, y):
    # Rows are packed separately (build_font.py pads each row to a byte).
    stride = (w + 7) // 8
    return (data[y * stride + (x >> 3)] >> (7 - (x & 7))) & 1


class Font:
    def __init__(self, path):
        # faces: name -> {base: (ascent, descent, {cp: (adv, w, h, bear, data)})}
        self.faces = {}
        with open(path, "r") as f:
            cur = None
            for line in f:
                parts = line.split()
                if not parts:
                    continue
                if parts[0] == "FACE":
                    name, base = parts[1], int(parts[2])
                    cur = (name, base)
                    self.faces.setdefault(name, {})[base] = (
                        int(parts[3]), int(parts[4]), {})
                elif parts[0] == "DATA" and cur is not None:
                    # One packed line per face/size: records separated by ";",
                    # each "<cp> <adv> <w> <h> <bear> <b64>" (b64 empty for
                    # blank glyphs such as space).
                    for rec in line[5:].strip().split(";"):
                        flds = rec.split(" ")
                        if len(flds) < 5:
                            continue
                        cp = int(flds[0])
                        adv, w, h, bear = (int(flds[1]), int(flds[2]),
                                            int(flds[3]), int(flds[4]))
                        data = (base64.b64decode(flds[5])
                                if len(flds) > 5 and flds[5] else b"")
                        self.faces[cur[0]][cur[1]][2][cp] = (
                            adv, w, h, bear, data)
        self.cache = {}
        self.pcache = {}

    def _base(self, face, size):
        bases = self.faces[face]
        big = [b for b in bases if b >= size]
        return min(big) if big else max(bases)

    def _bits_prefix(self, face, base, cp):
        """Integral image of one glyph's bits; cached per (face, base, cp)."""
        key = (face, base, cp)
        hit = self.pcache.get(key)
        if hit is not None:
            return hit
        ascent, descent, glyphs = self.faces[face][base]
        g = glyphs.get(cp)
        if g is None:
            g = glyphs.get(ord("?"), (base // 2, 0, 0, 0, b""))
        adv, w, h, bear, data = g
        ps = None
        if w and h:
            ps = [0] * ((w + 1) * (h + 1))
            for yy in range(h):
                s = 0
                for xx in range(w):
                    s += _bits_get(data, w, xx, yy)
                    ps[(yy + 1) * (w + 1) + xx + 1] = (
                        ps[yy * (w + 1) + xx + 1] + s)
        out = (adv, w, h, bear, ps)
        self.pcache[key] = out
        return out

    def _scaled(self, face, size, cp):
        key = (face, size, cp)
        hit = self.cache.get(key)
        if hit is not None:
            return hit
        base = self._base(face, size)
        adv, w, h, bear, ps = self._bits_prefix(face, base, cp)
        scale = size / float(base)
        tw = max(1, int(round(w * scale)))
        th = max(1, int(round(h * scale)))
        adv_s = adv * scale
        bear_s = int(round(bear * scale))
        rows = []
        if not (w and h):
            tw, th = 0, 0
        if w and h:
            def cov(x0, y0, x1, y1):
                x0 = max(0, min(w, x0))
                y0 = max(0, min(h, y0))
                x1 = max(0, min(w, x1))
                y1 = max(0, min(h, y1))
                if x1 <= x0 or y1 <= y0:
                    return 0.0
                a = ps[y1 * (w + 1) + x1] - ps[y0 * (w + 1) + x1] \
                    - ps[y1 * (w + 1) + x0] + ps[y0 * (w + 1) + x0]
                return a / float((x1 - x0) * (y1 - y0))

            for ty in range(th):
                sy0 = int(ty * h / th)
                sy1 = max(sy0 + 1, int((ty + 1) * h / th))
                row = bytearray(tw)
                for tx in range(tw):
                    sx0 = int(tx * w / tw)
                    sx1 = max(sx0 + 1, int((tx + 1) * w / tw))
                    if cov(sx0, sy0, sx1, sy1) >= 0.35:
                        row[tx] = 1
                rows.append(bytes(row))
        out = (adv_s, tw, th, bear_s, rows)
        self.cache[key] = out
        return out

    def width(self, face, size, text, tracking=0.0):
        total = 0.0
        for ch in text:
            total += self._scaled(face, size, ord(ch))[0] + tracking
        return total - tracking if text else 0.0

    def draw(self, img, face, size, x, baseline, text, color, tracking=0.0):
        cx = float(x)
        for ch in text:
            adv, tw, th, bear, rows = self._scaled(face, size, ord(ch))
            top = int(baseline) + bear
            for ty in range(th):
                yy = top + ty
                if yy < 0 or yy >= img.h:
                    continue
                row = rows[ty]
                base_i = (yy * img.w + int(cx)) * 3
                for tx in range(tw):
                    if row[tx]:
                        xx = int(cx) + tx
                        if 0 <= xx < img.w:
                            i = base_i + tx * 3
                            img.px[i] = color[0]
                            img.px[i + 1] = color[1]
                            img.px[i + 2] = color[2]
            cx += adv + tracking
        return cx

    def wrap(self, face, size, text, maxw, tracking=0.0):
        """Greedy word wrap; returns list of lines."""
        lines = []
        for para in text.split("\n"):
            words = para.split(" ")
            cur = ""
            for word in words:
                trial = word if not cur else cur + " " + word
                if self.width(face, size, trial, tracking) <= maxw or not cur:
                    cur = trial
                else:
                    lines.append(cur)
                    cur = word
            lines.append(cur)
        return lines


FONT = None


def load_font():
    global FONT
    here = os.path.dirname(os.path.abspath(__file__))
    FONT = Font(os.path.join(here, "fontdata.txt"))
    return FONT


# ---------------------------------------------------------------- palette
PAPER = (247, 240, 221)
INK = (26, 26, 26)
RED = (176, 38, 32)
DARKRED = (140, 28, 24)
NAVY = (16, 34, 64)
NAVY2 = (24, 48, 88)
SKY = (58, 110, 165)
SEA = (43, 90, 140)
SAND = (232, 220, 192)
LAND = (233, 221, 193)
GREEN = (46, 125, 50)
GREEN_NUM = (27, 94, 32)
TEAL = (0, 131, 143)
PURPLE = (106, 61, 154)
GOLD = (138, 109, 31)
GREY = (97, 97, 97)
WHITE = (255, 255, 255)
BLACK = (10, 10, 10)
ORANGE = (230, 126, 34)
YELLOW = (245, 197, 66)
CREAM = (250, 244, 228)

MX = 28          # page margin
CW = 968         # content width


def banner(img, x, y, text, size=11, h=20, color=RED):
    """Red label banner, top-left of a panel."""
    w = int(FONT.width("sansb", size, text)) + 16
    img.fill_rect(x, y, w, h, color)
    FONT.draw(img, "sansb", size, x + 8, y + h - 6, text, WHITE)


def strip(img, x, y, w, text, size=8.5, h=14, bg=BLACK):
    """Black source strip inside the bottom of a panel."""
    img.fill_rect(x, y, w, h, bg)
    FONT.draw(img, "sansb", size, x + 6, y + h - 4, text, WHITE)


def white_box(img, x, y, w, h, lines, size=9):
    img.fill_rect(x, y, w, h, WHITE)
    img.border(x, y, w, h, INK, 1)
    yy = y + size + 4
    for ln in lines:
        FONT.draw(img, "sansb", size, x + 6, yy, ln, INK)
        yy += size + 3


# ---------------------------------------------------------------- stories
# (kicker, headline, summary) — 13 leads, in news-weight order.
LEADS = [
    ("1 \u00b7 KYIV, UKRAINE \u00b7 WAR",
     "Russian missiles hit three Kyiv bridges",
     "An overnight barrage of about 100 missiles and 400 drones killed at "
     "least nine people and cut power and water in Kyiv. "
     "(Kyiv Independent, BBC)"),
    ("2 \u00b7 ODISHA, INDIA \u00b7 CYCLONE",
     "Cyclone Akvan comes ashore in eastern India",
     "The storm crossed the coast near Gopalpur in the morning; 372,000 "
     "people were moved to shelters. No deaths were reported. "
     "(IMD, Deccan Herald)"),
    ("3 \u00b7 TAIPEI \u00b7 SEOUL \u00b7 TOKYO \u00b7 MARKETS",
     "AI sell-off sinks Asia\u2019s stock markets",
     "Taiwan\u2019s index fell 6.2% to end its worst week since 1991. Seoul "
     "lost 5.2% and Tokyo 5.1% as chipmakers led the slide. "
     "(Al Jazeera, Anadolu)"),
]

MEDIUMS = [
    ("4 \u00b7 BRUSSELS \u00b7 DIPLOMACY",
     "UK and EU seal a \u201creset\u201d deal",
     "Food trade, youth visas, carbon link."),
    ("5 \u00b7 ANTALYA \u00b7 CLIMATE",
     "COP31 reaches its last day with no deal",
     "The draft text leaves out fossil fuels."),
    ("6 \u00b7 EASTERN POLAND \u00b7 SECURITY",
     "Russian missile lands in Poland",
     "It fell in a field; two airports paused."),
    ("7 \u00b7 CENTRAL IRAQ \u00b7 SECURITY",
     "Iraqi army enters a militia stronghold",
     "Troops deploy to Jurf al-Sakhar."),
    ("8 \u00b7 ITALY \u00b7 LABOUR",
     "General strike over Italy\u2019s budget",
     "Workers and students march."),
    ("9 \u00b7 TOKYO \u00b7 ECONOMY",
     "Japan\u2019s inflation picks up to 2.3%",
     "A December rate rise stays in view."),
    ("10 \u00b7 SEOUL \u00b7 POLITICS",
     "Korea\u2019s ruling party to impeach top judge",
     "It follows an overturned conviction."),
    ("11 \u00b7 TURKANA, KENYA \u00b7 ENERGY",
     "Kenya starts drilling its first oil well",
     "First crude is due on 1 December."),
    ("12 \u00b7 SAN SALVADOR \u00b7 POLITICS",
     "Bukele files to run for a third term",
     "The vote is on 28 February 2027."),
    ("13 \u00b7 WELLINGTON \u00b7 CRICKET",
     "Phillips hits 118 against India",
     "Hundreds v India in all three formats."),
]

# (number, source) — 22 more stories, two columns of 11.
ALSO = [
    ("14", "Lviv", "A strike on a railway station kills two", "BBC"),
    ("15", "Moscow", "Russia closes Estonia\u2019s border", "Reuters"),
    ("16", "Berlin", "Pupils strike against military service", "Al Jazeera"),
    ("17", "London", "General: UK runs cyber attacks", "Sky News"),
    ("18", "Beijing", "China holds loan rates for 18th month", "Xinhua"),
    ("19", "Tokyo", "SoftBank shares fall 14% in a day", "Al Jazeera"),
    ("20", "Seoul", "Kospi ends the week 7.9% lower", "Anadolu"),
    ("21", "Ganjam", "209 mm of rain as Akvan crosses Odisha", "PTI"),
    ("22", "Lebanon", "Israeli air strikes hit south and east", "Anadolu"),
    ("23", "Yemen", "Gunmen fire on cargo ship off coast", "UKMTO"),
    ("24", "Abuja", "Court bars Tinubu evidence", "Channels TV"),
    ("25", "Kampala", "Police enforce Ebola ban on rallies", "allAfrica"),
    ("26", "Malawi", "Fuel crisis brings night queues", "Al Jazeera"),
    ("27", "Africa", "AFDB: 22 countries in debt distress", "allAfrica"),
    ("28", "Las Vegas", "Russell fastest in wet GP practice", "Autosport"),
    ("29", "New York", "Nasdaq futures fall 1.6%", "24/7 Wall St"),
    ("30", "Washington", "Democrats query free work", "Al Jazeera"),
    ("31", "Wellington", "Nicholls makes 175 in a 216-run stand", "ICC"),
    ("32", "Sydney", "Australian shares fall 1.8% in sell-off", "Reuters"),
    ("33", "Antalya", "Panama asks COP31 to cap oil output", "Anadolu"),
    ("34", "Antalya", "EU calls climate draft unacceptable", "RTE"),
    ("35", "Turin", "ATP backs pay past $350m", "Anadolu"),
]

NUMBERS = [
    ("3", "bridges damaged in Kyiv"),
    ("372,000", "people evacuated ahead of Akvan"),
    ("\u22126.2%", "Taiwan\u2019s share index, Friday\u2019s close"),
    ("100,000", "youth visas a year in the UK\u2013EU deal"),
    ("2.3%", "Japan consumer inflation in October"),
    ("118", "runs by Glenn Phillips against India"),
]

REGIONS = [
    ("EUROPE 8", (31, 78, 121)),
    ("ASIA 8", (176, 38, 32)),
    ("MIDDLE EAST 3", (138, 109, 31)),
    ("AFRICA 5", (46, 125, 50)),
    ("AMERICAS 4", (106, 61, 154)),
    ("OCEANIA 3", (0, 131, 143)),
    ("GLOBAL 4", (97, 97, 97)),
]

DATE_CHECK = (
    "DATE CHECK  Left out as Thursday 19 November\u2019s news: the World "
    "Court\u2019s ruling on Myanmar, the three-leader declaration in Shenzhen, "
    "Tonga\u2019s drought emergency and the migrant boat lost off Senegal. "
    "Not yet happened, so not shown: Bepicolombo\u2019s entry into orbit round "
    "Mercury and any final COP31 text.")


# ---------------------------------------------------------------- lead art
def art_kyiv(img, x, y, w, h):
    img.fill_rect(x, y, w, h, NAVY)
    img.fill_rect(x, y, w, 26, (12, 26, 52))
    # stars
    for sx, sy in [(18, 14), (52, 8), (96, 18), (140, 10), (185, 16),
                   (230, 8), (268, 20), (296, 12), (70, 30), (210, 30),
                   (30, 42), (160, 38), (250, 40), (120, 26)]:
        img.set(x + sx, y + sy, WHITE)
        img.set(x + sx + 1, y + sy, (200, 200, 220))
    # missile streaks (dashed, top-right to bridge)
    img.dashed_line(x + 250, y + 8, x + 150, y + 88, WHITE, 6, 4)
    img.dashed_line(x + 290, y + 22, x + 210, y + 92, WHITE, 6, 4)
    img.dashed_line(x + 200, y + 4, x + 90, y + 86, (255, 220, 150), 6, 4)
    img.circle(x + 150, y + 88, 3, ORANGE)
    img.circle(x + 210, y + 92, 3, ORANGE)
    img.circle(x + 90, y + 86, 3, ORANGE)
    # skyline silhouettes
    for bx, bw, bh in [(0, 34, 34), (38, 26, 46), (68, 30, 30), (102, 22, 40),
                       (128, 36, 28), (168, 24, 44), (196, 30, 32),
                       (230, 26, 40), (260, 34, 30), (296, 16, 36)]:
        img.fill_rect(x + bx, y + h - 22 - bh, bw, bh, (10, 20, 40))
    # bridge deck + towers + arches
    img.fill_rect(x, y + h - 26, w, 6, (8, 16, 34))
    for tx in (60, 150, 240):
        img.fill_rect(x + tx, y + h - 62, 8, 40, (8, 16, 34))
    img.line(x + 20, y + h - 26, x + 64, y + h - 52, (8, 16, 34))
    img.line(x + 64, y + h - 52, x + 108, y + h - 26, (8, 16, 34))
    img.line(x + 154, y + h - 26, x + 198, y + h - 50, (8, 16, 34))
    img.line(x + 198, y + h - 50, x + 244, y + h - 26, (8, 16, 34))
    # fire glow on the bridge
    img.circle(x + 84, y + h - 30, 9, ORANGE)
    img.circle(x + 84, y + h - 30, 5, YELLOW)
    img.circle(x + 220, y + h - 30, 7, ORANGE)
    img.circle(x + 220, y + h - 30, 4, YELLOW)
    img.poly([(x + 80, y + h - 38), (x + 88, y + h - 38),
              (x + 84, y + h - 52)], YELLOW)
    img.poly([(x + 216, y + h - 36), (x + 224, y + h - 36),
              (x + 220, y + h - 48)], YELLOW)
    banner(img, x, y, "KYIV", 12, 22)
    img.fill_rect(x, y + 22, 118, 14, BLACK)
    FONT.draw(img, "sansb", 8.5, x + 6, y + 22 + 10, "3 BRIDGES HIT", WHITE)
    strip(img, x, y + h - 14, w, "Officials\u2019 count")


def art_akvan(img, x, y, w, h):
    img.fill_rect(x, y, w, h, SEA)
    # coast land on the left
    img.poly([(x, y), (x + 58, y), (x + 74, y + 34), (x + 62, y + 70),
              (x + 78, y + h), (x, y + h)], SAND)
    img.poly([(x + 58, y), (x + 74, y + 34), (x + 62, y + 70),
              (x + 78, y + h), (x + 66, y + h), (x + 52, y + 70),
              (x + 64, y + 34), (x + 48, y)], (210, 196, 160))
    # cyclone spiral: concentric rings, right of centre
    cx, cy = x + 205, y + 62
    for r in (12, 22, 32, 42, 52):
        img.ring(cx, cy, r, WHITE, 2)
    img.circle(cx, cy, 7, WHITE)
    img.circle(cx, cy, 3, RED)
    # rain slashes
    for rx, ry in [(120, 20), (140, 40), (110, 55), (150, 70), (130, 90),
                   (170, 30), (160, 95), (100, 80)]:
        img.line(x + rx, y + ry, x + rx - 6, y + ry + 10, (200, 220, 240))
    # landfall track: red dot on coast + dashed line to the eye
    img.circle(x + 66, y + 52, 5, RED)
    img.dashed_line(x + 66, y + 52, cx - 10, cy - 4, RED, 5, 4)
    banner(img, x, y, "CYCLONE AKVAN", 12, 22)
    white_box(img, x + w - 132, y + 30, 124, 30,
              ["LANDFALL COMPLETE", "11:20 IST"], 9)
    strip(img, x, y + h - 14, w, "Weather office")


def art_ai(img, x, y, w, h):
    img.fill_rect(x, y, w, h, NAVY)
    # faint grid
    for gy in range(y + 24, y + h - 14, 18):
        img.hline(x + 8, x + 178, gy, (40, 70, 120))
    # falling red chart (left 60%)
    pts = [(x + 10, y + 26), (x + 40, y + 34), (x + 70, y + 30),
           (x + 100, y + 52), (x + 125, y + 48), (x + 150, y + 76),
           (x + 175, y + 92)]
    img.poly(pts + [(x + 175, y + h - 14), (x + 10, y + h - 14)], (110, 22, 22))
    for i in range(len(pts) - 1):
        img.line(pts[i][0], pts[i][1], pts[i + 1][0], pts[i + 1][1], (235, 70, 60))
        img.line(pts[i][0], pts[i][1] + 1, pts[i + 1][0], pts[i + 1][1] + 1,
                 (235, 70, 60))
    img.circle(pts[-1][0], pts[-1][1], 4, (235, 70, 60))
    # market figures, right column
    img.fill_rect(x + 186, y, w - 186, h, (12, 26, 52))
    rows = [("Taipei", "\u22126.2%"), ("Seoul", "\u22125.2%"),
            ("Tokyo", "\u22125.1%"), ("Hong Kong", "\u22121.9%")]
    yy = y + 34
    for name, val in rows:
        FONT.draw(img, "sansb", 12, x + 194, yy, name, WHITE)
        vw = FONT.width("sansb", 12, val)
        FONT.draw(img, "sansb", 12, x + w - 8 - vw, yy, val, (235, 90, 80))
        yy += 21
    banner(img, x, y, "AI SELL-OFF", 12, 22)
    strip(img, x, y + h - 14, w, "Closing prices")


# ---------------------------------------------------------------- medium art
def art_ukeu(img, x, y, w, h):
    img.fill_rect(x, y, w, h, (0, 51, 153))
    # Union Jack, left half
    img.fill_rect(x, y, w // 2, h, (1, 33, 105))
    img.line(x, y, x + w // 2, y + h, WHITE)
    img.line(x + w // 2, y, x, y + h, WHITE)
    img.line(x, y + 2, x + w // 2, y + h - 2, WHITE)
    img.fill_rect(x + w // 4 - 5, y, 10, h, WHITE)
    img.fill_rect(x, y + h // 2 - 5, w // 2, 10, WHITE)
    img.fill_rect(x + w // 4 - 3, y, 6, h, (200, 16, 46))
    img.fill_rect(x, y + h // 2 - 3, w // 2, 6, (200, 16, 46))
    # EU stars, right half
    cx, cy = x + w // 2 + (w - w // 2) // 2, y + h // 2
    for k in range(12):
        import math
        a = 2 * math.pi * k / 12 - math.pi / 2
        img.circle(int(cx + 24 * math.cos(a)), int(cy + 20 * math.sin(a)),
                   2, YELLOW)
    banner(img, x, y, "UK\u2013EU DEAL", 9, 13)
    strip(img, x, y + h - 12, w, "Agreed \u00b7 Reuters", 8, 12)


def art_cop31(img, x, y, w, h):
    img.fill_rect(x, y, w, h, (18, 90, 110))
    img.fill_rect(x, y, w, 22, (58, 130, 165))
    # globe
    cx, cy = x + 52, y + 38
    img.circle(cx, cy, 22, (40, 110, 180))
    img.poly([(cx - 14, cy - 8), (cx - 2, cy - 14), (cx + 8, cy - 6),
              (cx + 2, cy + 2), (cx - 8, cy + 4)], GREEN)
    img.poly([(cx - 6, cy + 8), (cx + 12, cy + 6), (cx + 14, cy + 16),
              (cx - 2, cy + 18)], GREEN)
    # thermometer
    img.fill_rect(x + 118, y + 18, 8, 30, WHITE)
    img.circle(x + 122, y + 50, 8, RED)
    img.fill_rect(x + 120, y + 30, 4, 18, RED)
    img.fill_rect(x + 150, y + 18, 22, 34, (200, 60, 50))
    FONT.draw(img, "sansb", 9, x + 154, y + 40, "NO", WHITE)
    banner(img, x, y, "COP31: NO DEAL", 9, 13)
    strip(img, x, y + h - 12, w, "Ongoing \u00b7 UN News", 8, 12)


def art_poland(img, x, y, w, h):
    img.fill_rect(x, y, w, h, (208, 224, 232))
    img.fill_rect(x, y + 40, w, h - 40, (110, 160, 90))
    img.fill_rect(x, y + 52, w, h - 52, (80, 135, 70))
    # missile: slim body, pointed nose, tail fins, smoke trail
    img.ellipse(x + 108, y + 22, 24, 4, (90, 90, 96))
    img.poly([(x + 130, y + 18), (x + 146, y + 22), (x + 130, y + 26)],
             (70, 70, 76))
    img.poly([(x + 86, y + 18), (x + 96, y + 12), (x + 96, y + 18)],
             (70, 70, 76))
    img.poly([(x + 86, y + 26), (x + 96, y + 26), (x + 96, y + 32)],
             (70, 70, 76))
    for i, (sx, sy, sr) in enumerate([(70, 26, 5), (52, 30, 7), (32, 34, 9)]):
        img.circle(x + sx, y + sy, sr, (235, 235, 235))
    banner(img, x, y, "POLAND: MISSILE", 9, 13)
    strip(img, x, y + h - 12, w, "Minister says \u00b7 Reuters", 8, 12)


def art_iraq(img, x, y, w, h):
    img.fill_rect(x, y, w, h, (222, 196, 140))
    img.fill_rect(x, y, w, 20, (240, 220, 180))
    # palms
    for px, ph in [(30, 26), (52, 32)]:
        img.line(x + px, y + h - 12, x + px + 4, y + h - 12 - ph, (120, 82, 40))
        for dx, dy in [(-12, -6), (-8, -12), (0, -14), (10, -10), (14, -4)]:
            img.ellipse(x + px + 4 + dx, y + h - 12 - ph + dy, 9, 3, GREEN)
    # tank
    img.fill_rect(x + 104, y + h - 30, 62, 14, (90, 100, 60))
    img.fill_rect(x + 118, y + h - 40, 30, 11, (80, 90, 55))
    img.line(x + 148, y + h - 36, x + 178, y + h - 40, (60, 65, 40))
    for wx in (112, 126, 140, 154):
        img.circle(x + wx, y + h - 14, 4, (40, 40, 40))
    banner(img, x, y, "IRAQ: ARMY IN", 9, 13)
    strip(img, x, y + h - 12, w, "Witnessed \u00b7 Reuters", 8, 12)


def art_italy(img, x, y, w, h):
    img.fill_rect(x, y, w, h, (196, 206, 216))
    # crowd: rows of heads
    import math
    skins = [(232, 190, 150), (200, 150, 110), (240, 205, 170), (180, 130, 95)]
    for row, yy in enumerate((34, 46, 58)):
        for i in range(7):
            cx = x + 14 + i * 26 + (row % 2) * 10
            img.circle(cx, y + yy, 7, skins[(i + row) % 4])
            img.fill_rect(cx - 7, y + yy + 6, 14, 6, (60, 70, 90))
    # placards
    img.fill_rect(x + 96, y + 16, 26, 12, WHITE)
    img.border(x + 96, y + 16, 26, 12, INK, 1)
    img.line(x + 108, y + 28, x + 108, y + 44, INK)
    banner(img, x, y, "ITALY: STRIKE", 9, 13)
    white_box(img, x + w - 62, y + 2, 58, 12, ["SCIOPERO"], 8)
    strip(img, x, y + h - 12, w, "Reported \u00b7 Reuters", 8, 12)


def art_japan(img, x, y, w, h):
    img.fill_rect(x, y, w, h, CREAM)
    img.circle(x + 42, y + 34, 22, (188, 0, 45))
    # rising bars
    for i, bh in enumerate((10, 16, 24, 32)):
        img.fill_rect(x + 92 + i * 20, y + h - 14 - bh, 13, bh, (90, 90, 96))
    img.fill_rect(x + 92 + 3 * 20, y + h - 14 - 32, 13, 32, RED)
    banner(img, x, y, "JAPAN: +2.3%", 9, 13)
    strip(img, x, y + h - 12, w, "Official data \u00b7 Reuters", 8, 12)


def art_seoul(img, x, y, w, h):
    img.fill_rect(x, y, w, h, (214, 222, 228))
    # parliament: base + columns + roof
    img.fill_rect(x + 28, y + 46, 128, 8, (240, 240, 240))
    img.fill_rect(x + 34, y + 26, 116, 20, (245, 245, 245))
    for cx in range(40, 152, 16):
        img.fill_rect(x + cx, y + 28, 5, 18, (120, 120, 125))
    img.poly([(x + 28, y + 26), (x + 92, y + 8), (x + 156, y + 26)],
             (160, 30, 30))
    img.circle(x + 92, y + 14, 5, (160, 30, 30))
    banner(img, x, y, "SEOUL: IMPEACH", 9, 13)
    strip(img, x, y + h - 12, w, "Party decision \u00b7 Korea Herald", 8, 12)


def art_kenya(img, x, y, w, h):
    img.fill_rect(x, y, w, h, (232, 120, 40))
    img.fill_rect(x, y + 34, w, h - 34, (200, 90, 30))
    img.circle(x + 142, y + 26, 14, YELLOW)
    # derrick silhouette
    img.line(x + 62, y + h - 12, x + 84, y + 12, BLACK)
    img.line(x + 102, y + h - 12, x + 84, y + 12, BLACK)
    img.line(x + 68, y + h - 22, x + 96, y + h - 22, BLACK)
    img.line(x + 74, y + h - 34, x + 90, y + h - 34, BLACK)
    img.fill_rect(x + 80, y + 8, 8, 8, BLACK)
    img.fill_rect(x + 40, y + h - 16, w - 80, 4, BLACK)
    banner(img, x, y, "KENYA: OIL", 9, 13)
    strip(img, x, y + h - 12, w, "Ceremony held \u00b7 allAfrica", 8, 12)


def art_bukele(img, x, y, w, h):
    img.fill_rect(x, y, w, h, (31, 78, 121))
    # ballot box + paper
    img.poly([(x + 84, y + 8), (x + 100, y + 20), (x + 92, y + 26),
              (x + 78, y + 16)], WHITE)
    img.fill_rect(x + 62, y + 28, 64, 26, WHITE)
    img.fill_rect(x + 62, y + 28, 64, 4, (200, 200, 200))
    img.fill_rect(x + 82, y + 36, 24, 3, (60, 60, 60))
    img.fill_rect(x + 62, y + 54, 64, 4, (220, 220, 220))
    banner(img, x, y, "BUKELE: 3RD BID", 9, 13)
    strip(img, x, y + h - 12, w, "Filed \u00b7 AP", 8, 12)


def art_phillips(img, x, y, w, h):
    img.fill_rect(x, y, w, h, (46, 125, 50))
    img.fill_rect(x, y + 40, w, h - 40, (120, 170, 90))
    # stumps
    for sx in (140, 147, 154):
        img.fill_rect(x + sx, y + 26, 3, 22, YELLOW)
    # bat
    img.poly([(x + 40, y + 52), (x + 78, y + 14), (x + 88, y + 22),
              (x + 50, y + 58)], (222, 184, 135))
    img.line(x + 82, y + 18, x + 96, y + 6, (190, 150, 100))
    # ball
    img.circle(x + 118, y + 16, 7, (178, 34, 34))
    img.circle(x + 116, y + 14, 2, WHITE)
    banner(img, x, y, "PHILLIPS: 118", 9, 13)
    strip(img, x, y + h - 12, w, "Scorecard \u00b7 ICC", 8, 12)


MEDIUM_ART = [art_ukeu, art_cop31, art_poland, art_iraq, art_italy,
              art_japan, art_seoul, art_kenya, art_bukele, art_phillips]
LEAD_ART = [art_kyiv, art_akvan, art_ai]


# ---------------------------------------------------------------- map
CONTINENTS = [
    # North America
    [(-168, 66), (-145, 70), (-125, 71), (-110, 73), (-95, 80), (-85, 76),
     (-75, 72), (-65, 60), (-55, 47), (-60, 45), (-70, 42), (-75, 35),
     (-81, 26), (-84, 30), (-90, 21), (-97, 16), (-105, 20), (-110, 23),
     (-117, 33), (-124, 40), (-124, 49), (-132, 58), (-145, 60),
     (-158, 58), (-165, 60)],
    # Greenland
    [(-46, 60), (-32, 68), (-22, 70), (-25, 76), (-40, 80), (-55, 76),
     (-58, 70), (-53, 64)],
    # South America
    [(-79, 9), (-72, 12), (-62, 10), (-52, 5), (-50, -2), (-42, -5),
     (-35, -8), (-38, -15), (-40, -22), (-48, -28), (-55, -35), (-62, -41),
     (-68, -50), (-70, -44), (-72, -36), (-73, -28), (-78, -18),
     (-81, -8), (-80, -2)],
    # Africa
    [(-17, 15), (-16, 21), (-10, 31), (-5, 35), (0, 36), (10, 37),
     (15, 32), (22, 33), (30, 31), (33, 27), (35, 23), (39, 21),
     (43, 12), (48, 11), (51, 10), (46, 0), (40, -8), (36, -18),
     (32, -26), (28, -33), (20, -35), (16, -29), (12, -18), (13, -12),
     (9, 4), (4, 6), (-8, 5), (-13, 8), (-17, 12)],
    # Europe
    [(-10, 36), (-9, 43), (-2, 44), (-1, 46), (0, 50), (3, 52), (6, 54),
     (8, 57), (12, 56), (18, 56), (21, 55), (24, 58), (26, 60), (28, 62),
     (24, 65), (20, 68), (16, 70), (12, 68), (8, 62), (5, 58), (0, 52),
     (-4, 48), (-8, 43), (-10, 38)],
    # Asia
    [(28, 62), (32, 66), (40, 68), (50, 69), (60, 70), (70, 72), (80, 73),
     (95, 76), (110, 74), (125, 72), (140, 72), (155, 70), (170, 67),
     (178, 65), (170, 60), (162, 58), (158, 52), (150, 45), (142, 42),
     (140, 38), (135, 34), (129, 33), (127, 35), (122, 31), (120, 25),
     (116, 22), (110, 20), (108, 18), (105, 10), (103, 7), (100, 7),
     (98, 10), (95, 16), (92, 21), (89, 22), (86, 20), (80, 15),
     (77, 8), (75, 12), (72, 20), (68, 22), (62, 25), (58, 26),
     (54, 27), (50, 29), (48, 30), (44, 29), (42, 33), (40, 36),
     (36, 36), (33, 36), (30, 36), (28, 39), (26, 41), (24, 42),
     (22, 40), (26, 45), (28, 45), (28, 48), (30, 50), (30, 55), (28, 58)],
    # Australia
    [(113, -22), (113, -26), (114, -32), (115, -35), (120, -34),
     (124, -33), (129, -32), (132, -32), (136, -35), (138, -35),
     (140, -38), (145, -38), (148, -39), (150, -37), (153, -32),
     (153, -27), (150, -22), (146, -19), (143, -15), (142, -11),
     (139, -14), (136, -12), (132, -12), (128, -14), (124, -15),
     (120, -18), (116, -20)],
    # Japan
    [(130, 31), (132, 33), (135, 34), (138, 35), (140, 37), (141, 39),
     (140, 42), (143, 43), (141, 45), (140, 41), (137, 36), (133, 34)],
    # New Zealand
    [(167, -45), (170, -42), (173, -39), (175, -37), (176, -40),
     (172, -43), (168, -46)],
]

# (lon, lat, story number) — Europe pins nudged a few px apart; the map
# is small and five stories share one small region ("positions approximate").
PINS = [
    (30.5, 50.4, "1"), (85.0, 19.3, "2"), (121.5, 25.0, "3"),
    (2.0, 52.0, "4"), (33.0, 36.0, "5"), (24.0, 53.0, "6"),
    (44.2, 32.8, "7"), (11.0, 40.0, "8"), (139.7, 35.7, "9"),
    (127.0, 37.5, "10"), (36.0, 3.5, "11"), (-89.2, 13.7, "12"),
    (174.8, -41.3, "13"),
]

LANDC = (228, 214, 178)


def draw_map(img, x, y, w, h):
    def px(lon, lat):
        return (x + int((lon + 180.0) / 360.0 * w),
                y + int((84.0 - lat) / 142.0 * h))

    for cont in CONTINENTS:
        img.poly([px(lon, lat) for lon, lat in cont], LANDC)
    # Indonesia dots
    for lon, lat in [(95, -4), (105, -6), (113, -7), (120, -8),
                     (128, -4), (135, -4), (140, -6)]:
        ex, ey = px(lon, lat)
        img.ellipse(ex, ey, 5, 2, LANDC)
    for lon, lat, num in PINS:
        cx, cy = px(lon, lat)
        img.circle(cx, cy, 6, RED)
        img.circle(cx, cy, 6, WHITE, fill=False)
        nw = FONT.width("sansb", 7.5, num)
        FONT.draw(img, "sansb", 7.5, cx - nw / 2, cy + 3, num, WHITE)


# ---------------------------------------------------------------- page
WARNINGS = []


def autofit(face, text, start, minimum, maxw):
    size = start
    while size > minimum and FONT.width(face, size, text) > maxw:
        size -= 1
    return size


def draw_page():
    img = Img()
    # kicker row
    FONT.draw(img, "sansb", 14, MX, 26, "THE WORLD IN ONE DAY", RED)
    right = "35 STORIES \u00b7 7 REGIONS \u00b7 EVERY ONE DATED FRIDAY 20 NOVEMBER 2026"
    rw = FONT.width("sansb", 10.5, right)
    FONT.draw(img, "sansb", 10.5, MX + CW - rw, 26, right, INK)
    img.fill_rect(MX, 32, CW, 2, INK)

    # masthead
    title = "Friday 20 November 2026"
    tsize = autofit("serifb", title, 66, 40, CW)
    FONT.draw(img, "serifb", tsize, MX, 100, title, INK)
    sub = ("Russian missiles hit Kyiv\u2019s bridges \u00b7 Cyclone Akvan strikes "
           "India \u00b7 An AI sell-off sinks Asia\u2019s markets \u00b7 UK and EU "
           "seal a deal")
    ssize = autofit("serifi", sub, 17, 12, CW)
    FONT.draw(img, "serifi", ssize, MX, 122, sub, INK)
    img.fill_rect(MX, 132, CW, 1, INK)

    # numbers row
    colw = CW / 6.0
    for i, (num, cap) in enumerate(NUMBERS):
        cx = MX + int(i * colw)
        if i:
            img.fill_rect(cx - 6, 142, 2, 48, RED)
        FONT.draw(img, "serifb", 25, cx + 4, 164, num, INK)
        lines = FONT.wrap("serif", 10.5, cap, colw - 16)
        yy = 179
        for ln in lines[:2]:
            FONT.draw(img, "serif", 10.5, cx + 4, yy, ln, INK)
            yy += 12
        if len(lines) > 2:
            WARNINGS.append("numbers caption overflow: %s" % cap)

    # region bar
    ry, rh = 198, 20
    widths = [FONT.width("sansb", 10.5, t) + 18 for t, _ in REGIONS]
    gap = (CW - sum(widths)) / (len(REGIONS) - 1)
    rx = MX
    for (label, color), wd in zip(REGIONS, widths):
        img.fill_rect(int(rx), ry, int(wd), rh, color)
        tw = FONT.width("sansb", 10.5, label)
        FONT.draw(img, "sansb", 10.5, rx + (wd - tw) / 2, ry + 15, label, WHITE)
        rx += wd + gap

    # lead row: art 130 tall, then kicker / headline / summary
    lead_x = [MX, MX + 328, MX + 656]
    for art, (kick, head, summ), lx in zip(LEAD_ART, LEADS, lead_x):
        art(img, lx, 226, 312, 130)
        FONT.draw(img, "sansb", 10.5, lx, 372, kick, RED)
        lines = FONT.wrap("serifb", 20, head, 312)
        yy = 394
        for ln in lines[:2]:
            FONT.draw(img, "serifb", 20, lx, yy, ln, INK)
            yy += 22
        if len(lines) > 2:
            WARNINGS.append("lead headline overflow: %s" % head)
        slines = FONT.wrap("serif", 12, summ, 312)
        yy = 432
        for ln in slines[:3]:
            FONT.draw(img, "serif", 12, lx, yy, ln, INK)
            yy += 15
        if len(slines) > 3:
            WARNINGS.append("lead summary overflow (%d lines): %s"
                            % (len(slines), head))

    # medium rows: art 66 tall, then kicker / headline / summary
    med_x = [MX + i * 196 for i in range(5)]
    for row in range(2):
        ay = 474 + row * 154
        ty = ay + 80
        for col in range(5):
            idx = row * 5 + col
            kick, head, summ = MEDIUMS[idx]
            MEDIUM_ART[idx](img, med_x[col], ay, 184, 66)
            FONT.draw(img, "sansb", 9.5, med_x[col], ty, kick, RED)
            lines = FONT.wrap("serifb", 15, head, 184)
            yy = ty + 18
            for ln in lines[:2]:
                FONT.draw(img, "serifb", 15, med_x[col], yy, ln, INK)
                yy += 17
            if len(lines) > 2:
                WARNINGS.append("medium headline overflow: %s" % head)
            slines = FONT.wrap("serif", 10.5, summ, 184)
            yy = ty + 18 + 17 * min(2, len(lines))
            for ln in slines[:2]:
                FONT.draw(img, "serif", 10.5, med_x[col], yy, ln, INK)
                yy += 13
            if len(slines) > 2:
                WARNINGS.append("medium summary overflow: %s" % head)

    # bottom band: map left, ALSO right
    FONT.draw(img, "sansb", 12, MX, 792, "WHERE IT HAPPENED", RED)
    FONT.draw(img, "sansb", 12, 470, 792,
              "ALSO ON FRIDAY 20 NOVEMBER \u2014 22 MORE STORIES", RED)
    draw_map(img, MX, 800, 428, 112)
    FONT.draw(img, "serif", 9.5, MX, 926,
              "Numbers match the stories above. Positions are approximate.",
              GREY)
    colw2 = 258
    for ci in range(2):
        cx = 470 + ci * (colw2 + 10)
        for ri in range(11):
            num, place, text, src = ALSO[ci * 11 + ri]
            yy = 800 + ri * 12 + 10
            FONT.draw(img, "sansb", 8.5, cx, yy, num, GREEN_NUM)
            nw = FONT.width("sansb", 8.5, num)
            line = " %s %s (%s)" % (place, text, src)
            lw = FONT.width("serif", 8.5, line)
            if lw + nw > colw2:
                WARNINGS.append("ALSO overflow: %s %s" % (num, place))
            FONT.draw(img, "serif", 8.5, cx + nw, yy, line, INK)

    # DATE CHECK box
    img.border(MX, 934, CW, 44, RED, 2)
    label = "DATE CHECK  "
    lw = FONT.width("sansb", 10.5, label)
    FONT.draw(img, "sansb", 10.5, MX + 8, 950, "DATE CHECK", RED)
    rest = DATE_CHECK[len("DATE CHECK  "):]
    first = FONT.wrap("serif", 10.5, rest, CW - 24 - lw)
    FONT.draw(img, "serif", 10.5, MX + 8 + lw, 950, first[0], INK)
    yy = 964
    for ln in first[1:3]:
        FONT.draw(img, "serif", 10.5, MX + 8, yy, ln, INK)
        yy += 13
    if len(first) > 3:
        WARNINGS.append("DATE CHECK overflow: %d lines" % len(first))

    # footer
    left = ("Every story here happened, or was first reported, on Friday "
            "20 November 2026. Officials\u2019 counts are attributed.")
    FONT.draw(img, "serif", 9.5, MX, 992, left, INK)
    right = "Sources named beside each story \u00b7 original drawings"
    rw = FONT.width("serif", 9.5, right)
    FONT.draw(img, "serif", 9.5, MX + CW - rw, 992, right, INK)
    return img


def main():
    load_font()
    img = draw_page()
    outdir = os.environ.get("MAKEFUN_OUTPUT_DIR", "")
    path = os.path.join(outdir, "entry.png") if outdir else "entry.png"
    if outdir:
        os.makedirs(outdir, exist_ok=True)
    n = write_png(img.px, path)
    print("wrote %s (%d bytes)" % (path, n))
    for w in WARNINGS:
        print("WARNING:", w)
    if not WARNINGS:
        print("no layout warnings")


if __name__ == "__main__":
    main()
