"""Suspense music for Empire Maps, made by code (no copyright issues).

A dark drone and a ticking pulse that keep tension under the narration, a staccato string ostinato that
grows louder as the empire grows, a riser + hit on every year change, war drums from the middle,
and a big impact on the last line.
Usage: python music.py spec.json out.wav
"""
import json
import random
import sys
import wave

import numpy as np

spec = json.load(open(sys.argv[1]))
OUT = sys.argv[2]
SR = 48000
TOTAL = float(spec["total"])
starts = [float(s) for s in spec["line_starts"]]
VEND = float(spec.get("voice_end", TOTAL - 2))
rng = random.Random(spec.get("seed", 5))
nrng = np.random.default_rng(spec.get("seed", 5))
N = int(TOTAL * SR) + SR
L = np.zeros(N, np.float32)
R = np.zeros(N, np.float32)


def put(sig, at, gain=1.0, pan=0.0):
    i = int(at * SR)
    if i >= N or i < 0:
        return
    sig = sig[: N - i] * gain
    L[i:i + len(sig)] += sig * (1 - max(0, pan))
    R[i:i + len(sig)] += sig * (1 + min(0, pan))


def lp(x, hi):
    X = np.fft.rfft(x)
    f = np.fft.rfftfreq(len(x), 1 / SR)
    return np.fft.irfft(X / (1 + (f / hi) ** 4), len(x)).astype(np.float32)


def bp(x, lo, hi):
    X = np.fft.rfft(x)
    f = np.fft.rfftfreq(len(x), 1 / SR)
    m = 1 / (1 + (lo / np.maximum(f, 1)) ** 4) / (1 + (f / hi) ** 4)
    return np.fft.irfft(X * m, len(x)).astype(np.float32)


def noise(n):
    return nrng.uniform(-1, 1, n).astype(np.float32)


def saw(f, t):
    return (2 * ((f * t) % 1.0) - 1).astype(np.float32)


# ---------- sounds ----------
def boom(dur=3.0, big=1.0):
    n = int(dur * SR)
    t = np.arange(n) / SR
    f = 30 + 45 * np.exp(-t * 7)
    s = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 1.5)
    s += 0.5 * lp(noise(n), 700) * np.exp(-t * 5)
    return (s * big).astype(np.float32)


def braam(dur=2.8, root=73.42):
    n = int(dur * SR)
    t = np.arange(n) / SR
    s = np.zeros(n, np.float32)
    bright = np.minimum(1, t / 0.5) * np.exp(-t * 0.8)
    for f in (root / 2, root, root * 1.4983):
        s += saw(f, t) * 0.5 + saw(f * 1.004, t) * 0.5
    s = lp(s, 900) * bright
    return (s * np.exp(-t * 0.9) * 0.35).astype(np.float32)


def riser(dur=1.0):
    n = int(dur * SR)
    t = np.arange(n) / SR
    e = (t / dur) ** 2.5
    ph = 2 * np.pi * np.cumsum(300 + 1400 * (t / dur) ** 2) / SR
    x = bp(noise(n), 1200, 7000) * 0.5 + 0.25 * np.sin(ph)
    return (x * e * 0.5).astype(np.float32)


def hit(dur=1.6):
    n = int(dur * SR)
    t = np.arange(n) / SR
    f = 45 + 80 * np.exp(-t * 20)
    s = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 4)
    s += 0.35 * bp(noise(n), 2000, 9000) * np.exp(-t * 9)  # metallic swish
    return (s * 0.9).astype(np.float32)


def tick(dur=0.06, f=2400):
    n = int(dur * SR)
    t = np.arange(n) / SR
    return (np.sin(2 * np.pi * f * t) * np.exp(-t * 90) * 0.25 + bp(noise(n), 3000, 9000) * np.exp(-t * 120) * 0.2).astype(np.float32)


def heart(dur=0.5):
    n = int(dur * SR)
    t = np.arange(n) / SR
    f = 50 + 30 * np.exp(-t * 25)
    return (np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 11) * 0.9).astype(np.float32)


def taiko(dur=1.4):
    n = int(dur * SR)
    t = np.arange(n) / SR
    f = 60 + 60 * np.exp(-t * 16)
    s = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 3.5) + 0.3 * lp(noise(n), 1500) * np.exp(-t * 25)
    return (s * 0.8).astype(np.float32)


def string_note(f, dur=0.22):
    n = int(dur * SR)
    t = np.arange(n) / SR
    s = saw(f, t) * 0.6 + saw(f * 1.006, t) * 0.4
    s = lp(s, 2600) * np.minimum(1, t / 0.008) * np.exp(-t * 9)
    return (s * 0.22).astype(np.float32)


