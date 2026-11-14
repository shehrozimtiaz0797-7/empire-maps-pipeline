'use strict';
// Documentary narration with Gemini TTS (one request per video), then finds where each line starts.
const fs = require('fs');
const path = require('path');
const { env, log, run, duration, FFMPEG } = require('./lib');
const { speak } = require('./gemini');
const { withRetry } = require('./retry');

const TRIM = 'silenceremove=start_periods=1:start_threshold=-45dB,areverse,silenceremove=start_periods=1:start_threshold=-45dB,areverse';

// Finds where each line is spoken. The pauses between lines are silences in the dry voice (no echo).
// Each boundary is "snapped" to the real pause closest to where it should be by line length, so one missing
// pause never shifts the other lines.
async function lineSegments(dryWav, dur, lines) {
  const { spawn } = require('child_process');
  const out = await new Promise(resolve => {
    const p = spawn(FFMPEG(), ['-hide_banner', '-i', dryWav, '-af', 'silencedetect=noise=-36dB:d=0.12', '-f', 'null', '-']);
    let err = ''; p.stderr.on('data', d => { err += d; }); p.on('close', () => resolve(err));
  });
  const gaps = []; let st = null;
  for (const line of out.split('\n')) {
    const a = line.match(/silence_start: ([\d.]+)/); const b = line.match(/silence_end: ([\d.]+)/);
    if (a) st = Number(a[1]);
    if (b && st !== null) { gaps.push({ start: st, end: Number(b[1]) }); st = null; }
  }
  const inner = gaps.filter(g => g.start > 0.3 && g.end < dur - 0.2);
  const chars = lines.map(l => l.replace(/\*/g, '').length + 4);
  const avg = dur / lines.length;
  const cuts = [];
  let prev = 0, snapped = 0;
  for (let k = 0; k < lines.length - 1; k++) {
    const left = chars.slice(k).reduce((x, y) => x + y, 0);
    const expect = prev + (dur - prev) * chars[k] / left;
    let best = null, score = -1e9;
    for (const g of inner) {
      const mid = (g.start + g.end) / 2;
      if (g.start < prev + 0.5 || Math.abs(mid - expect) > avg * 0.5) continue;
      const s = (g.end - g.start) * 3 - Math.abs(mid - expect) / avg;
      if (s > score) { score = s; best = g; }
    }
    if (best) { cuts.push(best); prev = best.end; snapped++; } else { cuts.push({ start: expect - 0.05, end: expect + 0.05 }); prev = expect + 0.05; }
  }
  const segs = [];
  let s0 = 0;
  for (const g of cuts) { segs.push({ start: s0, end: g.start }); s0 = g.end; }
  segs.push({ start: s0, end: dur });
  return { segs, snapped, need: lines.length - 1 };
}

let turn = 0;
async function makeVoice(script, dir, n) {
  if (!env('GEMINI_API_KEY') || env('VOICE', 'on') === 'off') return null;
  const voices = env('GEMINI_TTS_VOICE', 'Charon,Orus').split(',').map(s => s.trim()).filter(Boolean);
  const voice = voices[(n + turn++) % voices.length];
  // only the words: one sentence per line, with pauses between lines
  const text = script.lines.map(l => l.replace(/\*/g, '').replace(/([^.!?])$/, '$1.')).join('\n\n...\n\n');
  try {
    const pcm = await withRetry('Voice', () => speak(text, voice), { tries: 2, waitMs: 20000, log });
    const raw = path.join(dir, 'voice.pcm'); const wav = path.join(dir, 'voice.wav');
    fs.writeFileSync(raw, pcm);
    const pitch = Number(env('VOICE_PITCH', '0.97')); const pace = Number(env('VOICE_PACE', '1.03'));
    await run(FFMPEG(), ['-y', '-loglevel', 'error', '-f', 's16le', '-ar', '24000', '-ac', '1', '-i', raw, '-af',
      `${TRIM},asetrate=${Math.round(24000 * pitch)},aresample=48000,atempo=${(pace / pitch).toFixed(4)},` +
      'highpass=f=70,equalizer=f=120:t=q:w=1:g=3,equalizer=f=3000:t=q:w=1.2:g=2,' +
      'acompressor=threshold=0.12:ratio=3:attack=5:release=90,aecho=0.8:0.5:35|60:0.10|0.06,loudnorm=I=-15:TP=-1.5',
      '-ar', '48000', wav]);
    // same timing as the final voice, but dry (no echo / compression) so the pauses between lines are clean
    const dry = path.join(dir, 'voice_dry.wav');
    await run(FFMPEG(), ['-y', '-loglevel', 'error', '-f', 's16le', '-ar', '24000', '-ac', '1', '-i', raw, '-af',
      `${TRIM},asetrate=${Math.round(24000 * pitch)},aresample=48000,atempo=${(pace / pitch).toFixed(4)}`, '-ar', '48000', dry]);
    fs.rmSync(raw, { force: true });
    const dur = await duration(wav);
    const found = await lineSegments(dry, dur, script.lines);
    fs.rmSync(dry, { force: true });
    log(`Voice ready (${voice}, ${dur.toFixed(1)}s, line pauses found: ${found.snapped}/${found.need})`);
    return { file: wav, dur, segments: found.segs };
  } catch (e) {
    log(`Voice failed: ${String(e.message).slice(0, 200)}`);
    return null;
  }
}

module.exports = { makeVoice };
