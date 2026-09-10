// Regression: marking whitespace between table cells created anonymous cells.
// Requires Playwright in Node's module search path and an installed Chrome.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { execFileSync } = require('node:child_process');
const { chromium } = require('playwright');
const repo = path.resolve(__dirname, '../..');
const temporary = fs.mkdtempSync(path.join(os.tmpdir(), 'visual-highlights-'));

async function inspect(page) {
  return page.locator('main table').evaluate(table => ({
    text: table.textContent,
    invalid: table.querySelectorAll('table > mark, thead > mark, tbody > mark, tfoot > mark, tr > mark, colgroup > mark').length,
    rows: [...table.rows].map(row => [...row.cells].map(cell => ({x: cell.getBoundingClientRect().x, y: cell.getBoundingClientRect().y}))),
    highlighted: [...table.querySelectorAll('mark')].map(mark => mark.textContent).join(''),
    formatted: table.querySelector('strong').textContent,
  }));
}

function assertAligned(result, text) {
  assert.equal(result.text, text, 'highlighting must preserve all table text');
  assert.equal(result.invalid, 0, 'highlights must not become structural table children');
  for (const row of result.rows) {
    assert.equal(row.length, 2);
    assert.equal(row[0].y, row[1].y, 'cells in each row remain on the same line');
    assert.ok(Math.abs(row[0].x - result.rows[0][0].x) < 1);
    assert.ok(Math.abs(row[1].x - result.rows[0][1].x) < 1);
  }
  assert.equal(result.formatted, 'local work');
}

async function verify(page, html) {
  await page.setContent(html);
  const baseline = await inspect(page);
  const quotes = [baseline.text.trim(), 'Background local work Silent command Finalization Save results'];
  const threads = quotes.map((quote, index) => ({id: `t${index}`, state: 'anchored', is_open: true, comments: [], anchor: {block_index: 0, quote}}));
  const seeded = html.replace(/(<script type="application\/json" id="vr-bootstrap">)[\s\S]*?(<\/script>)/,
    (_, start, end) => start + JSON.stringify({document_id: 'report-highlight-regression', revision: 1, threads}) + end);
  await page.setContent(seeded);
  let result = await inspect(page);
  assertAligned(result, baseline.text);
  assert.ok(result.highlighted.includes('Finalization'), 'cross-row quote remains highlighted');
  for (let index = 0; index < 3; index++) {
    for (const filter of ['resolved', 'all', 'open']) {
      await page.locator(`[data-filter="${filter}"]`).evaluate(button => button.click());
      result = await inspect(page);
      assertAligned(result, baseline.text);
    }
  }
}

(async () => {
  let browser;
  try {
    const source = path.join(temporary, 'source.md');
    fs.writeFileSync(source, '---\ntitle: Highlight regression\neyebrow: Test\nsubtitle: Table annotations\nslug: highlight-regression\ndate: 2026-09-10\nfolder: personal/tooling\n---\n\n| Reason | Activity |\n|---|---|\n| Background **local work** | Silent `command` |\n| Finalization | Save results |\n');
    execFileSync(path.join(repo, 'bin/visual-report'), ['render', source, '--kind', 'report', '--no-index'], {env: {...process.env, VISUAL_REPORT_ARCHIVE: temporary}});
    const html = fs.readFileSync(path.join(temporary, 'report-highlight-regression-2026-09-10.html'), 'utf8');
    browser = await chromium.launch({headless: true, channel: 'chrome'});
    for (const width of [1440, 390]) {
      const page = await browser.newPage({viewport: {width, height: 900}});
      await page.route('https://visual.test/**', route => route.fulfill({status: route.request().isNavigationRequest() ? 200 : 404, contentType: 'text/html', body: '<html></html>'}));
      await page.goto('https://visual.test/');
      const errors = [];
      page.on('pageerror', error => errors.push(error.message));
      await verify(page, html);
      assert.deepEqual(errors, []);
      await page.close();
    }
    console.log('Table annotations preserve layout and text across overlapping quotes and filter cycles.');
  } finally {
    if (browser) await browser.close();
    fs.rmSync(temporary, {recursive: true, force: true});
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