# ---------- harmony (D minor, darker variations) ----------
key = rng.choice([1.0, 0.9439, 1.0595])
D = 73.42 * key
prog = rng.choice([[0, -2, -4, -5], [0, 1, -4, -2], [0, -4, -2, -5]])  # semitone moves of the bass
BPM = rng.choice([96, 100, 104])
BEAT = 60 / BPM
BAR = BEAT * 4
first = starts[0] if starts else 1.6
last = starts[-1] if starts else TOTAL - 4
mid = starts[len(starts) // 2] if starts else TOTAL / 2

# 1) drone: low root + fifth, slow swell, always under everything
n = int(TOTAL * SR)
t = np.arange(n) / SR
drone = np.zeros(n, np.float32)
for f, g in ((D / 2, 1.0), (D, 0.6), (D * 1.4983, 0.35)):
    drone += g * (np.sin(2 * np.pi * f * t) + 0.3 * np.sin(2 * np.pi * f * 2.003 * t))
drone *= (0.55 + 0.45 * np.sin(2 * np.pi * t / 7.0) ** 2) * np.minimum(1, t / 1.5)
put(lp(drone, 500) * 0.10, 0.0)

# 2) the opening hit
put(braam(3.0, D), 0.0, 1.0)
put(boom(3.4, 1.1), 0.0, 0.9)

# 3) ticking clock + heartbeat from the first line (tension), ostinato strings grow with the story
tt = first
k = 0
while tt < VEND:
    grow = min(1.0, (tt - first) / max(1.0, last - first))
    put(tick(f=2400 if k % 4 == 0 else 1800), tt, 0.5 + 0.3 * grow, pan=0.25 if k % 2 else -0.25)
    if k % 4 == 0:
        put(heart(), tt, 0.55)
        put(heart(), tt + BEAT * 0.45, 0.35)
    # staccato strings: 8th notes on the chord of this bar
    bar = int((tt - first) / BAR)
    root = D * 2 ** (prog[bar % 4] / 12)
    notes = [root * 2, root * 2 * 1.1892, root * 2 * 1.4983, root * 4]
    for h in range(2):
        put(string_note(notes[(k * 2 + h) % 4]), tt + h * BEAT / 2, 0.35 + 0.65 * grow, pan=rng.uniform(-0.5, 0.5))
    tt += BEAT
    k += 1

# 4) every year change: riser into it, then a hit
for s in starts[1:]:
    put(riser(0.9), s - 0.9, 0.55)
    put(hit(), s, 0.75)

# 5) war drums from the middle line to the last line
tt = mid
while tt < last - 0.2:
    put(taiko(), tt, 0.6)
    put(taiko(1.0), tt + BEAT * 1.5, 0.35, pan=0.3)
    put(taiko(1.0), tt + BEAT * 2.5, 0.3, pan=-0.3)
    tt += BAR / 2

# 6) the last line: big impact and a held dark chord
put(riser(1.4), max(0.5, last - 1.4), 0.8)
put(boom(4.0, 1.3), last, 1.0)
put(braam(4.0, D), last, 0.9)
tail = TOTAL - last
nt = int(max(1.0, tail) * SR)
tt_ = np.arange(nt) / SR
chord = sum(np.sin(2 * np.pi * f * tt_) for f in (D, D * 1.1892, D * 1.4983, D * 2))
put((lp(chord.astype(np.float32), 1200) * np.minimum(1, tt_ / 0.8) * 0.06).astype(np.float32), last)

# ---------- room + finish ----------
ir_n = int(2.2 * SR)
ir = nrng.uniform(-1, 1, ir_n).astype(np.float32) * np.exp(-np.arange(ir_n) / SR * 2.8)
ir[0] = 0
ir /= np.abs(ir).sum() / 6


def conv(x):
    size = 1 << (len(x) + ir_n - 1).bit_length()
    return np.fft.irfft(np.fft.rfft(x, size) * np.fft.rfft(ir, size), size)[: len(x)].astype(np.float32)


L2 = L + 0.3 * conv(L)
R2 = R + 0.3 * conv(R)
fade = np.ones(N, np.float32)
fs = int((TOTAL - 1.2) * SR)
fade[fs:] = np.linspace(1, 0, N - fs)
L2 *= fade
R2 *= fade
peak = max(np.abs(L2).max(), np.abs(R2).max(), 1e-6)
st = np.stack([L2, R2], 1) / peak
st = np.tanh(3.2 * st) / np.tanh(3.2) * 0.9  # soft limiter: big hits stay big, the tense bed comes up
st = st[: int(TOTAL * SR)]
with wave.open(OUT, "wb") as w:
    w.setnchannels(2)
    w.setsampwidth(2)
    w.setframerate(SR)
    w.writeframes((st * 32767).astype(np.int16).tobytes())
