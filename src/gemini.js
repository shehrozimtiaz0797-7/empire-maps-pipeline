'use strict';
// Gemini: text (JSON) and text-to-speech.
const { env, requireEnv, fetchRetry } = require('./lib');

const BASE = 'https://generativelanguage.googleapis.com/v1beta/models';

function parseJSON(text) {
  const cleaned = String(text).replace(/^\s*```(?:json)?/i, '').replace(/```\s*$/, '').trim();
  try { return JSON.parse(cleaned); } catch (_) {
    const s = cleaned.indexOf('{'); const e = cleaned.lastIndexOf('}');
    if (s !== -1 && e > s) return JSON.parse(cleaned.slice(s, e + 1));
    throw new Error('Gemini did not return valid JSON');
  }
}

// Main key first; if its daily free limit is used up (HTTP 429), the backup key GEMINI_API_KEY_2 (another project) is used.
async function call(model, body) {
  const keys = [requireEnv('GEMINI_API_KEY'), env('GEMINI_API_KEY_2', '')].filter(Boolean);
  let last;
  for (let i = 0; i < keys.length; i++) {
    const res = await fetchRetry(`${BASE}/${model}:generateContent`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'x-goog-api-key': keys[i] },
      body: JSON.stringify(body),
    }, i + 1 < keys.length ? 2 : 3);
    const text = await res.text();
    if (res.ok) {
      if (i > 0) console.log(`[gemini] ${model}: used the backup key`);
      return JSON.parse(text);
    }
    last = new Error(`Gemini ${model} HTTP ${res.status}: ${text.slice(0, 400)}`);
    if (res.status !== 429) break;
  }
  throw last;
}

// main model first, then backups (a busy model answers 503 / 429 now and then)
const textModels = () => [...new Set([env('GEMINI_TEXT_MODEL', 'gemini-3.8-flash'), 'gemini-3.5-flash', 'gemini-3.5-flash-lite'])];

async function askJSON(prompt, { temperature = 0.9 } = {}) {
  let last;
  for (const model of textModels()) {
    try {
      const data = await call(model, {
        contents: [{ role: 'user', parts: [{ text: prompt }] }],
        generationConfig: { temperature, responseMimeType: 'application/json' },
      });
      const parts = data?.candidates?.[0]?.content?.parts || [];
      const text = parts.filter(p => p.text && !p.thought).map(p => p.text).join('');
      if (!text) throw new Error('Gemini returned no text: ' + JSON.stringify(data).slice(0, 300));
      return parseJSON(text);
    } catch (e) { last = e; }
  }
  throw last;
}

// Returns raw 16-bit mono PCM at 24000 Hz.
async function speak(text, voice) {
  const model = env('GEMINI_TTS_MODEL', 'gemini-3.8-flash-tts');
  const data = await call(model, {
    contents: [{ role: 'user', parts: [{ text }] }],
    generationConfig: {
      responseModalities: ['AUDIO'],
      speechConfig: { voiceConfig: { prebuiltVoiceConfig: { voiceName: voice } } },
    },
  });
  const part = (data?.candidates?.[0]?.content?.parts || []).find(p => p.inlineData && p.inlineData.data);
  if (!part) throw new Error('Gemini TTS returned no audio: ' + JSON.stringify(data).slice(0, 300));
  return Buffer.from(part.inlineData.data, 'base64');
}

module.exports = { askJSON, speak, parseJSON };
