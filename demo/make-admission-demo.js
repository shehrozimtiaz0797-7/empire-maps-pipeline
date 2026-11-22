'use strict';
// One demo Short for a possible new channel (Malaysia admissions, Urdu voice, Roman Urdu captions).
// The facts were checked by hand against EMGS and university pages on 22 Nov 2026. Nothing is uploaded.
// Usage: node demo/make-admission-demo.js
const fs = require('fs');
const path = require('path');
const { ROOT, log, run, FFMPEG, PYTHON } = require('../src/lib');
const { makeVoice } = require('../src/voice');

const SCENES = [
  { kind: 'title', title: 'MALAYSIA STUDENT VISA', badge: '5 ASAAN STEPS',
    urdu: 'ملائیشیا میں پڑھنا ہے؟ اسٹوڈنٹ ویزا کے پانچ آسان مراحل، یاد کر لیں۔',
    caption: 'Malaysia mein parhna hai? Student visa ke 5 asaan steps, yaad kar lein.' },
  { kind: 'step', n: 1, title: 'OFFER LETTER', detail: 'Recognised Malaysian university se admission offer',
    urdu: 'پہلا قدم: کسی تسلیم شدہ ملائیشین یونیورسٹی سے آفر لیٹر لیں۔',
    caption: 'Pehla step: kisi recognised Malaysian university se offer letter lein.' },
  { kind: 'step', n: 2, title: 'EMGS APPLICATION', detail: 'University aap ki student pass application EMGS mein jama karti hai — apne mulk se',
    urdu: 'دوسرا: یونیورسٹی آپ کی اسٹوڈنٹ پاس کی درخواست ای ایم جی ایس میں جمع کرتی ہے۔ یہ اپنے ملک سے ہی ہوتا ہے۔',
    caption: 'Doosra: university aap ki student pass application EMGS mein jama karti hai. Ye apne mulk se hi hota hai.' },
  { kind: 'step', n: 3, title: 'eVAL', detail: 'Approval ke baad Visa Approval Letter milta hai',
    urdu: 'تیسرا: منظوری کے بعد آپ کو ای ویل ملتا ہے، یعنی ویزا اپروول لیٹر۔',
    caption: 'Teesra: approval ke baad aap ko eVAL milta hai, yani Visa Approval Letter.' },
  { kind: 'step', n: 4, title: 'SINGLE ENTRY VISA', detail: 'Pakistan aur India ke students Malaysian embassy se SEV lete hain',
    urdu: 'چوتھا: پاکستان اور انڈیا کے طلبہ ای ویل کے ساتھ ملائیشین ایمبیسی سے سنگل انٹری ویزا لیتے ہیں۔',
    caption: 'Chautha: Pakistan aur India ke students eVAL ke saath Malaysian embassy se Single Entry Visa lete hain.' },
  { kind: 'step', n: 5, title: 'MEDICAL + STUDENT PASS', detail: 'Malaysia pohanch kar 7 din ke andar medical, phir passport par student pass',
    urdu: 'پانچواں: ملائیشیا پہنچ کر سات دن کے اندر میڈیکل، پھر پاسپورٹ پر اسٹوڈنٹ پاس لگتا ہے۔',
    caption: 'Paanchwa: Malaysia pohanch kar 7 din ke andar medical, phir passport par student pass lagta hai.' },
  { kind: 'warn', title: 'TOURIST VISA PAR NAHI', detail: 'Tourist visa par aa kar student pass nahi banta',
    urdu: 'یاد رکھیں: ٹورسٹ ویزا پر آ کر اسٹوڈنٹ پاس نہیں بنتا۔',
    caption: 'Yaad rakhein: tourist visa par aa kar student pass nahi banta.' },
  { kind: 'cta', title: 'ADMISSION HELP', contact: 'WhatsApp: +60 XX-XXX XXXX', detail: 'Free guidance — number description mein',
    urdu: 'داخلے اور ویزا میں مدد چاہیے؟ ڈسکرپشن میں دیے گئے نمبر پر واٹس ایپ کریں۔',
    caption: 'Admission aur visa mein madad chahiye? Description mein diye number par WhatsApp karein.' },
];

async function main() {
  const dir = path.join(ROOT, 'output', 'demo-admission');
  fs.mkdirSync(dir, { recursive: true });
  const voice = await makeVoice({ lines: SCENES.map(s => s.urdu) }, dir, 0);
  if (!voice) throw new Error('no voice');
  const LEAD = 0.6;
  const spec = {
    scenes: SCENES, segments: voice.segments, voice: voice.file, lead: LEAD, total: LEAD + voice.dur + 1.2,
    data_dir: path.join(ROOT, 'data'), out: path.join(dir, 'demo.mp4'), work: dir, ffmpeg: FFMPEG(),
  };
  fs.writeFileSync(path.join(dir, 'spec.json'), JSON.stringify(spec, null, 1));
  const o = await run(PYTHON(), [path.join(__dirname, 'admission_short.py'), path.join(dir, 'spec.json')]);
  log(o.trim());
}

main().catch(e => { log('FAILED: ' + (e.stack || e.message)); process.exit(1); });
