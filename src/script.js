'use strict';
// Picks the next empire and writes the narration (one line per map year) with Gemini, then fact-checks it.
const fs = require('fs');
const path = require('path');
const { ROOT, log } = require('./lib');
const { askJSON } = require('./gemini');

const HISTORY = path.join(ROOT, 'history.json');
const TOPICS = JSON.parse(fs.readFileSync(path.join(ROOT, 'topics.json'), 'utf8'));

function readHistory() { try { return JSON.parse(fs.readFileSync(HISTORY, 'utf8')); } catch (_) { return []; } }
function addHistory(entry) {
  const h = readHistory(); h.push(entry);
  fs.writeFileSync(HISTORY, JSON.stringify(h.slice(-500), null, 2));
}

// Every topic can be told 3 ways: the rise (start -> peak), the fall (peak -> end) and the whole story.
function angles(t) {
  const i = t.years.indexOf(t.peak);
  const out = [];
  if (i >= 2) out.push({ angle: 'rise', years: t.years.slice(0, i + 1) });
  if (i >= 0 && t.years.length - i >= 3) out.push({ angle: 'fall', years: t.years.slice(i) });
  out.push({ angle: 'full', years: t.years.length > 7 ? pickSpread(t.years, 7, t.peak) : t.years });
  return out;
}
function pickSpread(ys, n, keep) {
  const idx = new Set([0, ys.length - 1, ys.indexOf(keep)]);
  for (let k = 1; idx.size < n && k < n; k++) idx.add(Math.round(k * (ys.length - 1) / (n - 1)));
  return [...idx].filter(i => i >= 0).sort((a, b) => a - b).map(i => ys[i]);
}

function pickTopic(wanted) {
  const done = readHistory().map(h => `${h.topic}:${h.angle}`);
  const recent = readHistory().slice(-6).map(h => h.topic);
  const all = [];
  for (const t of TOPICS) for (const a of angles(t)) all.push({ topic: t, ...a });
  if (wanted) {
    const w = String(wanted).toLowerCase();
    const hit = all.filter(x => x.topic.id === w || x.topic.name.toLowerCase().includes(w) || x.topic.label.toLowerCase().includes(w));
    if (hit.length) return hit.find(x => !done.includes(`${x.topic.id}:${x.angle}`)) || hit[0];
  }
  // never-made first, but not the same empire as the last few videos; 'rise' stories first (they do best)
  const order = { rise: 0, full: 1, fall: 2 };
  const fresh = all.filter(x => !done.includes(`${x.topic.id}:${x.angle}`) && !recent.includes(x.topic.id));
  const pool = fresh.length ? fresh : all.filter(x => !recent.includes(x.topic.id));
  // topics.json is in order of how popular the empire is: famous empires first
  const rank = x => TOPICS.indexOf(x.topic);
  pool.sort((a, b) => order[a.angle] - order[b.angle] || rank(a) - rank(b));
  return pool[0];
}

const yearText = y => (y < 0 ? `${-y} BC` : y < 1000 ? `${y} AD` : String(y));

function prompt(p) {
  const ys = p.years.map(yearText).join(', ');
  const story = { rise: `how ${p.topic.name} grew from small beginnings to its peak`, fall: `how ${p.topic.name} shrank and fell after its peak`, full: `the whole rise and fall of ${p.topic.name}` }[p.angle];
  return `You write narration for "Empire Maps", a YouTube Shorts channel of animated history maps (like Kings and Generals, but 50 seconds).
The video shows the borders of ${p.topic.name} on a map at these snapshot years, one after another: ${ys}.
Story of this video: ${story}.

Write:
- "lines": exactly ${p.years.length + 1} narration lines. Line 1 goes with the map of ${yearText(p.years[0])}, line 2 with ${yearText(p.years[1] ?? p.years[0])}, and so on; the LAST line is extra and goes with the final map.
  * Line 1 is the hook: it must make people stay (surprise, contrast or a question), e.g. "In 1300, Moscow was a small town. 600 years later, it ruled a sixth of the world."
  * Each middle line starts with its year ("By 1530, ...", "In 1700, ...") and says what changed on the map around that time: conquests, wars, losses, who they fought. Name real places and real rulers.
  * The last line lands the story in one strong sentence, then asks the viewer a question to answer in the comments.
  * 10 to 18 words per line. ${Math.round((p.years.length + 1) * 13)} to ${Math.round((p.years.length + 1) * 16)} words in total. Simple, vivid English, like a great documentary narrator.
  * Only well-known, true history. No made-up numbers. Dates must match the snapshot years. Neutral tone: no praise or hate of any religion, nation or people.
- "scenes": exactly ${p.years.length} objects, one per snapshot year, in order: {"markers": [up to 2 famous cities or battle sites that the line for that year talks about, each {"name": "short name", "lat": number, "lon": number}], "arrow": null or {"from": {"lat","lon"}, "to": {"lat","lon"}} for a famous campaign or conquest in that line}. Coordinates must be real (decimal degrees).
- "hook_text": the on-screen title, 4 to 7 words, a curiosity title different from line 1 (e.g. "How Russia Became the Biggest Country", "The Empire That Ruled 3 Continents").
- "title": YouTube title under 70 characters with 1 emoji at the end, curious and searchable (e.g. "How the Ottoman Empire Got So Big 🗺️").
- "description": 2 short sentences about the video, then a blank line, then 4 hashtags (#history #maps #shorts and one about the empire).
- "tags": 10 to 14 search tags.

Return ONLY JSON: {"lines": [...], "scenes": [...], "hook_text": "...", "title": "...", "description": "...", "tags": [...]}`;
}

