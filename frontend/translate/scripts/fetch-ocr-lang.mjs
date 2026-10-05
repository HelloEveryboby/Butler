#!/usr/bin/env node
/* ============================================================
   下载 OCR 语言包（tesseract traineddata）到 vendor/lang/
   ------------------------------------------------------------
   这是【可选组件】：不下载也能用网页/PDF/文本翻译，
   只有图片翻译 / 截图翻译需要它。

   用法：
     npm run fetch:ocr-lang            # 下载 eng + chi_sim
     npm run fetch:ocr-lang -- jpn kor # 下载指定语言

   语言包来自 tessdata（Apache 2.0）：
     https://github.com/tesseract-ocr/tessdata_fast
   ============================================================ */

import { mkdir, writeFile, access } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const OUT_DIR = path.resolve(__dirname, '..', 'vendor', 'lang');

// tessdata_fast 4.0.0：体积小、速度快，适合浏览器端
const BASE = 'https://github.com/tesseract-ocr/tessdata_fast/raw/4.0.0';

const DEFAULT_LANGS = ['eng', 'chi_sim'];

async function exists(p) {
  try { await access(p); return true; } catch { return false; }
}

async function download(lang) {
  const file = path.join(OUT_DIR, `${lang}.traineddata.gz`);
  if (await exists(file)) {
    console.log(`  ✓ ${lang} 已存在，跳过`);
    return;
  }
  const url = `${BASE}/${lang}.traineddata.gz`;
  process.stdout.write(`  ↓ ${lang} ... `);
  const res = await fetch(url);
  if (!res.ok) {
    console.log(`失败（HTTP ${res.status}）`);
    process.exitCode = 1;
    return;
  }
  const buf = Buffer.from(await res.arrayBuffer());
  await writeFile(file, buf);
  console.log(`完成（${(buf.length / 1024 / 1024).toFixed(2)} MB）`);
}

const langs = process.argv.slice(2).filter(a => !a.startsWith('-'));
const list = langs.length ? langs : DEFAULT_LANGS;

console.log(`OCR 语言包下载 → ${OUT_DIR}`);
console.log(`语言：${list.join(', ')}`);
await mkdir(OUT_DIR, { recursive: true });
for (const lang of list) {
  await download(lang);
}
console.log('完成。构建后这些文件会随扩展打包到 dist/vendor/lang/，离线可用。');
