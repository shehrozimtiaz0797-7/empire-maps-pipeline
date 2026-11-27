# Changes

## 2026-11-28 (06:10 MY) Repeat Shorts must look new
- The 27 Nov 22:50 Rome rise Short got only 3 views in 15 h (Assyria, a new empire, got 277 in 3 h). Its on-screen hook
  "How Rome Conquered the Ancient World" was the same as the 14 Nov Rome Short (the prompt even used it as an example),
  so YouTube likely treated it as a re-upload and did not push it.
- Prompt: lists all earlier titles of the same empire and asks for a different hook line, rulers, battles and turning points;
  examples no longer include Rome. Validation rejects a title or hook_text equal to an earlier one of that empire.

## 2026-11-27 (21:45 MY) Shorts back to the week-1 style (owner: "mujh bs wesa he chaye jesy 1000+ view har video ma aty thy jo karna karo")
- Week 1 (14-20 Nov) every Short got 800-2,500 views: rise stories, famous empires, 45-66 s, up to 7 maps, 10-18 words a line, 1.6 s title first.
- Undone: the 30-40 s limit (MAX_MAPS 5 -> 7, words per line back to 10-18, total (n+1)*13..16, MAX_VOICE 36 -> 75 s) and the 0.5 s intro / short tail (back to 1.6 s / 2.2 s, outro fade as before).
- Kept: rise-only picker with famous every other Short (16:30 change). Manual topic (e.g. "roman") now picks that exact empire's rise.
- Tested on branch week1-test with upload off: 7 maps, voice 61 s, video built fine.

## 2026-11-27 (16:30 MY) Growth fix: only "rise" Shorts again
- Owner: "channel down hota jarah hai mujh grow chaye jo error ya galati hai isko fix karo".
- Found the cause in 44 Shorts of data: every RISE Short (empire growing on the map) got 795-2,503 views, even little-known ones
  (Khmer 1,157, Songhai 1,043, Srivijaya 892). FULL (rise+fall) Shorts mostly got 100-900 (Spanish 272, Qing 344, Persia 6).
  From 20 Nov the picker had used up the rise stories and the new 24 Nov empires mostly had no rise (peak = first map), so
  almost every Short became a "full" one -> daily views fell from ~4,800 to ~1,800.
- Also a bug: the "every other Short famous" rule needed a famous empire rested 7 days; none was, so new empires ran back to back.
- New pickTopic: only rise stories (3+ maps before the peak); every other Short famous (Rome, Ottoman, Mongol, British, Spanish,
  Japan, Qing, Russia, Mughal, USA, Habsburg, Germany, Poland ...); an empire rests REST_DAYS=6 days; a repeat rise uses the
  last maps before the peak so it looks different; Ottoman and Byzantine-Ottoman count as one empire. Simulated 30 days on the real history: 29 different empires, none closer than 6 days.

## 2026-11-26 — one 30+ minute video (owner asked, one time only)
- Owner: "ek long video banao 30+ minutes ki ... bs ek he video chaye roz roz ni chaye and abi upload kar do".
- New `long/make-mega.js` (copy of make-long.js): script written chapter by chapter from `long/mega-topic.json` (12 chapters x ~400 words, each fact-checked), voice in 9 chunks (main Gemini key, backup key on 429), uploads PUBLIC at once. No slot guard, no schedule.
- Topic: Rome, the complete 2,000-year history (Republic -> Empire -> Byzantium -> 1453), 19 map years, borders names checked per year in historical-basemaps.
- New workflow `mega-video.yml`: workflow_dispatch only (no cron), timeout 330 min. The daily long-video.yml stays DISABLED.

## 2026-11-25 (22:45 MY) Growth: famous empires back, proven title format
- Owner (25 Nov): "Empire Maps ko grow karna ... khuch b change karna hu tumay full permission hai".
- Data: week-1 Shorts (famous empires, "How the X Grew/Conquered..." titles) got 1,000-2,500 views each; the new
  little-known empires with question titles got 6-252 in their first day.
- pickTopic: every other Short is a famous empire again (FAMOUS list, after REST_DAYS = 7), the others are new empires.
- Title prompt: back to the channel's best format "How [the] <Empire> <verb phrase>"; no "Rise and Fall" / "Why".

## 2026-11-25 (02:05 MY) Shorts start fast, short tail (Shorts algorithm: swipe decision in the first 1-2 s)
- Voice now starts at 0.5 s (was 1.6 s of title + music only); the end card comes sooner and the tail is 1.4 s
  (was 2.2 s) so the Short loops back quickly (rewatches count). INTRO_S / TAIL_S env vars. Tested on branch
  fast-start without upload (Alexander, 27.9 s; caption visible at 0.8 s).

## 2026-11-24 (23:15 MY) Gemini overload retry
- The 22:50 MY Short failed: Gemini answered HTTP 503 ("high demand") on all text models for ~2 minutes. Re-ran it by
  hand. writeScript now retries busy errors (5xx/429) up to 6 times with waits of 30-150 s (~12 min in all).

## 2026-11-24 (16:20 MY) Growth: no more repeat empires, 19 new empires, varied titles
- Owner: "karo jo karna hai mujh grow chaye". Data: a second Short about the same empire got 3-7x fewer views
  (Spanish 1,412 -> 189, British 1,483 -> 356, Russia 1,231 -> 444, USA 1,184 -> 454), and all 26 old empires had
  already been made, so the pipeline was repeating them.
- topics.json: 19 new empires first (persia, alexander, egypt_ancient, inca, caliphates, timurid, carthage, maratha,
  chola, assyria, mamluk, vijayanagara, hittite, venice, dutch, axum, golden_horde, ghana_empire, khazar); every name
  checked in every listed year of historical-basemaps.
- src/script.js pickTopic: an empire never made comes first; a made empire waits REST_DAYS (14) and then the one made
  longest ago comes first; angles not made yet are preferred.
- Title prompt: shows the last 12 titles and asks for a different format (question / number / surprise), avoiding
  "Rise and Fall" / "How the" when recent titles used them.

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