function checkPrompt(p, s) {
  return `You are a careful history fact-checker. These narration lines go with maps of ${p.topic.name} at the years ${p.years.map(yearText).join(', ')} (the last line is a closing line).
${JSON.stringify(s.lines, null, 1)}

Fix any line that has a wrong fact, a wrong date, an exaggeration presented as fact, or that does not fit its year. Keep the same number of lines, the same style and about the same length (10 to 18 words each). Keep correct lines exactly as they are.
Return ONLY JSON: {"lines": [...], "changed": number of lines you changed}`;
}

const num = v => (typeof v === 'number' ? v : Number(v));
function cleanScenes(raw, n) {
  const out = [];
  for (let i = 0; i < n; i++) {
    const s = (raw || [])[i] || {};
    const ok = m => m && Number.isFinite(num(m.lat)) && Number.isFinite(num(m.lon)) && Math.abs(num(m.lat)) <= 85 && Math.abs(num(m.lon)) <= 180;
    const markers = (s.markers || []).filter(ok).slice(0, 2).map(m => ({ name: String(m.name || '').slice(0, 22), lat: num(m.lat), lon: num(m.lon) }));
    const arrow = s.arrow && ok(s.arrow.from) && ok(s.arrow.to) ? { from: { lat: num(s.arrow.from.lat), lon: num(s.arrow.from.lon) }, to: { lat: num(s.arrow.to.lat), lon: num(s.arrow.to.lon) } } : null;
    out.push({ markers, arrow });
  }
  return out;
}

function validate(p, s) {
  const n = p.years.length;
  const lines = (s.lines || []).map(l => String(l).replace(/\s+/g, ' ').trim()).filter(Boolean);
  if (lines.length !== n + 1) throw new Error(`need ${n + 1} lines, got ${lines.length}`);
  const words = lines.join(' ').split(' ').length;
  if (words < (n + 1) * 9 || words > (n + 1) * 19) throw new Error(`script is ${words} words`);
  const hook = String(s.hook_text || '').trim();
  if (!hook || hook.split(/\s+/).length > 9) throw new Error('bad hook_text');
  return {
    lines, hook_text: hook,
    title: String(s.title || hook).slice(0, 95),
    description: String(s.description || '').trim(),
    tags: (Array.isArray(s.tags) ? s.tags : []).map(String).slice(0, 15),
    scenes: cleanScenes(s.scenes, n),
  };
}

async function writeScript(wanted) {
  const p = pickTopic(wanted);
  log(`Topic: ${p.topic.name} (${p.angle}: ${p.years.map(yearText).join(', ')})`);
  let last;
  for (let a = 1; a <= 3; a++) {
    try {
      const s = validate(p, await askJSON(prompt(p), { temperature: 0.8 }));
      try {
        const c = await askJSON(checkPrompt(p, s), { temperature: 0.2 });
        if (Array.isArray(c.lines) && c.lines.length === s.lines.length) {
          if (c.changed) log(`Fact-check changed ${c.changed} line(s)`);
          s.lines = c.lines.map(l => String(l).replace(/\s+/g, ' ').trim());
        }
      } catch (e) { log('Fact-check skipped: ' + e.message); }
      return finish(p, s);
    } catch (e) { last = e; log(`Script attempt ${a} not usable (${e.message})`); }
  }
  throw last;
}

function finish(p, s) {
  const scenes = p.years.map((y, i) => ({ year: y, ...s.scenes[i] }));
  scenes.push({ year: p.years[p.years.length - 1], markers: [], arrow: null }); // closing line on the last map
  const credit = 'Map borders: historical-basemaps by André Ourednik (GPL-3.0). Narration: AI voice.';
  return {
    topic: { id: p.topic.id, label: p.topic.label, name: p.topic.name, names: p.topic.names }, angle: p.angle, years: p.years,
    lines: s.lines, scenes, hook_text: s.hook_text,
    title: s.title, description: `${s.description}\n\n${credit}`.trim(), tags: s.tags,
  };
}

module.exports = { writeScript, readHistory, addHistory, pickTopic, finish, TOPICS };
