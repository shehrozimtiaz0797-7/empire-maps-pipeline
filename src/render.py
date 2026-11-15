"""Empire Maps: draws the animated map Short (1080x1920, 30 fps) and pipes the frames to ffmpeg.

Usage: python render.py spec.json
spec: topic {label, names, years}, scenes [{year, markers, arrow}], lines, line_starts, line_ends,
      hook_text, intro, voice_end, total, fonts, ffmpeg, out, data_dir
"""
import json
import math
import os
import subprocess
import sys
import time

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

sys.path.insert(0, os.path.dirname(__file__))
from geo import Topic, edge_glow, mask_box  # noqa: E402

spec = json.load(open(sys.argv[1]))
W, H, FPS = 1080, 1920, 30
TOTAL = float(spec["total"])
INTRO = float(spec["intro"])
VEND = float(spec["voice_end"])
scenes = spec["scenes"]
starts = spec["line_starts"]
ends = spec["line_ends"]
lines = spec["lines"]
t0 = time.time()


def log(*a):
    print("[render]", *a, flush=True)


# ---------------- colours ----------------
OCEAN_TOP = np.array([10, 30, 44], np.float32)
OCEAN_BOT = np.array([16, 48, 66], np.float32)
LAND = np.array([214, 196, 152], np.float32)
LAND_DARK = np.array([186, 166, 120], np.float32)
BORDER = (110, 88, 58)
EMPIRE = (176, 32, 38)
GLOW = (255, 206, 92)
NEW = (255, 228, 120)
GOLD = (242, 193, 78)
WHITE = (255, 255, 255)

# ---------------- fonts ----------------
def font(path, size, weight=None):
    f = ImageFont.truetype(path, size)
    if weight:
        try:
            f.set_variation_by_name(weight)
        except Exception:
            pass
    return f


F_SERIF = spec["font_serif"]
F_BOLD = spec["font_bold"]
F_MED = spec["font_medium"]
f_title = font(F_SERIF, 76, "Bold")
f_title_big = font(F_SERIF, 96, "Bold")
f_year = font(F_SERIF, 168, "Bold")
f_label = font(F_SERIF, 64, "Bold")
f_brand = font(F_BOLD, 30)
f_cap = font(F_BOLD, 56)
f_marker = font(F_BOLD, 34)
f_nb = font(F_MED, 28)
f_small = font(F_MED, 22)
f_tick = font(F_MED, 26)

# ---------------- map layers ----------------
topic = spec["topic"]
years = sorted(set(s["year"] for s in scenes))
geo = Topic(topic["names"], years, spec["data_dir"], log=log)
land = geo.land()
log("land drawn", round(time.time() - t0, 1), "s")

