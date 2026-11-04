// Render every frame of a scene page to PNG via headless Chromium.
// usage: node tools/render.js render/ep01_intro.html build/ep01_intro [frame,frame,...]
// The page must expose window.setTimeline(tl) and async window.render(frame) -> dataURL.
const { chromium } = require('playwright');
const fs = require('fs'), path = require('path'), http = require('http');

const ROOT = path.resolve(__dirname, '..');
const TYPES = { '.html': 'text/html', '.js': 'text/javascript', '.mjs': 'text/javascript', '.json': 'application/json', '.jpg': 'image/jpeg', '.png': 'image/png' };

function serve() {
  return new Promise(res => {
    const s = http.createServer((req, rsp) => {
      const p = path.join(ROOT, decodeURIComponent(req.url.split('?')[0]));
      if (!p.startsWith(ROOT) || !fs.existsSync(p) || fs.statSync(p).isDirectory()) { rsp.writeHead(404); return rsp.end(); }
      rsp.writeHead(200, { 'Content-Type': TYPES[path.extname(p)] || 'application/octet-stream' });
      fs.createReadStream(p).pipe(rsp);
    }).listen(0, '127.0.0.1', () => res(s));
  });
}

(async () => {
  const [page, outDir, list] = process.argv.slice(2);
  const tl = JSON.parse(fs.readFileSync(path.join(outDir, 'timeline.json')));
  if (process.env.NO_CAPTIONS) tl.noCaptions = true;   // captions delivered as YouTube subtitle files instead
  const framesDir = path.join(outDir, 'frames');
  fs.mkdirSync(framesDir, { recursive: true });
  const frames = list ? list.split(',').map(Number) : Array.from({ length: tl.frames }, (_, i) => i);
  const server = await serve();
  const url = `http://127.0.0.1:${server.address().port}/${page}`;
  const browser = await chromium.launch({ args: ['--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'] });
  const workers = Math.min(Number(process.env.WORKERS || 4), frames.length);
  let done = 0;
  await Promise.all(Array.from({ length: workers }, async (_, w) => {
    const p = await browser.newPage({ viewport: { width: 1920, height: 1080 } });
    p.on('pageerror', e => console.error('PAGE ERROR', e.message));
    p.on('console', m => { if (m.type() === 'error') console.error('CONSOLE', m.text()); });
    await p.goto(url, { timeout: 180000 });
    await p.waitForFunction(() => window.ready === true, null, { timeout: 180000 });
    await p.evaluate(tl => window.setTimeline(tl), tl);
    for (let k = w; k < frames.length; k += workers) {
      const f = frames[k];
      const data = await p.evaluate(f => window.render(f), f);
      fs.writeFileSync(path.join(framesDir, `f${String(f).padStart(5, '0')}.png`), Buffer.from(data.split(',')[1], 'base64'));
      if (++done % 100 === 0) console.log(`${done}/${frames.length}`);
    }
  }));
  await browser.close(); server.close();
})();
