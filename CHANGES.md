# Changes

## 2026-11-15
- First version: animated history-map Shorts (borders from historical-basemaps), Gemini narration + fact-check, documentary voice, epic music, 2 uploads a day (2:50 and 8:50 Malaysia time).

## 2026-11-15 (01:10 MY)
- New suspense music: dark drone, ticking clock + heartbeat, staccato strings that grow with the story, a riser + hit on every year change, war drums from the middle, big impact on the last line, soft limiter so the tension bed is audible.
- 4 videos a day (owner request): 2:50 am, 8:50 am, 12:50 pm, 3:50 pm Malaysia time.
- Every run saves its newest video, script and timing to the `qa` branch so it can be checked.
- Caption timing: line pauses are found on the dry voice (no echo) and each boundary snaps to the nearest real pause; a short '...' pause is asked for between lines. (Before: one missed pause made all timings 'estimated'.)
- Year counter never shows year 0.
- Checked the Mongol test video: line pauses 3/3 found and captions start exactly on each spoken line. Music was only 1-3 dB under the voice near the end, so: music 0.8x, stronger ducking (threshold 0.03, ratio 6), softer last-line impact. Voice is now 6-17 dB above the music.
- Slot 3:50 pm (US night) moved to 10:50 pm Malaysia (UK afternoon, India prime time, US morning). Slots now 2:50 am, 8:50 am, 12:50 pm, 10:50 pm.

## 2026-11-15 (16:30 MY)
- First day: 4 videos, 707-1,549 views each (Rome 1,549 with 45 likes), but only 1 subscriber. Added a red 'SUBSCRIBE FOR THE NEXT EMPIRE' button from the closing line to the end.
- Subscribe button REMOVED again the same day: the owner's rule is that a channel that is doing well must not be changed. Only bug fixes for Empire Maps from now on.

## 2026-11-22
- New: daily long video (5-6 min, 16:9), owner's request ("4 short and 1 long"). Separate files only:
  long/make-long.js, long/longtools.py, .github/workflows/long-video.yml. The Shorts code, workflow and times are unchanged.
  Map shots of the empire per paragraph (land won since the last map glows gold, lost land fades), chapter cards,
  word-by-word captions, calm music, map thumbnail. Upload is private with a scheduled publish time (16:30 UTC).
  Test phase: started by hand; the daily schedule is added after the owner approves the test video.
- Backup Gemini key (owner added GEMINI_API_KEY_2 on 22 Nov, another project): src/gemini.js tries the main key first and
  only on HTTP 429 (free daily limit used up) uses the backup. Both workflows pass the new secret. Nothing else in the Shorts changed.
- Long video captions: word times now come from faster-whisper (long/align.py). The first test had no recogniser
  (missing 'requests', then a PyAV clash), so captions were estimated and drifted. Map changes follow the real paragraph starts too.
- Note: the long-video tests on 22 Nov night used up the shared Gemini TTS free limit (10/day), so the 08:50 and 12:50 Shorts
  may fail today; they are made up after the 16:00 reset.
