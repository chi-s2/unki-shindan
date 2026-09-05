/**
 * アイキャッチ画像を作る。
 *   node _source/make-images.js
 * posts/*.md の eyecatchTitle / eyecatchSub / category を読んで
 * images/eyecatch-<ファイル名>.png を書き出す。トップ用のOGP画像も作る。
 */
const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');

const SRC = __dirname;
const OUT = path.join(SRC, '..', 'images');
const CFG = JSON.parse(fs.readFileSync(path.join(SRC, 'config.json'), 'utf8'));

function readPosts() {
  const dir = path.join(SRC, 'posts');
  return fs.readdirSync(dir).filter(f => f.endsWith('.md')).map(f => {
    const raw = fs.readFileSync(path.join(dir, f), 'utf8');
    const front = raw.split('\n---\n')[0];
    const meta = { slug: f.replace(/\.md$/, '') };
    for (const ln of front.trim().split('\n')) {
      const idx = ln.indexOf(':');
      if (idx > 0) meta[ln.slice(0, idx).trim()] = ln.slice(idx + 1).trim();
    }
    return meta;
  });
}

const template = (cat, title, sub, site) => `<!doctype html><html lang="ja"><head><meta charset="utf-8"><style>
  * { margin:0; padding:0; box-sizing:border-box; }
  body { width:1200px; height:630px; overflow:hidden;
         font-family:"IPAPGothic","IPAGothic","Hiragino Kaku Gothic ProN",sans-serif; }
  .card { position:relative; width:1200px; height:630px;
          background:linear-gradient(145deg,#fbdde2 0%,#fdeef0 42%,#fffaf8 100%);
          overflow:hidden; }
  .blob { position:absolute; border-radius:50%; }
  .b1 { width:520px; height:520px; right:-140px; bottom:-190px;
        background:radial-gradient(circle at 32% 32%, rgba(224,138,149,.34), rgba(224,138,149,.07)); }
  .b2 { width:260px; height:260px; right:150px; top:-90px;
        background:radial-gradient(circle at 40% 40%, rgba(201,160,119,.26), rgba(201,160,119,.04)); }
  .ring { position:absolute; right:96px; bottom:78px; width:190px; height:190px;
          border:2px solid rgba(189,85,103,.26); border-radius:50%; }
  .inner { position:relative; padding:86px 92px; height:100%; display:flex; flex-direction:column; }
  .cat { display:flex; align-items:center; gap:16px;
         font-size:25px; color:#bd5567; letter-spacing:.16em; font-weight:bold; }
  .cat::before { content:""; width:46px; height:3px; background:#e08a95; border-radius:2px; }
  h1 { margin-top:38px; font-size:62px; line-height:1.52; color:#3a3034;
       letter-spacing:.02em; font-weight:bold; }
  h1 em { font-style:normal; color:#bd5567; }
  .sub { margin-top:auto; margin-bottom:76px; font-size:26px; color:#7a6e72;
         letter-spacing:.04em; line-height:1.6; padding-right:300px; }
  .site { position:absolute; left:92px; bottom:52px;
          font-size:23px; color:#bd5567; letter-spacing:.1em; font-weight:bold; }
</style></head><body>
  <div class="card">
    <div class="blob b1"></div><div class="blob b2"></div><div class="ring"></div>
    <div class="inner">
      <div class="cat">${cat}</div>
      <h1>${title}</h1>
      <div class="sub">${sub}</div>
    </div>
    <div class="site">${site}</div>
  </div>
</body></html>`;

(async () => {
  fs.mkdirSync(OUT, { recursive: true });
  const browser = await chromium.launch({
    executablePath: process.env.CHROMIUM_PATH || '/opt/pw-browsers/chromium',
  });
  const page = await browser.newPage({ viewport: { width: 1200, height: 630 } });

  for (const p of readPosts()) {
    await page.setContent(
      template(p.category || '', p.eyecatchTitle || p.title || '', p.eyecatchSub || '', CFG.company),
      { waitUntil: 'load' });
    await page.waitForTimeout(250);
    const file = path.join(OUT, `eyecatch-${p.slug}.png`);
    await page.screenshot({ path: file });
    console.log('書き出し:', path.basename(file));
  }

  // トップページのOGP画像
  await page.setContent(
    template('AI × CONTENT', CFG.hero.title, CFG.tagline, CFG.company), { waitUntil: 'load' });
  await page.waitForTimeout(250);
  await page.screenshot({ path: path.join(OUT, 'ogp-top.png') });
  console.log('書き出し: ogp-top.png');

  await browser.close();
})();
