'use strict';
// Builds the final video: map frames (render.py) + narration + music (ducked under the voice).
const fs = require('fs');
const path = require('path');
const { ROOT, log, run, FFMPEG, PYTHON } = require('./lib');

async function buildVideo(script, voice, dir) {
  const VSTART = 1.6; // the title hit plays alone first
  const speakDur = voice ? voice.dur : Math.max(20, script.lines.join(' ').split(' ').length / 2.6);
  const total = VSTART + speakDur + 2.2;
  let starts, ends;
  if (voice && voice.segments) {
    starts = voice.segments.map(sg => VSTART + sg.start - 0.05);
    ends = voice.segments.map(sg => VSTART + sg.end);
  } else {
    const chars = script.lines.map(l => l.length + 8);
    const sum = chars.reduce((a, b) => a + b, 0);
    let acc = 0;
    starts = chars.map(c => { const s = VSTART + speakDur * (acc / sum); acc += c; return s; });
    ends = starts.map((s, i) => (i + 1 < starts.length ? starts[i + 1] - 0.15 : VSTART + speakDur));
  }
  const silent = path.join(dir, 'silent.mp4');
  const spec = {
    topic: script.topic, scenes: script.scenes, lines: script.lines, hook_text: script.hook_text,
    line_starts: starts, line_ends: ends, total, intro: VSTART, voice_end: VSTART + speakDur,
    font_serif: path.join(ROOT, 'fonts', 'Lora-Variable.ttf'), font_bold: path.join(ROOT, 'fonts', 'Poppins-Bold.ttf'),
    font_medium: path.join(ROOT, 'fonts', 'Poppins-Medium.ttf'),
    data_dir: path.join(ROOT, 'data'), ffmpeg: FFMPEG(), out: silent, seed: Date.now() % 100000,
  };
  const specFile = path.join(dir, 'render.json');
  fs.writeFileSync(specFile, JSON.stringify(spec, null, 2));
  log(`Drawing map video (${total.toFixed(1)}s)...`);
  await run(PYTHON(), [path.join(ROOT, 'src', 'render.py'), specFile]);

  const music = path.join(dir, 'music.wav');
  await run(PYTHON(), [path.join(ROOT, 'src', 'music.py'), specFile, music]);
  const file = path.join(dir, 'final.mp4');
  const inputs = ['-i', silent, '-i', music];
  let filter;
  if (voice) {
    inputs.push('-i', voice.file);
    filter = `[2:a]aformat=sample_rates=48000:channel_layouts=stereo,adelay=${Math.round(VSTART * 1000)}:all=1,apad,asplit=2[v1][v2];` +
      `[1:a]volume=1.0[m];[m][v2]sidechaincompress=threshold=0.06:ratio=3:attack=30:release=450[md];` +
      `[md][v1]amix=inputs=2:duration=first:normalize=0,loudnorm=I=-14:TP=-1.5:LRA=9,aresample=48000[aout]`;
  } else {
    filter = '[1:a]loudnorm=I=-14:TP=-1.5,aresample=48000[aout]';
  }
  await run(FFMPEG(), ['-y', '-loglevel', 'error', ...inputs, '-filter_complex', filter, '-map', '0:v', '-map', '[aout]',
    '-c:v', 'copy', '-c:a', 'aac', '-b:a', '192k', '-ac', '2', '-t', total.toFixed(2), '-movflags', '+faststart', file]);
  for (const x of [silent, music]) fs.rmSync(x, { force: true });
  log(`Video ready: ${file}`);
  return { file, duration: total };
}

module.exports = { buildVideo };
