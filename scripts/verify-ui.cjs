// Optional smoke check: npm install --no-save playwright, then node scripts/verify-ui.cjs.
// On machines without Playwright browsers set BROWSER_EXECUTABLE to a Chromium executable.
const { chromium } = require('playwright');
const fs = require('node:fs');
const path = require('node:path');
(async () => {
  const browser = await chromium.launch({ headless: true, ...(process.env.BROWSER_EXECUTABLE ? { executablePath: process.env.BROWSER_EXECUTABLE } : {}) });
  try {
    const context = await browser.newContext({ viewport: { width: 1440, height: 960 } });
    const page = await context.newPage();
    const errors = [];
    page.on('pageerror', error => errors.push(error.message));
    await page.goto(process.env.APP_URL || 'http://localhost:5173');
    await page.getByRole('heading', { name: '欢迎回来' }).waitFor();
    await page.getByRole('button', { name: '开始使用' }).click();
    await page.getByRole('heading', { name: '你的订单，我们一起看。' }).waitFor();
    const screenshots = path.resolve(__dirname, '../docs/screenshots');
    fs.mkdirSync(screenshots, { recursive: true });
    await page.screenshot({ path: path.join(screenshots, 'welcome.png'), fullPage: true });
    await page.getByRole('button', { name: /让数据，讲清楚故事/ }).click();
    await page.locator('canvas').waitFor();
    await page.getByRole('button', { name: '开启新对话' }).waitFor({ state: 'visible' });
    await page.waitForFunction(() => !document.querySelector('.new-chat').disabled);
    if (await page.locator('.composer-error').count()) throw new Error(await page.locator('.composer-error').innerText());
    const headers = await page.locator('th').allTextContents();
    if (!headers.includes('金额')) throw new Error('Chart query table missing amount column');
    await page.getByLabel('图表类型').selectOption('line');
    await page.screenshot({ path: path.join(screenshots, 'chart.png'), fullPage: true });
    const cid = await page.locator('.history-list .selected').innerText();
    await page.reload();
    await page.getByRole('heading', { name: '你的订单，我们一起看。' }).waitFor();
    await page.getByRole('button', { name: cid.trim(), exact: true }).click();
    await page.locator('canvas').waitFor();
    await page.getByLabel('输入你的问题').fill('改成饼图');
    await page.getByRole('button', { name: '发送消息' }).click();
    await page.waitForFunction(() => !document.querySelector('.new-chat').disabled && document.querySelectorAll('.chart-host canvas').length === 2);
    if (await page.locator('.composer-error').count()) throw new Error(await page.locator('.composer-error').innerText());
    await page.getByRole('button', { name: '开启新对话' }).click();
    await page.getByRole('button', { name: /售后问题，轻松解决/ }).click();
    await page.locator('.source-tag').first().waitFor();
    await page.waitForFunction(() => !document.querySelector('.new-chat').disabled);
    if (!(await page.locator('.message-text').last().innerText()).includes('7 天')) throw new Error('Policy answer missing evidence');
    await page.setViewportSize({ width: 390, height: 844 });
    await page.getByRole('button', { name: '打开菜单' }).click();
    await page.getByRole('button', { name: '开启新对话' }).click();
    await page.screenshot({ path: path.join(screenshots, 'mobile.png'), fullPage: true });
    if (await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth)) throw new Error('Mobile horizontal overflow');
    if (errors.length) throw new Error(errors.join('\n'));
    console.log('UI smoke check passed: login, chart, history restore, follow-up, RAG, mobile.');
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exit(1); });
