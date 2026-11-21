'use strict';
// Empire Maps long video (5-6 min, 16:9): the whole story of one empire on real historical borders.
// Script + fact-check (Gemini) -> voice in a few chunks (Gemini TTS) -> map shots per paragraph (longtools.py)
// -> upload as private with a scheduled publish time + thumbnail. The Shorts code is not touched.
// Usage: node long/make-long.js [--topic id] [--no-upload]
const fs = require('fs');
const path = require('path');
const { askJSON, speak } = require('../src/gemini');
const { ROOT, env, log, run, duration, fetchRetry, FFMPEG, PYTHON } = require('../src/lib');

const args = process.argv.slice(2);
const opt = n => { const i = args.indexOf(n); return i >= 0 ? args[i + 1] : ''; };
const NO_UPLOAD = args.includes('--no-upload');
const TOPICS = JSON.parse(fs.readFileSync(path.join(ROOT, 'topics.json'), 'utf8'));
const HIST = path.join(ROOT, 'long-history.json');
const readHist = () => { try { return JSON.parse(fs.readFileSync(HIST, 'utf8')); } catch (_) { return []; } };
const yearText = y => (y < 0 ? `${-y} BC` : y < 1000 ? `${y} AD` : String(y));
const CHANNEL = 'https://youtube.com/@empiremaps1857?sub_confirmation=1';

// Extra map years for the long story (e.g. the fall of Rome needs 400 and 500 AD, where the data names the
// empire differently). Only the long video reads this file; the Shorts keep using topics.json as it is.
const EXTRA = (() => { try { return JSON.parse(fs.readFileSync(path.join(__dirname, 'extra-years.json'), 'utf8')); } catch (_) { return {}; } })();

function withExtra(t) {
  const x = EXTRA[t.id];
  if (!x) return t;
  return { ...t, years: [...new Set([...t.years, ...(x.years || [])])].sort((a, b) => a - b), names: [...new Set([...t.names, ...(x.names || [])])], labels: { ...(t.labels || {}), ...(x.labels || {}) } };
}

function pickTopic() {
  const want = opt('--topic');
  if (want) { const t = TOPICS.find(x => x.id === want); if (t) return withExtra(t); }
  const done = readHist().map(h => h.topic);
  // long/queue.json: preferred order (best Shorts first); then the rest of topics.json; then round again
  let queue = [];
  try { queue = JSON.parse(fs.readFileSync(path.join(__dirname, 'queue.json'), 'utf8')); } catch (_) {}
  const ordered = [...queue.map(id => TOPICS.find(t => t.id === id)).filter(Boolean), ...TOPICS.filter(t => !queue.includes(t.id))];
  return withExtra(ordered.find(t => !done.includes(t.id)) || ordered[done.length % ordered.length]);
}

function scriptPrompt(t) {
  return `You write long YouTube videos for "Empire Maps", a history channel that shows empires growing and shrinking on animated maps.
Subject: the full story of ${t.name}: how it began, how it grew, its peak (around ${yearText(t.peak)}), how it declined and ended.
Map snapshots available (the map on screen shows the real borders in these years): ${t.years.map(yearText).join(', ')}.

Write a gripping, accurate narration of about 6 minutes (720 to 820 words) that tells it as a STORY: the rulers, the key wars and
turning points, why it grew, why it fell. Open with a strong one-sentence hook about the most surprising fact, then start at the beginning.
End with why it still matters today and one question for the comments ("Which empire should we map next?").
Plain spoken English, short sentences, no lists, no headings inside the text, no emoji.

Return ONLY JSON:
{"title": "YouTube title under 70 characters, curiosity + searchable (e.g. 'How the X Empire Rose and Fell'), no emoji",
 "thumb_text": "2 to 4 BIG words for the thumbnail",
 "description": "2 short paragraphs about the video, then a blank line, then 5 hashtags",
 "tags": [12 to 15 search tags],
 "chapters": [5 or 6 objects: {"heading": "short chapter name (2 to 5 words)", "paragraphs": [3 objects: {"text": "45 to 60 words of narration", "year": one of the snapshot years above that the map should show while this is said (number, negative for BC)}]}]}

The "year" values must go forward in time through the video (never back), start with the earliest snapshot and use as many different snapshots as possible.
Facts: only well-known, true history. No invented numbers or quotes. Neutral and respectful about every people and religion; no modern politics.`;
}

