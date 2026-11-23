# Changes

## 2026-11-24 (04:40 MY) Long videos stopped by the owner
- Owner: "empire long video khatam kar do band kar". long-video.yml is disabled (GitHub Actions -> Enable workflow to
  start again) and the run that was in progress was cancelled. Shorts are not changed.
- At the owner's confirmed request the 2 long videos were deleted from YouTube: j4PrtHGrVzE (Roman, 2 views) and
  Ki8igBSE6ho (Ottoman, 0 views).

## 2026-11-23 (16:20 MY) Shorts: hard 40 s cap
- The French Short (56 words) still came out 47 s because the voice read slowly. make-video.js now speeds the voice
  up a little (max x1.15) when it is longer than MAX_VOICE = 36 s, so the Short stays under ~40 s.

## 2026-11-23 (10:05 MY) Fixes from the daily check
- Long video: GitHub's 16:35 MY cron ran 8 hours late (00:35 MY) and made the next video early (Ottoman, public 24 Nov
  00:30 MY = 2026-11-23T16:30Z). To stop a second long video for the same slot (late cron + backup starter),
  make-long.js now does nothing if long-history.json already has a video for the next publish slot (--force overrides).
- Shorts: a --no-upload test run was written to history.json (Holy Roman, 22 Nov 21:44 MY, no videoId), which made the
  pipeline think that topic was done. Removed that entry; make-video.js no longer records --no-upload runs.

## 2026-11-23 (01:40 MY) New topics from competitor research
- Owner asked me to pick ("jo dil hai karna"). Research of 16 history-map channels: "Evolution of India" (43x the
  channel's median), "Evolution of China" (18x) and the French Empire (29x) were top outliers. Added topics `india`
  (Maurya -> Gupta -> Delhi Sultanate -> Mughal -> British Raj -> India) and `china` (Han -> Sui -> Tang -> Song ->
  Ming -> Qing -> China), names checked in every year of historical-basemaps, and moved them plus `french` to the front
  of topics.json. No code change.

## 2026-11-22 (21:20 MY) Shorts 30-40 seconds
- Owner's choice: Shorts were 45-66 s; the shorter ones (27-46 s) got more views. Now at most 5 map years per Short
  (MAX_MAPS in src/script.js) and 7-10 words per line (max 11 per line on average, also in the fact-check), so a Short is about 30-40 s.
  First test (Holy Roman, 5 maps, 76 words) came out 44 s, so the limit was tightened to max 66 words for 5 maps. Rollback: MAX_MAPS = 7 and the old
  word limits (10-18 per line, 13-16 x lines in total, check 9-19).

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
- Long video approved by the owner (22 Nov 04:52 MY): daily schedule on (16:35 MY), goes public 00:30 MY.
  Order of empires in long/queue.json (Rome first: best Shorts), then the rest of topics.json.
