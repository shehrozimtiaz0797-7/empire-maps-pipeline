"""Historical borders: loads the yearly GeoJSON maps and turns one empire into picture layers.

Border data: historical-basemaps by Andre Ourednik (GPL-3.0), downloaded on first use.
"""
import json
import math
import os
import urllib.request

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

BASE_URL = "https://raw.githubusercontent.com/aourednik/historical-basemaps/master/geojson/"


def year_file(y):
    return "world_%s.geojson" % (("bc%d" % -y) if y < 0 else y)


def load_year(y, data_dir):
    path = os.path.join(data_dir, year_file(y))
    if not os.path.exists(path):
        os.makedirs(data_dir, exist_ok=True)
        tmp = path + ".part"
        urllib.request.urlretrieve(BASE_URL + year_file(y), tmp)
        os.replace(tmp, path)
    with open(path, encoding="utf-8") as f:
        return json.load(f)["features"]


def polygons(geom):
    """List of polygons; each polygon is a list of rings [(lon, lat), ...] (first ring = outside)."""
    if not geom:
        return []
    t, c = geom.get("type"), geom.get("coordinates") or []
    if t == "Polygon":
        return [c]
    if t == "MultiPolygon":
        return c
    return []


def matches(feat, names):
    p = feat.get("properties") or {}
    return p.get("NAME") in names or p.get("SUBJECTO") in names


def ring_area_centroid(pts):
    a = cx = cy = 0.0
    n = len(pts)
    for i in range(n):
        x0, y0 = pts[i]
        x1, y1 = pts[(i + 1) % n]
        cr = x0 * y1 - x1 * y0
        a += cr
        cx += (x0 + x1) * cr
        cy += (y0 + y1) * cr
    if abs(a) < 1e-9:
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        return 0.0, (sum(xs) / n, sum(ys) / n)
    a *= 0.5
    return abs(a), (cx / (6 * a), cy / (6 * a))