async function writeScript(t) {
  let last;
  for (let a = 1; a <= 3; a++) {
    try {
      const s = await askJSON(scriptPrompt(t), { temperature: 0.8 });
      const ch = (s.chapters || []).filter(c => c && Array.isArray(c.paragraphs) && c.paragraphs.length);
      const paras = ch.flatMap(c => c.paragraphs);
      const words = paras.map(p => String(p.text || '')).join(' ').split(/\s+/).length;
      if (ch.length < 4 || words < 600) throw new Error(`too short (${ch.length} chapters, ${words} words)`);
      log(`Script: ${ch.length} chapters, ${paras.length} paragraphs, ${words} words`);
      // years: only snapshot years, never going back in time
      let y = t.years[0];
      for (const p of paras) {
        let want = Number(p.year);
        if (!t.years.includes(want)) want = t.years.reduce((b, v) => (Math.abs(v - want) < Math.abs(b - want) ? v : b), t.years[0]);
        y = Math.max(y, want);
        p.year = y;
      }
      s.chapters = ch;
      try {
        const c = await askJSON(`You are a careful history fact-checker. Here are the narration paragraphs of a video about ${t.name}, as a JSON list of strings:
${JSON.stringify(paras.map(p => p.text))}
Fix any wrong fact, wrong date, wrong name or exaggeration presented as fact. Keep the same number of items, the same style and about the same length. Keep correct text exactly as it is.
Return ONLY JSON: {"texts": [...], "changed": number of items you changed}`, { temperature: 0.2 });
        if (Array.isArray(c.texts) && c.texts.length === paras.length) {
          paras.forEach((p, i) => { p.text = String(c.texts[i]); });
          log(`Fact-check changed ${c.changed || 0} paragraph(s)`);
        }
      } catch (e) { log('Fact-check skipped: ' + e.message); }
      return s;
    } catch (e) { last = e; log(`Script attempt ${a} not usable: ${e.message}`); }
  }
  throw last;
}

function wav(pcm, file) {
  const h = Buffer.alloc(44);
  h.write('RIFF', 0); h.writeUInt32LE(36 + pcm.length, 4); h.write('WAVE', 8); h.write('fmt ', 12);
  h.writeUInt32LE(16, 16); h.writeUInt16LE(1, 20); h.writeUInt16LE(1, 22); h.writeUInt32LE(24000, 24);
  h.writeUInt32LE(48000, 28); h.writeUInt16LE(2, 32); h.writeUInt16LE(16, 34); h.write('data', 36); h.writeUInt32LE(pcm.length, 40);
  fs.writeFileSync(file, Buffer.concat([h, pcm]));
}

async function makeVoice(s, dir) {
  const voice = env('LONG_VOICE', 'Charon');
  const paras = s.chapters.flatMap((c, ci) => c.paragraphs.map((p, pi) => ({ ...p, ci, first: pi === 0 })));
  const N = Number(env('LONG_VOICE_CHUNKS', '3'));
  const per = Math.ceil(paras.length / N);
  const style = 'Read this like a calm, gripping history documentary narrator, deep warm voice, steady pace, small pauses between paragraphs:\n';
  const pieces = [];
  for (let k = 0; k * per < paras.length; k++) {
    const group = paras.slice(k * per, (k + 1) * per);
    const text = style + group.map(p => p.text).join('\n\n');
    let pcm;
    for (let a = 1; a <= 3 && !pcm; a++) {
      try { pcm = await speak(text, voice); } catch (e) { log(`Voice chunk ${k + 1} try ${a}: ${e.message.slice(0, 200)}`); if (a === 3) throw e; await new Promise(r => setTimeout(r, 20000)); }
    }
    const f = path.join(dir, `voice${k + 1}.wav`); wav(pcm, f);
    const d = await duration(f);
    log(`Voice chunk ${k + 1}: ${d.toFixed(1)}s`);
    const chars = group.map(p => p.text.length); const tot = chars.reduce((a, b) => a + b, 0);
    group.forEach((p, i) => { p.dur = d * chars[i] / tot; });
    pieces.push({ file: f, dur: d, group });
  }
  return { paras, pieces };
}

