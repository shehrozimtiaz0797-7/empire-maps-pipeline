"""Finds when every word is really spoken in each voice chunk (faster-whisper), so the captions and the
map changes follow the voice exactly.
Usage: python long/align.py in.json out.json
in:  {"chunks": [{"file": "voice1.wav", "paras": ["text", ...]}, ...]}
out: {"chunks": [{"words": [[word, start, end], ...], "para_start": [s, ...], "matched": n, "spoken": n}]}
Times are seconds inside each chunk. Words come from the recogniser (so they match the voice); where a
spoken word matches the script, the script's spelling and punctuation are used."""
import json
import os
import re
import sys
from difflib import SequenceMatcher

from faster_whisper import WhisperModel


def norm(w):
    return re.sub(r"[^a-z0-9]", "", w.lower())


spec = json.load(open(sys.argv[1]))
model = WhisperModel(os.environ.get("WHISPER_MODEL", "base.en"), device="cpu", compute_type="int8")
out = []
for ch in spec["chunks"]:
    segs, _ = model.transcribe(ch["file"], language="en", word_timestamps=True, vad_filter=False, beam_size=5)
    heard = []
    for sg in segs:
        for w in sg.words or []:
            txt = w.word.strip()
            if txt:
                heard.append([txt, float(w.start), float(w.end)])
    script, owner = [], []
    for pi, p in enumerate(ch["paras"]):
        for w in p.split():
            script.append(w)
            owner.append(pi)
    a = [norm(w) for w in script]
    b = [norm(h[0]) for h in heard]
    s2h = {}
    for blk in SequenceMatcher(None, a, b, autojunk=False).get_matching_blocks():
        for k in range(blk.size):
            s2h[blk.a + k] = blk.b + k
    h2s = {v: k for k, v in s2h.items()}
    matched = sorted(s2h.values())
    # words to show: from the first to the last matched spoken word (drops anything said before or after the script)
    words = []
    if matched:
        for hi in range(matched[0], matched[-1] + 1):
            w, s0, s1 = heard[hi]
            words.append([script[h2s[hi]] if hi in h2s else w, s0, s1])
    # paragraph starts: the first matched word of each paragraph
    starts = []
    for pi in range(len(ch["paras"])):
        idx = [s2h[k] for k in range(len(script)) if owner[k] == pi and k in s2h]
        starts.append(heard[min(idx)][1] if idx else None)
    # fill paragraphs that matched nothing: between their neighbours
    for pi in range(len(starts)):
        if starts[pi] is None:
            prev = next((starts[j] for j in range(pi - 1, -1, -1) if starts[j] is not None), 0.0)
            nxt = next((starts[j] for j in range(pi + 1, len(starts)) if starts[j] is not None), None)
            starts[pi] = prev if nxt is None else (prev + nxt) / 2
    for pi in range(1, len(starts)):
        starts[pi] = max(starts[pi], starts[pi - 1] + 0.5)
    print(f"align: {os.path.basename(ch['file'])}: {len(s2h)}/{len(script)} script words found in {len(heard)} spoken words", flush=True)
    out.append({"words": words, "para_start": starts, "matched": len(s2h), "script": len(script), "spoken": len(heard)})
json.dump({"chunks": out}, open(sys.argv[2], "w"))
