'use strict';
// Empire Maps: makes an animated history-map Short and uploads it to YouTube.
//   node make-video.js                        next empire, made and uploaded
//   node make-video.js --topic ottoman        a chosen empire (id or name from topics.json)
//   node make-video.js --no-upload            make it but do not upload (for testing)
//   node make-video.js --sample --no-upload   test video without any keys (Ottoman Empire)
const fs = require('fs');
const path = require('path');
const { ROOT, env, log, slugify } = require('./src/lib');
const { withRetry } = require('./src/retry');
const { writeScript, readHistory, addHistory, finish, TOPICS } = require('./src/script');
const { makeVoice } = require('./src/voice');
const { buildVideo } = require('./src/video');
const { upload } = require('./src/youtube');

function arg(name) {
  const i = process.argv.indexOf(name);
  return i === -1 ? null : (process.argv[i + 1] || '');
}
const NO_UPLOAD = process.argv.includes('--no-upload') || env('UPLOAD', 'yes').toLowerCase() === 'no';
const SAMPLE = process.argv.includes('--sample');

function sampleScript() {
  const t = TOPICS.find(x => x.id === 'ottoman');
  const years = [1400, 1492, 1530, 1600, 1800, 1914, 1920];
  return finish({ topic: t, angle: 'full', years }, {
    lines: [
      'In 1400, the Ottomans held a strip of Anatolia and the Balkans. Then they took everything.',
      'By 1492, Constantinople had fallen, and the thousand-year Byzantine Empire was gone.',
      'By 1530, Egypt, Syria and Iraq were Ottoman, and Suleiman was marching on Vienna.',
      'Around 1600, the empire stretched across three continents, from Hungary to the Persian Gulf.',
      'But by 1800, Russia and Austria were cutting pieces away, one war at a time.',
      'In 1914, the empire joined the First World War on the losing side.',
      'By 1920, only Anatolia was left, and a new Turkey rose from the ruins.',
      'Six centuries of power in under a minute. Which empire should I map next?',
    ],
    hook_text: 'The Empire That Ruled 3 Continents',
    title: 'How the Ottoman Empire Got So Big 🗺️',
    description: 'Six hundred years of Ottoman history on one map.\n\n#history #maps #shorts #ottomanempire',
    tags: ['ottoman empire', 'history', 'maps', 'empire', 'history maps', 'animated map'],
    scenes: [
      { markers: [{ name: 'Bursa', lat: 40.19, lon: 29.06 }], arrow: null },
      { markers: [{ name: 'Constantinople', lat: 41.01, lon: 28.98 }], arrow: { from: { lat: 40.19, lon: 29.06 }, to: { lat: 41.01, lon: 28.98 } } },
      { markers: [{ name: 'Cairo', lat: 30.04, lon: 31.24 }, { name: 'Vienna', lat: 48.21, lon: 16.37 }], arrow: { from: { lat: 41.01, lon: 28.98 }, to: { lat: 48.21, lon: 16.37 } } },
      { markers: [{ name: 'Baghdad', lat: 33.31, lon: 44.36 }], arrow: null },
      { markers: [], arrow: null },
      { markers: [{ name: 'Gallipoli', lat: 40.41, lon: 26.67 }], arrow: null },
      { markers: [{ name: 'Ankara', lat: 39.93, lon: 32.86 }], arrow: null },
    ],
  });
}

function cleanup() {
  const keepDays = Number(env('KEEP_DAYS', '7'));
  const outRoot = path.join(ROOT, 'output');
  for (const d of fs.readdirSync(outRoot)) {
    const p = path.join(outRoot, d);
    try { if (Date.now() - fs.statSync(p).mtimeMs > keepDays * 86400000) fs.rmSync(p, { recursive: true, force: true }); } catch (_) { /* ignore */ }
  }
}

(async () => {
  const script = SAMPLE ? sampleScript() : await writeScript(arg('--topic'));
  const n = new Date(), p = v => String(v).padStart(2, '0');
  const dir = path.join(ROOT, 'output', `${n.getFullYear()}-${p(n.getMonth() + 1)}-${p(n.getDate())}_${p(n.getHours())}-${p(n.getMinutes())}_${slugify(script.topic.id + '-' + script.angle)}`);
  fs.mkdirSync(dir, { recursive: true });
  fs.writeFileSync(path.join(dir, 'script.json'), JSON.stringify(script, null, 2));

  const voice = SAMPLE && !env('GEMINI_API_KEY') ? null : await makeVoice(script, dir, readHistory().length);
  if (!voice && !SAMPLE) throw new Error('No voice (Gemini TTS failed or its free daily limit is used up). Not uploading a silent video.');
  const video = await buildVideo(script, voice, dir);

  let videoId = null;
  if (NO_UPLOAD) log('Upload skipped (--no-upload). Video is in: ' + dir);
  else ({ id: videoId } = await withRetry('YouTube upload', () => upload(video.file, script), { tries: 3, waitMs: 45000, log }));

  if (!SAMPLE && !NO_UPLOAD) addHistory({ topic: script.topic.id, angle: script.angle, years: script.years, title: script.title, date: new Date().toISOString(), videoId });
  cleanup();
  log(`Done: "${script.title}" ${videoId ? 'https://youtube.com/shorts/' + videoId : ''}`);
})().catch(e => { log('Failed: ' + (e.stack || e.message)); process.exit(1); });