// Real word times from the voice (faster-whisper): paragraph starts for the map changes, words for the captions.
async function align(pieces, dir) {
  const inp = path.join(dir, 'align-in.json'), out = path.join(dir, 'align.json');
  fs.writeFileSync(inp, JSON.stringify({ chunks: pieces.map(pc => ({ file: pc.file, paras: pc.group.map(p => p.text) })) }));
  const o = await run(PYTHON(), [path.join(__dirname, 'align.py'), inp, out]);
  if (o.trim()) log(o.trim());
  return JSON.parse(fs.readFileSync(out, 'utf8')).chunks;
}

function nextPublish() {
  // publish at PUBLISH_UTC (HH:MM) — the first one at least 45 minutes from now
  const [hh, mm] = env('PUBLISH_UTC', '16:30').split(':').map(Number);
  const t = new Date(); t.setUTCHours(hh, mm || 0, 0, 0);
  while (t.getTime() < Date.now() + 45 * 60000) t.setUTCDate(t.getUTCDate() + 1);
  return t.toISOString().replace(/\.\d{3}Z$/, 'Z');
}

async function uploadLong(file, meta) {
  const { accessToken } = require('../src/youtube');
  const token = await accessToken();
  const size = fs.statSync(file).size;
  const publishAt = nextPublish();
  const body = {
    snippet: { title: meta.title, description: meta.description, tags: meta.tags.slice(0, 15), categoryId: env('YT_CATEGORY', '27'), defaultLanguage: 'en', defaultAudioLanguage: 'en' },
    status: { privacyStatus: 'private', publishAt, selfDeclaredMadeForKids: false, containsSyntheticMedia: false },
  };
  const start = await fetchRetry('https://www.googleapis.com/upload/youtube/v3/videos?uploadType=resumable&part=snippet,status', {
    method: 'POST',
    headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json; charset=UTF-8', 'X-Upload-Content-Type': 'video/mp4', 'X-Upload-Content-Length': String(size) },
    body: JSON.stringify(body),
  });
  if (!start.ok) throw new Error(`YouTube upload start failed HTTP ${start.status}: ${(await start.text()).slice(0, 400)}`);
  const where = start.headers.get('location');
  if (!where) throw new Error('YouTube did not give an upload address');
  const put = await fetch(where, { method: 'PUT', headers: { 'Content-Type': 'video/mp4', 'Content-Length': String(size) }, body: fs.readFileSync(file) });
  const text = await put.text();
  if (!put.ok) throw new Error(`YouTube upload failed HTTP ${put.status}: ${text.slice(0, 400)}`);
  const data = JSON.parse(text);
  log(`Uploaded: https://youtube.com/watch?v=${data.id} (private, goes public at ${publishAt})`);
  return { id: data.id, publishAt, token };
}

