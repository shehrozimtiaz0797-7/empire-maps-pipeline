"""Empire Maps long video (16:9) from long.json: title card, chapter cards and map shots of the empire in each
year (real borders, newly won land glows), slow camera moves and soft dissolves, calm music under the narration,
word-by-word captions, a small preview and a thumbnail.
Usage: python long/longtools.py long.json"""
import json
import os
import re
import subprocess
import sys
import wave
from difflib import SequenceMatcher

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

spec = json.load(open(sys.argv[1]))
HERE = os.path.dirname(os.path.abspath(__file__))
ENG = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ENG, "src"))
from geo import Topic, edge_glow, mask_box  # noqa: E402

W, H, FPS = 1920, 1080, 25
BW, BH = 2880, 1620  # stills are drawn bigger so the camera can move inside them
FF = spec.get("ffmpeg", "ffmpeg")
WORK = spec["work"]
BRAND = spec.get("brand", "EMPIRE MAPS")
FONT_SERIF = os.path.join(ENG, "fonts", "Lora-Variable.ttf")
FONT_BOLD = os.path.join(ENG, "fonts", "Poppins-Bold.ttf")
FONT_MED = os.path.join(ENG, "fonts", "Poppins-Medium.ttf")
OCEAN = ((14, 30, 48), (8, 18, 30))
LAND = ((176, 160, 128), (150, 134, 104))
BORDER = (70, 60, 46)
EMPIRE = (176, 36, 36)
NEW = (255, 196, 70)
GLOW = (255, 214, 120)
ACCENT = (255, 196, 70)
CREAM = (255, 246, 232)
DARK = (12, 8, 4)


def log(*a):
    print(*a, flush=True)


def font(p, size, bold=False):
    f = ImageFont.truetype(p, size)
    if bold:
        try:
            f.set_variation_by_name("Bold")
        except Exception:
            pass
    return f