# base picture: ocean gradient + parchment land with a soft shadow and coast line
gy = np.linspace(0, 1, geo.H, dtype=np.float32)[:, None, None]
ocean = OCEAN_TOP * (1 - gy) + OCEAN_BOT * gy
ocean = np.broadcast_to(ocean, (geo.H, geo.W, 3)).copy()
la = np.asarray(land, np.float32)[:, :, None] / 255.0
rng = np.random.default_rng(7)
small_noise = rng.normal(0, 1, (geo.H // 16 + 1, geo.W // 16 + 1)).astype(np.float32)
noise = np.asarray(Image.fromarray(((small_noise + 3) * 40).clip(0, 255).astype(np.uint8)).resize((geo.W, geo.H), Image.BICUBIC), np.float32)[:, :, None] / 255.0
land_col = LAND_DARK * (1 - noise) + LAND * noise
shadow = np.asarray(land.filter(ImageFilter.GaussianBlur(max(2, geo.ppd / 6))), np.float32)[:, :, None] / 255.0
base = ocean * (1 - 0.35 * shadow)
base = base * (1 - la) + land_col * la
coast = np.asarray(edge_glow(land, geo.ppd * 0.6), np.float32)[:, :, None] / 255.0
base = base * (1 - 0.35 * coast) + np.array([60, 50, 36], np.float32) * 0.35 * coast
base_img = Image.fromarray(base.clip(0, 255).astype(np.uint8))
del ocean, la, base, noise, shadow, coast, land_col, small_noise

layers = {}
prev_mask = None
for y in years:
    m = geo.empire(y)
    new = None
    if prev_mask is not None:
        new = Image.fromarray(np.clip(np.asarray(m, np.int16) - np.asarray(prev_mask, np.int16), 0, 255).astype(np.uint8))
        new = new.filter(ImageFilter.MinFilter(3))
    layers[y] = {
        "mask": m,
        "glow": edge_glow(m, geo.ppd),
        "borders": geo.borders(y),
        "new": new,
        "box": mask_box(m),
        "nb": geo.neighbours(y),
    }
    prev_mask = m
log("layers ready", round(time.time() - t0, 1), "s")

# ---------------- camera ----------------
VIEW = (70, 390, 1010, 1280)  # where the empire should fit on screen (below the title, above the year)
VCX, VCY = (VIEW[0] + VIEW[2]) / 2, (VIEW[1] + VIEW[3]) / 2
MIN_DEG = 22.0  # never zoom closer than this many degrees across


def camera_for(year, extra=1.0):
    b = layers[year]["box"]
    if b is None:
        b = (geo.W * 0.4, geo.H * 0.4, geo.W * 0.6, geo.H * 0.6, geo.W * 0.5, geo.H * 0.5)
    x0, y0, x1, y1, _, _ = b
    bw, bh = max(1.0, x1 - x0), max(1.0, y1 - y0)
    s = min((VIEW[2] - VIEW[0]) / (bw * 1.12), (VIEW[3] - VIEW[1]) / (bh * 1.12))
    s = min(s, W / (MIN_DEG * geo.ppd))  # frame px per canvas px
    s /= extra
    # smallest zoom that still fits in the canvas
    s = max(s, W / geo.W, H / geo.H)
    return [(x0 + x1) / 2, (y0 + y1) / 2, s]


def crop_box(cam):
    cx, cy, s = cam
    left = cx - VCX / s
    top = cy - VCY / s
    w, h = W / s, H / s
    left = min(max(0, left), geo.W - w)
    top = min(max(0, top), geo.H - h)
    return (left, top, left + w, top + h)


def ease(x):
    x = min(1.0, max(0.0, x))
    return x * x * (3 - 2 * x)


def lerp_cam(a, b, t):
    t = ease(t)
    return [a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t, math.exp(math.log(a[2]) + (math.log(b[2]) - math.log(a[2])) * t)]


cams = [camera_for(s["year"]) for s in scenes]
# the last line pulls back to show the whole story
all_box = None
for y in years:
    b = layers[y]["box"]
    if b:
        all_box = b if all_box is None else (min(all_box[0], b[0]), min(all_box[1], b[1]), max(all_box[2], b[2]), max(all_box[3], b[3]), 0, 0)
if len(cams) > 1:
    x0, y0, x1, y1 = all_box[:4]
    s = min((VIEW[2] - VIEW[0]) / ((x1 - x0) * 1.1), (VIEW[3] - VIEW[1]) / ((y1 - y0) * 1.1))
    s = max(s, W / geo.W, H / geo.H)
    cams[-1] = [(x0 + x1) / 2, (y0 + y1) / 2, min(cams[-1][2], s)]
wide = list(cams[0])
wide[2] = max(cams[0][2] / 2.6, W / geo.W, H / geo.H)


def camera_at(t):
    if t < INTRO:
        return lerp_cam(wide, cams[0], (t - 0.2) / max(0.5, INTRO + 0.6))
    i = scene_at(t)
    st = starts[i]
    prev = cams[i - 1] if i > 0 else lerp_cam(wide, cams[0], 1.0)
    cam = lerp_cam(prev, cams[i], (t - st) / 1.3)
    # slow push-in during the scene
    nxt = starts[i + 1] if i + 1 < len(starts) else TOTAL
    push = 1 + 0.035 * ease((t - st) / max(1, nxt - st))
    return [cam[0], cam[1], cam[2] * push]


def scene_at(t):
    i = 0
    for k, s in enumerate(starts):
        if t >= s - 0.05:
            i = k
    return i


# ---------------- overlays drawn once ----------------
def vignette():
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    d = np.sqrt(((xx - W / 2) / (W * 0.75)) ** 2 + ((yy - H * 0.45) / (H * 0.7)) ** 2)
    a = np.clip((d - 0.55) * 1.2, 0, 1) ** 1.6 * 200
    # dark bands for text: top title, bottom year + captions
    top = np.clip(1 - yy / 470, 0, 1) ** 1.3 * 235
    bot = np.clip((yy - 1250) / 420, 0, 1) ** 1.1 * 225
    a = np.maximum(a, np.maximum(top, bot))
    img = np.zeros((H, W, 4), np.uint8)
    img[:, :, 3] = a.clip(0, 255).astype(np.uint8)
    img[:, :, :3] = (6, 10, 16)
    return Image.fromarray(img, "RGBA")


VIG = vignette()


def wrap(text, f, width):
    words, out, cur = text.split(), [], ""
    for w in words:
        trial = (cur + " " + w).strip()
        if f.getlength(trial) <= width or not cur:
            cur = trial
        else:
            out.append(cur)
            cur = w
    if cur:
        out.append(cur)
    return out


def year_text(y):
    y = int(round(y))
    if y == 0:
        y = 1  # there is no year 0
    if y < 0:
        return "%d BC" % (-y)
    if y < 1000:
        return "%d AD" % y
    return str(y)


# word timing for the captions: inside each line, words share the time by their length
word_times = []
for i, ln in enumerate(lines):
    ws = ln.split()
    st, en = starts[i], ends[i]
    weights = [len(w) + 2 for w in ws]
    tot = float(sum(weights)) or 1.0
    acc, wt = 0.0, []
    for w, k in zip(ws, weights):
        wt.append((w, st + (en - st) * acc / tot))
        acc += k
    word_times.append(wt)

hook = spec["hook_text"].upper()
first_year, last_year = years[0], years[-1]


def text_c(d, xy, txt, f, fill, stroke=4, sfill=(0, 0, 0), anchor="mm", spacing=0):
    d.text(xy, txt, font=f, fill=fill, stroke_width=stroke, stroke_fill=sfill, anchor=anchor)


def spaced(d, cx, cy, txt, f, fill, gap, stroke=0, sfill=(0, 0, 0)):
    widths = [f.getlength(c) for c in txt]
    total = sum(widths) + gap * (len(txt) - 1)
    x = cx - total / 2
    for c, w in zip(txt, widths):
        d.text((x, cy), c, font=f, fill=fill, anchor="lm", stroke_width=stroke, stroke_fill=sfill)
        x += w + gap


def draw_arrow(d, p0, p1, prog, col=(255, 222, 120)):
    if prog <= 0:
        return
    (x0, y0), (x1, y1) = p0, p1
    mx, my = (x0 + x1) / 2, (y0 + y1) / 2
    dx, dy = x1 - x0, y1 - y0
    L = math.hypot(dx, dy) or 1
    cx, cy = mx - dy / L * L * 0.22, my + dx / L * L * 0.22
    n = 40
    pts = []
    for k in range(int(n * prog) + 1):
        u = k / n
        pts.append(((1 - u) ** 2 * x0 + 2 * (1 - u) * u * cx + u * u * x1, (1 - u) ** 2 * y0 + 2 * (1 - u) * u * cy + u * u * y1))
    if len(pts) < 2:
        return
    d.line(pts, fill=(20, 10, 8), width=17, joint="curve")
    d.line(pts, fill=col, width=10, joint="curve")
    hx, hy = pts[-1]
    px, py = pts[-2]
    ang = math.atan2(hy - py, hx - px)
    size = 34
    head = [(hx + math.cos(ang) * size * 0.6, hy + math.sin(ang) * size * 0.6),
            (hx + math.cos(ang + 2.5) * size, hy + math.sin(ang + 2.5) * size),
            (hx + math.cos(ang - 2.5) * size, hy + math.sin(ang - 2.5) * size)]
    d.polygon(head, fill=col, outline=(20, 10, 8))


def to_frame(lon, lat, box):
    x, y = geo.xy(lon, lat)
    sx = W / (box[2] - box[0])
    return ((x - box[0]) * sx, (y - box[1]) * sx)


# ---------------- frames ----------------
nframes = int(TOTAL * FPS)
cmd = [spec["ffmpeg"], "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", "%dx%d" % (W, H), "-r", str(FPS), "-i", "-",
       "-c:v", "libx264", "-preset", "veryfast", "-crf", "19", "-pix_fmt", "yuv420p", "-r", str(FPS), spec["out"]]
ff = subprocess.Popen(cmd, stdin=subprocess.PIPE)

year_order = {y: i for i, y in enumerate(years)}
border_col = Image.new("RGB", (W, H), BORDER)
empire_col = Image.new("RGB", (W, H), EMPIRE)
glow_col = Image.new("RGB", (W, H), GLOW)
new_col = Image.new("RGB", (W, H), NEW)


def layer(y, key, box):
    im = layers[y][key]
    return im.resize((W, H), Image.BILINEAR, box=box)


for fi in range(nframes):
    t = fi / FPS
    i = scene_at(t) if t >= INTRO - 0.05 else 0
    sc = scenes[i]
    y_now = sc["year"]
    y_prev = scenes[i - 1]["year"] if i > 0 else y_now
    st = starts[i] if t >= INTRO - 0.05 else 0.0
    trans = ease((t - st) / 1.1) if y_prev != y_now else 1.0

    cam = camera_at(t)
    box = crop_box(cam)
    frame = base_img.resize((W, H), Image.BILINEAR, box=box)

    def blended(key):
        a = layer(y_now, key, box)
        if trans >= 1.0 or y_prev == y_now:
            return a
        return Image.blend(layer(y_prev, key, box), a, trans)

    bmask = blended("borders").point(lambda v: v * 0.55)
    frame = Image.composite(border_col, frame, bmask)
    emask = blended("mask").point(lambda v: v * 0.80)
    frame = Image.composite(empire_col, frame, emask)
    gmask = blended("glow").point(lambda v: min(255, v * 1.1))
    frame = Image.composite(glow_col, frame, gmask)
    new = layers[y_now]["new"]
    if new is not None and y_prev != y_now:
        fl = max(0.0, 1 - (t - st) / 2.2) * min(1.0, (t - st) / 0.35)
        if fl > 0.01:
            nmask = new.resize((W, H), Image.BILINEAR, box=box).point(lambda v, f=fl: v * 0.6 * f)
            frame = Image.composite(new_col, frame, nmask)

    d = ImageDraw.Draw(frame, "RGBA")
    sx = W / (box[2] - box[0])

    # neighbour names (small, quiet)
    shown = 0
    for name, nx, ny, area in layers[y_now]["nb"]:
        fx, fy = (nx - box[0]) * sx, (ny - box[1]) * sx
        if not (60 < fx < W - 60 and 430 < fy < 1250):
            continue
        if area * sx * sx < 9000:
            continue
        label = name if len(name) <= 22 else name[:21] + "."
        d.text((fx, fy), label.upper(), font=f_nb, fill=(70, 52, 30, 200), anchor="mm")
        shown += 1
        if shown >= 5:
            break

    # empire name on the map
    b = layers[y_now]["box"]
    if b:
        ex, ey = (b[4] - box[0]) * sx, (b[5] - box[1]) * sx
        ex = min(max(ex, 230), W - 230)
        ey = min(max(ey, 470), 1220)
        a = int(255 * ease((t - st - 0.3) / 0.6)) if t >= INTRO else 0
        for m in (sc.get("markers") or []) if t >= INTRO else []:
            try:
                mx, my = to_frame(float(m["lon"]), float(m["lat"]), box)
            except Exception:
                continue
            if abs(my - ey) < 85 and abs(mx - ex) < 330:
                ey = my + 95 if my < 1100 else my - 140
        if a > 0:
            lab = topic["label"]
            fsz = f_label if f_label.getlength(lab) < 860 else font(F_SERIF, 46, "Bold")
            spaced(d, ex, ey, lab, fsz, (255, 240, 200, a), 4, stroke=5, sfill=(40, 8, 8, a))

    # markers and arrow for this scene
    if t >= INTRO:
        for k, m in enumerate(sc.get("markers") or []):
            try:
                mx, my = to_frame(float(m["lon"]), float(m["lat"]), box)
            except Exception:
                continue
            ap = ease((t - st - 0.5 - 0.3 * k) / 0.4)
            if ap <= 0 or not (-50 < mx < W + 50 and 380 < my < 1300):
                continue
            pulse = (t * 1.6 + k * 0.3) % 1.0
            r = 14 + 26 * pulse
            d.ellipse((mx - r, my - r, mx + r, my + r), outline=(255, 230, 140, int(200 * (1 - pulse) * ap)), width=4)
            d.ellipse((mx - 11, my - 11, mx + 11, my + 11), fill=(255, 214, 90, int(255 * ap)), outline=(30, 16, 6, int(255 * ap)), width=4)
            name = str(m.get("name", ""))[:22]
            lx = min(max(mx, 40 + f_marker.getlength(name) / 2), W - 40 - f_marker.getlength(name) / 2)
            d.text((lx, my - 42), name, font=f_marker, fill=(255, 255, 255, int(255 * ap)), stroke_width=5, stroke_fill=(10, 8, 6, int(255 * ap)), anchor="mm")
        ar = sc.get("arrow")
        if ar:
            try:
                p0 = to_frame(float(ar["from"]["lon"]), float(ar["from"]["lat"]), box)
                p1 = to_frame(float(ar["to"]["lon"]), float(ar["to"]["lat"]), box)
                draw_arrow(d, p0, p1, ease((t - st - 0.5) / 1.3))
            except Exception:
                pass

    # dark bands, vignette
    frame.paste(VIG, (0, 0), VIG)
    d = ImageDraw.Draw(frame, "RGBA")

    # brand
    spaced(d, W / 2, 62, "EMPIRE MAPS", f_brand, (242, 193, 78, 230), 10)

    # title: big in the middle during the intro, then at the top
    if t < INTRO + 0.4:
        flash = max(0.0, 1 - t / 0.35)
        if flash > 0:
            d.rectangle((0, 0, W, H), fill=(255, 245, 220, int(200 * flash)))
        a = int(255 * min(1.0, t / 0.25))
        y_mid = 860 - 30 * ease(t / INTRO)
        lines_t = wrap(hook, f_title_big, 940)
        move = ease((t - INTRO + 0.25) / 0.65)
        y_top = 150
        for k, ln in enumerate(lines_t):
            yy = (y_mid + (k - (len(lines_t) - 1) / 2) * 108) * (1 - move) + (y_top + k * 84) * move
            ff_ = f_title_big if move < 0.5 else f_title
            text_c(d, (W / 2, yy), ln, ff_, (255, 248, 230, a), stroke=6, sfill=(0, 0, 0, a))
    else:
        for k, ln in enumerate(wrap(hook, f_title, 960)[:3]):
            text_c(d, (W / 2, 150 + k * 84), ln, f_title, (255, 248, 230), stroke=6)

    # year counter + timeline
    if t >= INTRO - 0.2:
        yv = y_prev + (y_now - y_prev) * ease((t - st) / 0.9) if t >= INTRO else y_now
        txt = year_text(yv)
        d.text((W / 2 + 4, 1402), txt, font=f_year, fill=(0, 0, 0, 160), anchor="mm")
        text_c(d, (W / 2, 1396), txt, f_year, GOLD, stroke=3, sfill=(40, 22, 4))
        x0, x1, ty = 120, 960, 1508
        d.line((x0, ty, x1, ty), fill=(255, 255, 255, 90), width=4)
        span = (last_year - first_year) or 1
        for y in years:
            tx = x0 + (x1 - x0) * (y - first_year) / span
            on = y <= y_now
            d.ellipse((tx - 7, ty - 7, tx + 7, ty + 7), fill=(242, 193, 78, 255) if on else (255, 255, 255, 110))
        px = x0 + (x1 - x0) * (yv - first_year) / span
        d.line((x0, ty, px, ty), fill=(242, 193, 78, 255), width=5)
        d.ellipse((px - 13, ty - 13, px + 13, ty + 13), fill=(255, 226, 140), outline=(40, 22, 4), width=3)
        d.text((x0, ty + 36), year_text(first_year), font=f_tick, fill=(255, 255, 255, 150), anchor="lm")
        d.text((x1, ty + 36), year_text(last_year), font=f_tick, fill=(255, 255, 255, 150), anchor="rm")

    # captions: the current line, the spoken word in gold
    if INTRO <= t <= VEND + 0.3:
        li = None
        for k in range(len(lines)):
            if starts[k] - 0.1 <= t <= (starts[k + 1] - 0.1 if k + 1 < len(lines) else VEND + 0.3):
                li = k
        if li is not None:
            wt = word_times[li]
            cur = 0
            for k, (w, wt0) in enumerate(wt):
                if t >= wt0:
                    cur = k
            rows, row = [], []
            for k, (w, _) in enumerate(wt):
                trial = " ".join(x for x, _ in row + [(w, 0)])
                if row and f_cap.getlength(trial) > 960:
                    rows.append(row)
                    row = []
                row.append((w, k))
            rows.append(row)
            # show at most two rows: the ones around the current word
            ri = next(r for r, rw in enumerate(rows) if any(k == cur for _, k in rw))
            first = min(ri, max(0, len(rows) - 2)) if ri < len(rows) - 1 else max(0, ri - 1)
            for rr, rw in enumerate(rows[first:first + 2]):
                widths = [f_cap.getlength(w + " ") for w, _ in rw]
                x = W / 2 - sum(widths) / 2
                yy = 1648 + rr * 74
                for (w, k), wd in zip(rw, widths):
                    col = GOLD if k == cur else ((255, 255, 255) if k < cur else (255, 255, 255, 170))
                    d.text((x, yy), w, font=f_cap, fill=col, stroke_width=5, stroke_fill=(0, 0, 0), anchor="lm")
                    x += wd

    # outro
    if t > VEND + 0.2:
        a = int(255 * ease((t - VEND - 0.2) / 0.5))
        text_c(d, (W / 2, 1660), "WHICH EMPIRE NEXT?", f_title, (255, 248, 230, a), stroke=6, sfill=(0, 0, 0, a))
        text_c(d, (W / 2, 1752), "Tell me in the comments", f_cap, (242, 193, 78, a), stroke=5, sfill=(0, 0, 0, a))

    # subscribe button from the closing line on (views were high but almost nobody subscribed)
    if t > starts[-1] + 0.8:
        a = int(255 * ease((t - starts[-1] - 0.8) / 0.4))
        pop = 1 + 0.06 * max(0.0, 1 - (t - starts[-1] - 0.8) / 0.3)
        txt = "SUBSCRIBE FOR THE NEXT EMPIRE"
        tw = f_marker.getlength(txt) * pop
        bx0, bx1, by0, by1 = W / 2 - tw / 2 - 34, W / 2 + tw / 2 + 34, 1836 - 34 * pop, 1836 + 34 * pop
        d.rounded_rectangle((bx0, by0, bx1, by1), radius=34, fill=(204, 0, 0, a), outline=(255, 255, 255, a), width=3)
        d.text((W / 2, 1836), txt, font=f_marker, fill=(255, 255, 255, a), anchor="mm")
    d.text((W / 2, 1885), "Borders: historical-basemaps (A. Ourednik, GPL-3.0)", font=f_small, fill=(255, 255, 255, 70), anchor="mm")

    ff.stdin.write(frame.tobytes())
    if fi % 300 == 0:
        log("frame", fi, "/", nframes, round(time.time() - t0, 1), "s")

ff.stdin.close()
ff.wait()
if ff.returncode != 0:
    sys.exit("ffmpeg failed")
log("done", round(time.time() - t0, 1), "s")