async function main() {
  const t = pickTopic();
  const stamp = new Date().toISOString().slice(0, 16).replace(/[:T]/g, '-');
  const dir = path.join(ROOT, 'output', `long-${stamp}-${t.id}`);
  fs.mkdirSync(dir, { recursive: true });
  log(`LONG video: ${t.name}`);
  const s = await writeScript(t);
  fs.writeFileSync(path.join(dir, 'script.json'), JSON.stringify(s, null, 2));
  const { pieces } = await makeVoice(s, dir);
  const al = await align(pieces, dir);
  al.forEach((a, i) => {
    const r = a.matched / Math.max(1, a.script);
    if (r < 0.75) throw new Error(`voice chunk ${i + 1} does not match the script well enough (${Math.round(r * 100)}% of words found)`);
  });

  // timeline: 4 s title (music only), then the narration. Each chapter opens with a short chapter card;
  // each paragraph shows the map of its year (land won since the last map glows gold); long paragraphs get two shots.
  const TITLE = 4;
  const timeline = [{ kind: 'title', dur: TITLE }];
  const voiceAt = [];
  let tcur = TITLE, prevYear = null, k = 0;
  const zooms = ['wide', 'mid', 'close'];
  const words = [];
  pieces.forEach((piece, pi) => {
    const a = al[pi];
    // cut anything spoken before the first or after the last script word (e.g. the reading instruction)
    const first = a.words.length ? a.words[0][1] : 0, lastEnd = a.words.length ? a.words[a.words.length - 1][2] : piece.dur;
    const skip = first > 1.2 ? first - 0.3 : 0;
    const keep = Math.min(piece.dur, lastEnd + 0.8) - skip;
    if (skip || keep < piece.dur - 0.01) log(`Voice chunk ${pi + 1}: using ${skip.toFixed(1)}s to ${(skip + keep).toFixed(1)}s of ${piece.dur.toFixed(1)}s`);
    a.words = a.words.map(w => [w[0], w[1] - skip, w[2] - skip]);
    a.para_start = a.para_start.map(x => Math.max(0, x - skip));
    piece.dur = keep;
    voiceAt.push({ file: piece.file, start: tcur, skip, dur: piece.dur, text: piece.group.map(p => p.text).join(' ') });
    for (const w of a.words) words.push([w[0], tcur + w[1], tcur + w[2]]);
    // each paragraph lasts from its first spoken word to the next paragraph's first word
    piece.group.forEach((p, gi) => {
      const st = gi === 0 ? 0 : a.para_start[gi];
      const en = gi + 1 < piece.group.length ? a.para_start[gi + 1] : piece.dur;
      p.dur = Math.max(0.8, en - st);
    });
    for (const p of piece.group) {
      let d = p.dur;
      if (p.first) {
        const cd = Math.min(3.5, d * 0.35);
        timeline.push({ kind: 'chapter', dur: cd, heading: s.chapters[p.ci].heading, chapter: p.ci + 1, year: p.year });
        d -= cd;
      }
      const parts = d > 11 ? 2 : 1;
      for (let h = 0; h < parts; h++) {
        timeline.push({ kind: 'map', dur: d / parts, year: p.year, prev: prevYear === null ? null : prevYear, zoom: zooms[k++ % 3] });
      }
      prevYear = p.year;
    }
    tcur += piece.dur;
  });
  timeline.push({ kind: 'outro', dur: 5 });
  const total = tcur + 5;
  const spec = {
    topic: { names: t.names, years: t.years, label: t.label, labels: t.labels || {}, peak: t.peak }, brand: env('BRAND', 'EMPIRE MAPS'),
    timeline, voice: voiceAt, words, total, data_dir: path.join(ROOT, 'data'), out: path.join(dir, 'final.mp4'),
    title: s.title, preview: path.join(dir, 'preview.mp4'), thumb: path.join(dir, 'thumb.jpg'), thumb_text: s.thumb_text, ffmpeg: FFMPEG(), work: dir,
  };
  fs.writeFileSync(path.join(dir, 'long.json'), JSON.stringify(spec, null, 1));
  const ro = await run(PYTHON(), [path.join(__dirname, 'longtools.py'), path.join(dir, 'long.json')]);
  if (ro.trim()) log(ro.trim().split('\n').filter(l => !/^shots /.test(l)).join('\n'));
  const real = await duration(spec.out);
  log(`Video ready: ${(real / 60).toFixed(1)} min`);

  const chapters = ['0:00 Intro'];
  let at = 0;
  for (const it of timeline) { if (it.kind === 'chapter') chapters.push(`${Math.floor(at / 60)}:${String(Math.floor(at % 60)).padStart(2, '0')} ${it.heading}`); at += it.dur; }
  const credit = 'Map borders: historical-basemaps by André Ourednik (GPL-3.0). Narration: AI voice. Script fact-checked.';
  const desc = `${s.description}\n\n▶ A new empire map every day — subscribe: ${CHANNEL}\n\nChapters:\n${chapters.join('\n')}\n\n${credit}`;
  fs.writeFileSync(path.join(dir, 'meta.json'), JSON.stringify({ title: s.title, description: desc, tags: s.tags || [] }, null, 2));

  const entry = { topic: t.id, title: s.title, date: new Date().toISOString(), minutes: +(real / 60).toFixed(1) };
  if (!NO_UPLOAD) {
    const up = await uploadLong(spec.out, { title: s.title, description: desc, tags: s.tags || [] });
    entry.videoId = up.id; entry.publishAt = up.publishAt;
    try {
      const r = await fetch(`https://www.googleapis.com/upload/youtube/v3/thumbnails/set?videoId=${up.id}`, { method: 'POST', headers: { Authorization: `Bearer ${up.token}`, 'Content-Type': 'image/jpeg' }, body: fs.readFileSync(spec.thumb) });
      log(r.ok ? 'Thumbnail set' : `Thumbnail not set (HTTP ${r.status}: ${(await r.text()).slice(0, 200)})`);
    } catch (e) { log('Thumbnail not set: ' + e.message); }
    const h = readHist(); h.push(entry); fs.writeFileSync(HIST, JSON.stringify(h, null, 2));
  }
}

main().catch(e => { log('FAILED: ' + (e.stack || e.message)); process.exit(1); });
