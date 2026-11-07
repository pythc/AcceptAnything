// Live platform UI checks. Does not start acceptance jobs or change target repos.
const { chromium } = require('playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

(async () => {
  const out = path.resolve('docs/design/d043');
  const browser = await chromium.launch({ headless: true, ...(process.env.CHROMIUM_EXECUTABLE ? { executablePath: process.env.CHROMIUM_EXECUTABLE } : {}) });
  const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
  page.setDefaultTimeout(15000);
  const errors = [], requests = [], results = { browser: browser.version(), checks: [] };
  page.on('pageerror', e => errors.push(e.message));
  page.on('request', r => requests.push(r.url()));
  const record = 'int-fe2b255558a6465f';
  try {
    await page.goto(`http://127.0.0.1:18890/?view=records&run=${record}`);
    await page.waitForLoadState('networkidle');
    await page.waitForFunction(() => document.querySelectorAll('.catalogue-row').length === 50);
    assert.equal(requests.filter(url => /\/api\/runs\/[^/]+(?:\?|$)/.test(url)).length, 0, 'catalogue must not silently verify the selected run');
    results.checks.push('目录不触发隐藏的完整核验');
    const response = await page.request.get('http://127.0.0.1:18890/api/catalogue?limit=500');
    const all = await response.json(); assert(all.total > 100);
    const old = all.runs.findLast(r => !r.record_error).id;
    while (await page.getByRole('button', { name: '加载更多', exact: true }).count()) {
      const count = await page.locator('.catalogue-row').count();
      await page.getByRole('button', { name: '加载更多', exact: true }).click();
      await page.waitForFunction(n => document.querySelectorAll('.catalogue-row').length > n, count);
    }
    assert.equal(await page.locator('.catalogue-row').count(), all.total);
    results.checks.push(`分页访问全部 ${all.total} 条记录`);
    await page.getByRole('textbox', { name: '搜索验收记录' }).fill(old);
    await page.waitForFunction(() => document.querySelectorAll('.catalogue-row').length === 1);
    assert((await page.locator('.catalogue-row').innerText()).includes(old));
    results.checks.push('服务端搜索到首页以外的旧记录');
    await page.getByRole('textbox', { name: '搜索验收记录' }).fill(record);
    await page.waitForFunction(id => document.querySelector('.catalogue-row')?.textContent.includes(id), record);
    await page.locator('.catalogue-row').click({ position: { x: 20, y: 25 } });
    await page.waitForFunction(id => document.querySelector('.catalogue-detail')?.textContent.includes(id), record);
    assert((await page.locator('.catalogue-detail').innerText()).includes('打开详情时重新核验'));
    assert((await page.locator('.catalogue-detail').innerText()).includes('当时无法下结论'));
    await page.screenshot({ path: path.join(out, 'records.png'), fullPage: true });
    results.checks.push('历史判定与原件核验状态分别显示');
    await page.getByRole('button', { name: '代码仓库', exact: true }).click();
    await page.waitForLoadState('networkidle');
    const repositoryRow = page.locator('.catalogue-row').first();
    await repositoryRow.click();
    await page.locator('.repository-tabs').getByRole('button', { name: /^验收记录/ }).click();
    await page.waitForFunction(() => document.querySelectorAll('.repository-runs .repo-recent').length > 0);
    const repoCount = Number((await page.locator('.catalogue-row[aria-pressed="true"]').innerText()).match(/(\d+) 次验收/)[1]);
    while (await page.getByRole('button', { name: '更多验收记录' }).count()) {
      const count=await page.locator('.repository-runs .repo-recent').count();
      await page.getByRole('button', { name: '更多验收记录' }).click();
      await page.waitForFunction(n => document.querySelectorAll('.repository-runs .repo-recent').length > n, count);
    }
    assert.equal(await page.locator('.repository-runs .repo-recent').count(), repoCount);
    await page.screenshot({ path: path.join(out, 'repositories.png'), fullPage: true });
    results.checks.push('仓库历史数量与筛选后全部记录一致');
    await page.setViewportSize({ width: 900, height: 900 });
    await page.screenshot({ path: path.join(out, 'repositories-900.png'), fullPage: true });
    assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1));
    results.checks.push('900px 窗口无横向页面溢出');
    await page.setViewportSize({ width: 1440, height: 1000 });
    const runResponse = page.waitForResponse(r => r.url().includes(`/api/runs/${record}?`), { timeout: 180000 });
    await page.goto(`http://127.0.0.1:18890/?run=${record}&tab=flow`);
    const frozenRun = await (await runResponse).json();
    assert.equal(frozenRun.id, record);
    assert.equal(frozenRun.decision, 'inconclusive');
    await page.waitForLoadState('networkidle', { timeout: 180000 });
    assert.match(await page.locator('.focus-verdict').innerText(), /验收未完成|验收结论待确认/);
    await page.screenshot({ path: path.join(out, 'flow.png'), fullPage: false });
    await page.getByRole('tab', { name: '缺陷详情' }).click();
    await page.screenshot({ path: path.join(out, 'findings.png'), fullPage: false });
    const artifactResponse = page.waitForResponse(r => /\/api\/runs\/[^/]+\/artifacts\//.test(r.url()));
    await page.getByRole('tab', { name: '证据溯源' }).click();
    assert.equal((await artifactResponse).status(), 200);
    await page.getByText('读取并校验证据…', { exact: true }).waitFor({ state: 'hidden' });
    const contract = page.getByRole('link', { name: '核验结果 JSON', exact: true });
    assert.equal(await contract.getAttribute('href'), `/api/runs/${record}/result-contract`);
    const verified = await page.request.get(`http://127.0.0.1:18890/api/runs/${record}/result-contract`);
    assert.equal(verified.status(), 200);
    const result = await verified.json();
    assert.equal(result.provenance.evidence_verified_now, true);
    assert.equal(result.gate.decision, 'inconclusive');
    await page.screenshot({ path: path.join(out, 'evidence.png'), fullPage: false });
    results.checks.push('三个详情 Tab 保留真实数据、原件与结果契约入口');
    assert.deepEqual(errors, []);
    results.errors=errors;results.requests=requests.filter(url => url.includes('/api/'));
    fs.writeFileSync(path.join(out, 'browser-verification.json'), JSON.stringify(results, null, 2));
    console.log(JSON.stringify(results, null, 2));
  } finally { await browser.close(); }
})().catch(e => { console.error(e); process.exitCode = 1; });