class Topic:
    """Everything needed to draw one empire across its years on one shared canvas."""

    def __init__(self, names, years, data_dir, max_px=6200, max_ppd=42.0, log=print):
        self.names = set(names)
        self.years = list(years)
        self.feats = {y: load_year(y, data_dir) for y in self.years}
        self.land_feats = load_year(2010, data_dir)
        self.log = log

        # lon/lat points of the empire in every year (used for the canvas size and the wrap check)
        lons, lats = [], []
        for y in self.years:
            for f in self.feats[y]:
                if matches(f, self.names):
                    for poly in polygons(f.get("geometry")):
                        for lon, lat in poly[0][::3]:
                            lons.append(lon)
                            lats.append(lat)
        if not lons:
            raise ValueError("empire not found in the border data: %s" % ", ".join(sorted(self.names)))
        lons = np.array(lons)
        lats = np.array(lats)
        # Empires across the 180° line (Russia): shift the west part by 360 if that makes the map narrower.
        w_norm = np.percentile(lons, 99.5) - np.percentile(lons, 0.5)
        shifted = np.where(lons < 0, lons + 360, lons)
        w_shift = np.percentile(shifted, 99.5) - np.percentile(shifted, 0.5)
        self.wrap = bool(w_shift < w_norm * 0.7)
        L = shifted if self.wrap else lons
        lo, hi = np.percentile(L, 0.3), np.percentile(L, 99.7)
        la_lo, la_hi = np.percentile(lats, 0.3), np.percentile(lats, 99.7)
        self.lat_c = float(np.clip((la_lo + la_hi) / 2, -60, 60))
        self.k = math.cos(math.radians(self.lat_c))  # east-west squeeze for this latitude
        wdeg = (hi - lo) * self.k
        hdeg = la_hi - la_lo
        # roomy canvas: portrait frames need much more north-south space than the empire itself
        mx = max(18.0, 0.45 * (hi - lo))
        my = max(30.0, 0.9 * hdeg, 0.9 * wdeg)
        self.lon0, self.lon1 = lo - mx, hi + mx
        self.lat0, self.lat1 = la_lo - my, la_hi + my  # lat1 = top
        span_x = (self.lon1 - self.lon0) * self.k
        span_y = self.lat1 - self.lat0
        self.ppd = float(min(max_ppd, max_px / span_x, max_px / span_y))
        self.W = int(span_x * self.ppd)
        self.H = int(span_y * self.ppd)
        self.log("canvas %dx%d, %.1f px/deg, wrap=%s" % (self.W, self.H, self.ppd, self.wrap))

    # lon/lat -> canvas pixel
    def xy(self, lon, lat):
        if self.wrap and lon < 0:
            lon += 360
        return ((lon - self.lon0) * self.k * self.ppd, (self.lat1 - lat) * self.ppd)

    def _ring_px(self, ring):
        pts = [self.xy(lon, lat) for lon, lat in ring]
        if self.wrap:
            return pts
        # a ring that jumps across the map edge (180°) would draw a band over the whole map: skip those jumps
        return pts

    def _fill(self, draw, feats, value=255):
        for f in feats:
            for poly in polygons(f.get("geometry")):
                if len(poly[0]) < 3:
                    continue
                draw.polygon(self._ring_px(poly[0]), fill=value)
                for hole in poly[1:]:
                    if len(hole) >= 3:
                        draw.polygon(self._ring_px(hole), fill=0)

    def land(self):
        img = Image.new("L", (self.W, self.H), 0)
        self._fill(ImageDraw.Draw(img), self.land_feats)
        # older maps sometimes reach where 2010 coasts do not (and the other way round): add every year's shapes too
        d = ImageDraw.Draw(img)
        for y in self.years:
            self._fill(d, self.feats[y])
        return img

    def borders(self, y):
        img = Image.new("L", (self.W, self.H), 0)
        d = ImageDraw.Draw(img)
        w = max(1, int(round(self.ppd / 22)))
        for f in self.feats[y]:
            for poly in polygons(f.get("geometry")):
                if len(poly[0]) >= 3:
                    d.line(self._ring_px(poly[0]) + [self._ring_px(poly[0])[0]], fill=255, width=w)
        return img

    def empire(self, y):
        img = Image.new("L", (self.W, self.H), 0)
        self._fill(ImageDraw.Draw(img), [f for f in self.feats[y] if matches(f, self.names)])
        return img

    def neighbours(self, y, n=12):
        """Biggest other countries this year: [(name, x, y, area_px)]."""
        best = {}
        for f in self.feats[y]:
            if matches(f, self.names):
                continue
            name = (f.get("properties") or {}).get("NAME")
            if not name or "hunter" in name.lower() or "culture" in name.lower() or "peoples" in name.lower():
                continue
            for poly in polygons(f.get("geometry")):
                if len(poly[0]) < 3:
                    continue
                a, c = ring_area_centroid(self._ring_px(poly[0]))
                if a > best.get(name, (0,))[0]:
                    best[name] = (a, c)
        out = sorted(((v[0], k, v[1]) for k, v in best.items()), reverse=True)[:n]
        return [(k, c[0], c[1], a) for a, k, c in out]


def edge_glow(mask, ppd):
    r = max(3, int(ppd / 9)) | 1
    band = Image.fromarray(np.clip(np.asarray(mask.filter(ImageFilter.MaxFilter(r)), np.int16)
                                   - np.asarray(mask.filter(ImageFilter.MinFilter(r)), np.int16), 0, 255).astype(np.uint8))
    return band.filter(ImageFilter.GaussianBlur(max(1.5, ppd / 18)))


def mask_box(mask):
    """Bounding box of the empire, ignoring tiny far-away islands: (x0, y0, x1, y1, cx, cy)."""
    small = mask.resize((max(1, mask.width // 8), max(1, mask.height // 8)), Image.BILINEAR)
    a = np.asarray(small, np.float32)
    tot = a.sum()
    if tot <= 0:
        return None
    ys, xs = np.nonzero(a > 40)
    if len(xs) == 0:
        return None
    w = a[ys, xs]

    def wq(v, q):
        order = np.argsort(v)
        c = np.cumsum(w[order])
        return v[order][min(len(v) - 1, np.searchsorted(c, q * c[-1]))]

    x0, x1 = wq(xs, 0.01), wq(xs, 0.99)
    y0, y1 = wq(ys, 0.01), wq(ys, 0.99)
    cx = float((xs * w).sum() / w.sum())
    cy = float((ys * w).sum() / w.sum())
    s = 8.0
    return (x0 * s, y0 * s, (x1 + 1) * s, (y1 + 1) * s, cx * s, cy * s)
