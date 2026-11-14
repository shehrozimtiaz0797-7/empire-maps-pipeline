# Empire Maps

Animated history-map YouTube Shorts, made and uploaded automatically every day.

- Script: Gemini writes one narration line per map year, then a second Gemini call fact-checks it.
- Map: borders from [historical-basemaps](https://github.com/aourednik/historical-basemaps) by André Ourednik (GPL-3.0), drawn with Pillow (`src/render.py`).
- Voice: Gemini TTS. Music: made by code (`src/music.py`).
- Upload: YouTube Data API (`src/youtube.js`).

Setup steps: see `START-HERE.txt`. Empires and years: `topics.json`.
