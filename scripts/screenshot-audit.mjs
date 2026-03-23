import { chromium } from 'playwright';
import { fileURLToPath } from 'url';
import path from 'path';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const SCREENSHOT_DIR = path.join(__dirname, '..', 'screenshots');
const URL = 'http://localhost:8787';

async function main() {
  const browser = await chromium.launch();

  const viewports = [
    { name: 'mobile-375', width: 375, height: 812 },   // iPhone SE/X
    { name: 'mobile-414', width: 414, height: 896 },   // iPhone Plus
    { name: 'tablet-768', width: 768, height: 1024 },  // iPad
    { name: 'desktop-1200', width: 1200, height: 900 }, // Desktop
  ];

  for (const vp of viewports) {
    const context = await browser.newContext({
      viewport: { width: vp.width, height: vp.height },
    });
    const page = await context.newPage();

    // 1. Initial load
    await page.goto(URL, { waitUntil: 'networkidle' });
    await page.waitForTimeout(1000);
    await page.screenshot({ path: path.join(SCREENSHOT_DIR, `${vp.name}-01-initial.png`), fullPage: true });

    // 2. Select 24h distance filter
    await page.selectOption('#filterDistance', '24h');
    await page.waitForTimeout(500);
    await page.screenshot({ path: path.join(SCREENSHOT_DIR, `${vp.name}-02-filtered-24h.png`), fullPage: true });

    // 3. Click "Top 5 All-Time" quick pick
    const quickPicks = await page.$$('.quick-pick-btn');
    if (quickPicks.length > 0) {
      await quickPicks[0].click();
      await page.waitForTimeout(500);
    }
    await page.screenshot({ path: path.join(SCREENSHOT_DIR, `${vp.name}-03-top5-selected.png`), fullPage: true });

    // 4. Switch to Selected view
    await page.click('#pillSelected');
    await page.waitForTimeout(300);
    await page.screenshot({ path: path.join(SCREENSHOT_DIR, `${vp.name}-04-cart-view.png`), fullPage: true });

    // 5. Scroll to viz area
    const vizArea = await page.$('#vizArea');
    if (vizArea) {
      await vizArea.scrollIntoViewIfNeeded();
      await page.waitForTimeout(1000);
      await page.screenshot({ path: path.join(SCREENSHOT_DIR, `${vp.name}-05-projection.png`), fullPage: true });
    }

    // 6. Search interaction
    await page.click('#pillBrowse');
    await page.waitForTimeout(200);
    await page.fill('#searchInput', 'Sorokin');
    await page.waitForTimeout(500);
    await page.screenshot({ path: path.join(SCREENSHOT_DIR, `${vp.name}-06-search.png`), fullPage: true });

    await context.close();
  }

  await browser.close();
  console.log('Screenshots saved to', SCREENSHOT_DIR);
}

main().catch(console.error);