def sh(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise SystemExit("ffmpeg failed: " + r.stderr[-1500:])


def text_c(d, xy, t, f, fill=CREAM, stroke=6, sfill=DARK, anchor="mm"):
    d.text(xy, t, font=f, fill=fill, anchor=anchor, stroke_width=stroke, stroke_fill=sfill)


def fit_lines(d, text, f, maxw):
    words, lines, cur = text.split(), [], ""
    for w in words:
        nxt = (cur + " " + w).strip()
        if d.textlength(nxt, font=f) <= maxw or not cur:
            cur = nxt
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def year_text(y):
    return f"{-y} BC" if y < 0 else (f"{y} AD" if y < 1000 else str(y))


# ---------- the map ----------
topic = spec["topic"]
tl = spec["timeline"]
years_needed = sorted({int(i["year"]) for i in tl if "year" in i} | {int(i["prev"]) for i in tl if i.get("prev") is not None})
geo = Topic(topic["names"], sorted(set(topic["years"]) | set(years_needed)), spec["data_dir"], max_px=4600, log=lambda *a: None)
_extra = 0.45 * (geo.lon1 - geo.lon0)
geo.lon0 -= _extra
geo.lon1 += _extra
geo.W = int((geo.lon1 - geo.lon0) * geo.k * geo.ppd)
gy = np.linspace(0, 1, geo.H, dtype=np.float32)[:, None, None]
ocean = np.array(OCEAN[0], np.float32) * (1 - gy) + np.array(OCEAN[1], np.float32) * gy
base = np.broadcast_to(ocean, (geo.H, geo.W, 3)).copy()
la = np.asarray(geo.land(), np.float32)[:, :, None] / 255
rng = np.random.default_rng(3)
nz = np.asarray(Image.fromarray(((rng.normal(0, 1, (geo.H // 16 + 1, geo.W // 16 + 1)) + 3) * 40).clip(0, 255).astype(np.uint8)).resize((geo.W, geo.H), Image.BICUBIC), np.float32)[:, :, None] / 255
base = base * (1 - la) + (np.array(LAND[1], np.float32) * (1 - nz) + np.array(LAND[0], np.float32) * nz) * la
BASE = Image.fromarray(base.clip(0, 255).astype(np.uint8))
del base, la, nz, ocean
_masks = {}


def emask(y):
    if y not in _masks:
        _masks[y] = geo.empire(y)
    return _masks[y]


def painted(year, prev=None):
    """Whole canvas: land, borders of that year, the empire in red, land won since `prev` in gold."""
    m = emask(year)
    pic = BASE.copy()
    pic.paste(Image.new("RGB", pic.size, BORDER), (0, 0), geo.borders(year).point(lambda v: int(v * 0.8)))
    pic.paste(Image.new("RGB", pic.size, EMPIRE), (0, 0), m.point(lambda v: int(v * 0.88)))
    if prev is not None and prev != year:
        pm = np.asarray(emask(prev), np.int16)
        gain = Image.fromarray(np.clip(np.asarray(m, np.int16) - pm, 0, 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(1))
        if np.asarray(gain).mean() > 0.02:
            pic.paste(Image.new("RGB", pic.size, NEW), (0, 0), gain.point(lambda v: int(v * 0.75)))
        lost = Image.fromarray(np.clip(pm - np.asarray(m, np.int16), 0, 255).astype(np.uint8))
        if np.asarray(lost).mean() > 0.02:
            pic.paste(Image.new("RGB", pic.size, EMPIRE), (0, 0), lost.point(lambda v: int(v * 0.35)))
    pic.paste(Image.new("RGB", pic.size, GLOW), (0, 0), edge_glow(m, geo.ppd))
    return pic


def frame_box(year, prev=None, zoom="wide"):
    """Canvas box (16:9) around the empire this year (and last year, so lost land stays in view)."""
    boxes = [b for b in (mask_box(emask(year)), mask_box(emask(prev)) if prev is not None else None) if b]
    if not boxes:
        return (0, 0, geo.W, geo.H)
    x0 = min(b[0] for b in boxes); y0 = min(b[1] for b in boxes)
    x1 = max(b[2] for b in boxes); y1 = max(b[3] for b in boxes)
    pad = {"wide": 1.75, "mid": 1.35, "close": 1.12}[zoom]
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    bw = max((x1 - x0) * pad, (y1 - y0) * pad * 16 / 9, 14 * geo.ppd)
    bh = bw * 9 / 16
    cy += bh * 0.04  # a little room for the captions at the bottom
    return fit_box((cx - bw / 2, cy - bh / 2, cx + bw / 2, cy + bh / 2))


def fit_box(box):
    x0, y0, x1, y1 = box
    bw, bh = x1 - x0, y1 - y0
    if bw <= geo.W:
        x0 = min(max(x0, 0), geo.W - bw)
    if bh <= geo.H:
        y0 = min(max(y0, 0), geo.H - bh)
    return (x0, y0, x0 + bw, y0 + bh)


def crop_canvas(pic, box, size):
    x0, y0, x1, y1 = [int(v) for v in box]
    out = Image.new("RGB", (x1 - x0, y1 - y0), OCEAN[1])
    ix0, iy0, ix1, iy1 = max(0, x0), max(0, y0), min(pic.width, x1), min(pic.height, y1)
    if ix1 > ix0 and iy1 > iy0:
        out.paste(pic.crop((ix0, iy0, ix1, iy1)), (ix0 - x0, iy0 - y0))
    return out.resize(size, Image.LANCZOS)


def label_neighbours(img, year, box, n=6):
    """Names of the biggest neighbours, small and quiet, so viewers know where they are."""
    d = ImageDraw.Draw(img)
    sx = img.width / (box[2] - box[0]); sy = img.height / (box[3] - box[1])
    f = font(FONT_MED, int(30 * img.width / W))
    placed = []
    for name, x, y, area in geo.neighbours(year, 14):
        px, py = (x - box[0]) * sx, (y - box[1]) * sy
        if not (img.width * 0.06 < px < img.width * 0.94 and img.height * 0.12 < py < img.height * 0.78):
            continue
        if area * sx * sy < (img.width * 0.012) ** 2:
            continue
        if any(abs(px - qx) < img.width * 0.14 and abs(py - qy) < img.height * 0.06 for qx, qy in placed):
            continue
        d.text((px, py), name.upper(), font=f, fill=(242, 232, 210), anchor="mm", stroke_width=3, stroke_fill=(40, 30, 20))
        placed.append((px, py))
        if len(placed) >= n:
            break


def empire_label(img, year, box):
    m = emask(year)
    b = mask_box(m)
    if not b:
        return
    sx = img.width / (box[2] - box[0]); sy = img.height / (box[3] - box[1])
    px, py = (b[4] - box[0]) * sx, (b[5] - box[1]) * sy
    py = min(py, img.height * 0.72)
    label = (topic.get("labels") or {}).get(str(year), topic["label"])
    d = ImageDraw.Draw(img)
    size = int(52 * img.width / W)
    f = font(FONT_SERIF, size, True)
    while d.textlength(label, font=f) > img.width * 0.5 and size > 26:
        size -= 4
        f = font(FONT_SERIF, size, True)
    d.text((px, py), label, font=f, fill=CREAM, anchor="mm", stroke_width=6, stroke_fill=(60, 8, 8))


def corner_marks(d, year, sc=1.0):
    d.rounded_rectangle((40 * sc, 36 * sc, 330 * sc, 92 * sc), int(14 * sc), fill=(20, 14, 8))
    d.text((185 * sc, 64 * sc), BRAND, font=font(FONT_BOLD, int(30 * sc)), fill=ACCENT, anchor="mm")
    text_c(d, ((W - 50) * sc, 70 * sc), year_text(year), font(FONT_SERIF, int(92 * sc), True), ACCENT, int(6 * sc), anchor="rt")


def map_still(year, prev, zoom, out):
    box = frame_box(year, prev, zoom)
    img = crop_canvas(painted(year, prev), box, (BW, BH))
    label_neighbours(img, year, box)
    empire_label(img, year, box)
    img.save(out, quality=93)


def overlay(year):
    ov = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    corner_marks(ImageDraw.Draw(ov), year, 1.0)
    return ov


def chapter_still(year, heading, chapter, out):
    box = frame_box(year, None, "mid")
    img = crop_canvas(painted(year), box, (BW, BH)).convert("RGBA")
    img = Image.alpha_composite(img, Image.new("RGBA", img.size, (0, 0, 0, 120)))
    d = ImageDraw.Draw(img)
    s = BW / W
    text_c(d, (BW / 2, 360 * s), f"CHAPTER {chapter}", font(FONT_BOLD, int(40 * s)), ACCENT, int(3 * s))
    f = font(FONT_SERIF, int(104 * s), True)
    lines = fit_lines(d, heading.upper(), f, 1600 * s)
    for k, ln in enumerate(lines[:2]):
        text_c(d, (BW / 2, (470 + k * 120) * s), ln, f, CREAM, int(7 * s))
    text_c(d, (BW / 2, (470 + len(lines[:2]) * 120 + 40) * s), year_text(year), font(FONT_SERIF, int(64 * s), True), ACCENT, int(5 * s))
    img.convert("RGB").save(out, quality=93)


def title_still(out):
    peak = int(topic.get("peak") or topic["years"][len(topic["years"]) // 2])
    box = frame_box(peak, None, "wide")
    img = crop_canvas(painted(peak), box, (BW, BH)).convert("RGBA")
    img = Image.alpha_composite(img, Image.new("RGBA", img.size, (0, 0, 0, 140)))
    d = ImageDraw.Draw(img)
    s = BW / W
    text_c(d, (BW / 2, 330 * s), BRAND, font(FONT_BOLD, int(44 * s)), ACCENT, int(3 * s))
    f = font(FONT_SERIF, int(100 * s), True)
    lines = fit_lines(d, spec["title"].upper(), f, 1650 * s)
    for k, ln in enumerate(lines[:3]):
        text_c(d, (BW / 2, (470 + k * 120) * s), ln, f, CREAM, int(7 * s))
    img.convert("RGB").save(out, quality=93)


def outro_still(out):
    last = int(topic.get("peak") or topic["years"][len(topic["years"]) // 2])
    box = frame_box(last, None, "wide")
    img = crop_canvas(painted(last), box, (BW, BH)).convert("RGBA")
    img = Image.alpha_composite(img, Image.new("RGBA", img.size, (0, 0, 0, 160)))
    d = ImageDraw.Draw(img)
    s = BW / W
    text_c(d, (BW / 2, 450 * s), "WHICH EMPIRE NEXT?", font(FONT_SERIF, int(120 * s), True), CREAM, int(7 * s))
    text_c(d, (BW / 2, 600 * s), "Tell me in the comments  •  Subscribe for a new empire map every day", font(FONT_MED, int(46 * s)), ACCENT, int(3 * s))
    img.convert("RGB").save(out, quality=93)


def thumbnail(out):
    peak = int(topic.get("peak") or topic["years"][len(topic["years"]) // 2])
    box = frame_box(peak, None, "mid")
    # shift the map to the right so the words fit on the left
    bw = box[2] - box[0]
    box = fit_box((box[0] - bw * 0.22, box[1], box[2] - bw * 0.22, box[3]))
    img = crop_canvas(painted(peak), box, (1280, 720))
    empire_label(img, peak, box)
    img = img.convert("RGBA")
    g = Image.new("RGBA", (1280, 720), (0, 0, 0, 0))
    gd = ImageDraw.Draw(g)
    for x in range(700):
        gd.line((x, 0, x, 720), fill=(0, 0, 0, int(215 * (1 - x / 700))))
    img = Image.alpha_composite(img, g)
    d = ImageDraw.Draw(img)
    words = (spec.get("thumb_text") or spec["title"]).upper().split()[:4]
    f = font(FONT_SERIF, 118 if len(words) <= 3 else 98, True)
    y = 380 - (len(words) - 1) * 60
    for k, w in enumerate(words):
        d.text((50, y + k * 122), w, font=f, fill=ACCENT if k == len(words) - 1 else CREAM, anchor="lm", stroke_width=8, stroke_fill=(0, 0, 0))
    d.rounded_rectangle((40, 40, 330, 100), 14, fill=ACCENT)
    d.text((185, 70), BRAND, font=font(FONT_BOLD, 34), fill=DARK, anchor="mm")
    a, b = int(topic["years"][0]), int(topic["years"][-1])
    d.text((50, 670), f"{year_text(a)} – {year_text(b)}", font=font(FONT_BOLD, 40), fill=CREAM, anchor="lm", stroke_width=4, stroke_fill=(0, 0, 0))
    img.convert("RGB").save(out, quality=92)


# ---------- video: one pass, frames piped to ffmpeg ----------
def ease(x):
    return x * x * (3 - 2 * x)


def cam(k, u):
    """Camera inside a big still: (zoom, x 0..1, y 0..1) at progress u for shot k."""
    mode = k % 4
    e = ease(u)
    if mode == 0:
        return 1.0 + 0.10 * e, 0.5, 0.5
    if mode == 1:
        return 1.10 - 0.10 * e, 0.5, 0.5
    if mode == 2:
        return 1.08, 0.25 + 0.5 * e, 0.5
    return 1.08, 0.75 - 0.5 * e, 0.5


silent = os.path.join(WORK, "_video.mp4")
enc = subprocess.Popen([FF, "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
                        "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p", silent], stdin=subprocess.PIPE)
prev_frame = None
XF = int(0.7 * FPS)  # dissolve between shots
total_frames = 0
for k, it in enumerate(tl):
    still = os.path.join(WORK, f"_still{k}.jpg")
    kind = it["kind"]
    if kind == "title":
        title_still(still)
    elif kind == "outro":
        outro_still(still)
    elif kind == "chapter":
        chapter_still(int(it["year"]), it["heading"], it["chapter"], still)
    else:
        map_still(int(it["year"]), it.get("prev"), it.get("zoom", "wide"), still)
    big = Image.open(still).convert("RGB")
    ov = overlay(int(it["year"])) if kind == "map" else None
    n = max(2, int(round(float(it["dur"]) * FPS)))
    gentle = kind != "map"
    for i in range(n):
        z, cx, cy = cam(k, i / (n - 1))
        if gentle:
            z = 1.0 + (z - 1.0) * 0.4
        cw, ch = BW / z, BH / z
        x0 = (BW - cw) * cx
        y0 = (BH - ch) * cy
        fr = big.resize((W, H), Image.BILINEAR, box=(x0, y0, x0 + cw, y0 + ch))
        if ov is not None:
            fr = Image.alpha_composite(fr.convert("RGBA"), ov).convert("RGB")
        if prev_frame is not None and i < XF:
            fr = Image.blend(prev_frame, fr, (i + 1) / (XF + 1))
        enc.stdin.write(fr.tobytes())
        last = fr
    prev_frame = last
    total_frames += n
    os.remove(still)
    if k % 10 == 0:
        log(f"shots {k + 1}/{len(tl)}")
enc.stdin.close()
if enc.wait() != 0:
    raise SystemExit("video encoder failed")
log("video frames:", total_frames)


# ---------- captions: script words timed by speech recognition ----------
def norm(w):
    return re.sub(r"[^a-z0-9]", "", w.lower())


_WM = None


def timed_words(v):
    global _WM
    words = v["text"].split()
    whis = []
    try:
        from faster_whisper import WhisperModel
        if _WM is None:
            _WM = WhisperModel(os.environ.get("WHISPER_MODEL", "base.en"), device="cpu", compute_type="int8")
        segs, _ = _WM.transcribe(v["file"], language="en", word_timestamps=True, vad_filter=False, beam_size=1)
        for sg in segs:
            for w in sg.words or []:
                whis.append((norm(w.word), float(w.start), float(w.end)))
    except Exception as e:
        log("word timing fallback:", e)
    off = float(v["start"])
    dur = float(v.get("dur") or 0)
    times = [None] * len(words)
    if whis:
        a = [norm(w) for w in words]
        b = [w[0] for w in whis]
        for blk in SequenceMatcher(None, a, b, autojunk=False).get_matching_blocks():
            for j in range(blk.size):
                times[blk.a + j] = (whis[blk.b + j][1], whis[blk.b + j][2])
    if not dur:
        dur = sum(len(w) for w in words) * 0.065
    known = [i for i, t in enumerate(times) if t]
    if not known:
        tot = sum(len(w) + 1 for w in words)
        t0 = 0.0
        for i, w in enumerate(words):
            d = dur * (len(w) + 1) / tot
            times[i] = (t0, t0 + d * 0.9)
            t0 += d
    else:
        i = 0
        while i < len(words):
            if times[i]:
                i += 1
                continue
            j = i
            while j < len(words) and not times[j]:
                j += 1
            lo = times[i - 1][1] if i > 0 else 0.0
            hi = times[j][0] if j < len(words) else dur
            span = max(0.05, hi - lo)
            tot = sum(len(words[q]) + 1 for q in range(i, j))
            t0 = lo
            for q in range(i, j):
                d = span * (len(words[q]) + 1) / tot
                times[q] = (t0, t0 + d * 0.9)
                t0 += d
            i = j
    log(f"captions: chunk at {off:.0f}s, {len(known)}/{len(words)} words timed")
    return [(w, off + t[0], off + t[1]) for w, t in zip(words, times)]


def ass_time(t):
    t = max(0.0, t)
    return "%d:%02d:%02d.%02d" % (int(t // 3600), int(t % 3600 // 60), int(t % 60), int(t * 100 % 100))


def write_ass(path):
    allw = []
    for v in spec["voice"]:
        allw += timed_words(v)
    lines, cur = [], []
    for k, (w, s0, s1) in enumerate(allw):
        cur.append((w, s0, s1))
        text = " ".join(x[0] for x in cur)
        nxt = allw[k + 1] if k + 1 < len(allw) else None
        if (nxt is None or len(cur) >= 7 or len(text) >= 32 or re.search(r"[.!?;:]$", w)
                or (nxt and nxt[1] - s1 > 0.6) or (len(cur) >= 4 and w.endswith(","))):
            lines.append(cur)
            cur = []
    ev = []
    for ln in lines:
        st, en = ln[0][1], ln[-1][2] + 0.25
        parts = []
        for k, (w, s0, s1) in enumerate(ln):
            nxt = ln[k + 1][1] if k + 1 < len(ln) else s1
            parts.append("{\\kf%d}%s" % (max(1, int(round((nxt - s0) * 100))), w.replace("{", "(").replace("}", ")")))
        ev.append("Dialogue: 0,%s,%s,Cap,,0,0,0,,%s" % (ass_time(st), ass_time(en), " ".join(parts)))
    head = """[Script Info]
ScriptType: v4.00+
PlayResX: 1920
PlayResY: 1080
WrapStyle: 0

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Cap,Poppins,66,&H0046C4FF,&H00FFFFFF,&H00000000,&H96000000,-1,0,0,0,100,100,0,0,1,5,2,2,120,120,70,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    open(path, "w", encoding="utf-8").write(head + "\n".join(ev) + "\n")
    return len(ev)


# ---------- music: calm, slow and warm, quieter under the voice ----------
SR = 24000
T = float(spec["total"])
N = int(T * SR) + SR
t = np.arange(N, dtype=np.float32) / SR
mus = np.zeros(N, np.float32)
chords = [(146.83, 174.61, 220.0), (130.81, 164.81, 196.0), (116.54, 146.83, 174.61), (110.0, 138.59, 164.81)]
bar = 8.0
for i, chd in enumerate(chords * int(T / (bar * 4) + 2)):
    a, b = int(i * bar * SR), int((i + 1) * bar * SR)
    if a >= N:
        break
    b = min(b, N)
    tt = t[a:b] - t[a]
    env_ = np.minimum(1, tt / 2.0) * np.minimum(1, (bar - tt) / 2.0)
    for f0 in chd:
        mus[a:b] += 0.05 * env_ * (np.sin(2 * np.pi * f0 * tt) + 0.35 * np.sin(2 * np.pi * f0 * 2.002 * tt))
    mus[a:b] += 0.06 * env_ * np.sin(2 * np.pi * chd[0] / 2 * tt)
drum = np.exp(-np.arange(int(0.7 * SR)) / (0.16 * SR)) * np.sin(2 * np.pi * 50 * np.arange(int(0.7 * SR)) / SR)
beat = 0.0
while beat < T:
    i = int(beat * SR)
    if i + len(drum) < N:
        mus[i:i + len(drum)] += 0.16 * drum
    beat += 4.0
fade = np.minimum(1, t / 3) * np.minimum(1, np.maximum(0, (T - t)) / 4)
mus = (mus * fade / max(1e-6, np.abs(mus).max()) * 0.9 * 32767).astype(np.int16)
mwav = os.path.join(WORK, "_music.wav")
with wave.open(mwav, "wb") as wv:
    wv.setnchannels(1)
    wv.setsampwidth(2)
    wv.setframerate(SR)
    wv.writeframes(mus.tobytes())

ins, flt = [], []
for i, v in enumerate(spec["voice"]):
    ins += ["-i", v["file"]]
    ms = int(float(v["start"]) * 1000)
    flt.append(f"[{i + 1}:a]aresample=48000,adelay={ms}|{ms},apad[v{i}]")
nv = len(spec["voice"])
flt.append("".join(f"[v{i}]" for i in range(nv)) + f"amix=inputs={nv}:normalize=0:duration=longest,atrim=0:{T:.2f}[voice]")
flt.append(f"[{nv + 1}:a]aresample=48000,volume=0.22[m]")
flt.append("[voice]asplit[vo][sc]")
flt.append("[m][sc]sidechaincompress=threshold=0.03:ratio=6:attack=20:release=400[md]")
flt.append("[vo][md]amix=inputs=2:normalize=0,alimiter=limit=0.95[a]")
ass = os.path.join(WORK, "captions.ass")
log("caption lines:", write_ass(ass))
fontsdir = os.path.join(ENG, "fonts")
flt.append("[0:v]subtitles=filename=%s:fontsdir=%s[vout]" % (ass.replace(":", "\\:"), fontsdir.replace(":", "\\:")))
sh([FF, "-y", "-loglevel", "error", "-i", silent] + ins + ["-i", mwav, "-filter_complex", ";".join(flt),
    "-map", "[vout]", "-map", "[a]", "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-ac", "2", "-t", f"{T:.2f}", "-movflags", "+faststart", spec["out"]])
sh([FF, "-y", "-loglevel", "error", "-i", spec["out"], "-vf", "scale=854:480", "-c:v", "libx264", "-preset", "veryfast", "-crf", "30", "-c:a", "aac", "-b:a", "96k", spec["preview"]])
thumbnail(spec["thumb"])
os.remove(silent)
log("long video done")
