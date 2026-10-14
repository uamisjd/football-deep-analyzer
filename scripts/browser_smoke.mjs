// Smoke test reale Chromium: campione per lega, due viewport e temi, axe WCAG AA.
// npm ci && npx playwright install --with-deps chromium && npm run test:browser
// FDA_CHROMIUM_PATH consente un binario già installato (sandbox); output ignorato da Git.
import { chromium } from 'playwright';
import AxeBuilder from '@axe-core/playwright';
import { createServer } from 'node:http';
import { readFile, readdir, mkdir, writeFile } from 'node:fs/promises';
import { resolve, extname, join, relative, sep } from 'node:path';

const root = resolve(process.env.FDA_SITE_DIR || 'site');
const output = resolve('browser-results');
const types = { '.html':'text/html; charset=utf-8', '.css':'text/css', '.woff2':'font/woff2', '.xml':'application/xml' };
const server = createServer(async (req, res) => {
  try {
    const pathname = decodeURIComponent(new URL(req.url, 'http://audit.invalid').pathname);
    const file = resolve(root, '.' + pathname + (pathname.endsWith('/') ? 'index.html' : ''));
    if (relative(root, file).split(sep).includes('..')) { res.writeHead(403).end(); return; }
    const data = await readFile(file);
    res.writeHead(200, { 'Content-Type':types[extname(file)] || 'application/octet-stream' }).end(data);
  } catch { res.writeHead(404).end(); }
});
await new Promise(r => server.listen(0, '127.0.0.1', r));
const base = `http://127.0.0.1:${server.address().port}`;
const pages = ['index.html','prossime.html','risultati.html','accuratezza.html','stato.html','laboratorio.html','giocatori/index.html'];
const seen = new Set();
for (const name of (await readdir(join(root,'partite'))).sort()) {
  if (!name.endsWith('.html')) continue;
  const text = await readFile(join(root,'partite',name), 'utf8');
  const league = /<p class="crumb">.*?<span>([^<]+)<\/span><\/p>/.exec(text)?.[1];
  if (!league) continue;
  const kind = text.includes('id="notizie"') ? 'pre' : 'post';
  const key = `${league}:${kind}`;
  if (!seen.has(key)) { seen.add(key); pages.push(`partite/${name}`); }
}
await mkdir(output, {recursive:true});
const failures = [], checks = [];
let browser;
try {
  browser = await chromium.launch({
    executablePath:process.env.FDA_CHROMIUM_PATH || undefined,
    args:['--no-sandbox','--disable-dev-shm-usage','--use-gl=angle','--use-angle=swiftshader','--enable-unsafe-swiftshader'],
    headless:true
  });
  for (const width of [375,1280]) for (const theme of ['light','dark']) {
    const context = await browser.newContext({viewport:{width,height:900},colorScheme:theme});
    const page = await context.newPage();
    let current = '';
    page.on('pageerror', e => failures.push({page:current,width,theme,type:'javascript',message:e.message}));
    for (const file of pages) {
      current = file;
      const response = await page.goto(`${base}/${file}`, {waitUntil:'load'});
      if (response?.status() !== 200) { failures.push({file,width,theme,type:'http'}); continue; }
      await page.evaluate(() => document.fonts.ready);
      const geometry = await page.evaluate(() => ({w:innerWidth,scroll:document.documentElement.scrollWidth}));
      if (geometry.scroll > geometry.w + 1) failures.push({file,width,theme,type:'overflow',geometry});
      const title = await page.title();
      if (/<[a-z]/i.test(title)) failures.push({file,width,theme,type:'title',title});
      // La prima Tab deve rendere visibile il salto al contenuto.
      await page.keyboard.press('Tab');
      if (!await page.locator('.skip-link').evaluate(e=>e===document.activeElement))
        failures.push({file,width,theme,type:'keyboard-skip-link'});
      if (file === 'prossime.html') {
        const search=page.locator('[data-match-search]');
        await search.fill('zzzz_no_team_zzzz');
        // La ricerca ha debounce 120 ms + requestAnimationFrame: osservare l'esito,
        // non fotografare il DOM prima che il filtro abbia avuto tempo di applicarsi.
        await page.waitForFunction(() => [...document.querySelectorAll('[data-match-card]')].every(e=>e.hidden), null, {timeout:5000});
        await search.fill('');
        await page.waitForFunction(() => [...document.querySelectorAll('[data-match-card]')].some(e=>!e.hidden), null, {timeout:5000});
      }
      if (file.startsWith('partite/')) {
        const deepLink = page.locator('main a[href="#probabilita"]').first();
        if (await deepLink.count()) {
          await deepLink.click();
          if (!await page.locator('#probabilita').isVisible()) failures.push({file,width,theme,type:'closed-deep-link'});
        }
      }
      const a11y = await new AxeBuilder({page}).withTags(['wcag2a','wcag2aa','wcag21aa']).analyze();
      for (const v of a11y.violations) failures.push({file,width,theme,type:'accessibility',rule:v.id,
        impact:v.impact,nodes:v.nodes.map(n=>({target:n.target,summary:n.failureSummary}))});
      // Toggle funzionante e coerente con aria-pressed, poi ripristino del tema.
      const original = await page.locator('html').getAttribute('data-theme');
      await page.locator('#themeToggle').click();
      const changed = await page.locator('html').getAttribute('data-theme');
      if (changed === original) failures.push({file,width,theme,type:'theme-toggle'});
      await page.locator('#themeToggle').click();
      if (file === 'accuratezza.html') {
        const link = page.locator('main a[href="laboratorio.html"]');
        if (!await link.isVisible()) failures.push({file,width,theme,type:'laboratory-link'});
      }
      if (width === 375 && ['index.html','accuratezza.html',pages[7]].includes(file))
        await page.screenshot({path:join(output,`${file.replaceAll('/','-')}-${theme}.png`),fullPage:false});
      checks.push({file,width,theme,geometry,axePasses:a11y.passes.length});
      console.log(`${width} ${theme} ${file}: verificata`);
    }
    await context.close();
  }
} catch (err) {
  failures.push({type:'harness',message:err.message});
} finally {
  await browser?.close();
  await new Promise(r=>server.close(r));
}
await writeFile(join(output,'report.json'),JSON.stringify({pages,checks,failures},null,2));
console.log(`${checks.length} visite (${pages.length} pagine × 2 viewport × 2 temi), ${failures.length} problemi`);
if (failures.length) { console.log(JSON.stringify(failures.slice(0,6),null,2)); process.exitCode=1; }
