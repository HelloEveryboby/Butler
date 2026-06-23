const { chromium } = require('playwright');
const path = require('path');

(async () => {
  const browser = await chromium.launch();
  const context = await browser.newContext({
    viewport: { width: 390, height: 844 }, // iPhone 12/13/14 size
    isMobile: true,
    hasTouch: true,
  });
  const page = await context.newPage();

  // Load the index.html from assets
  const filePath = 'file://' + path.resolve('frontend/index.html');
  await page.goto(filePath);

  // Wait for any animations
  await page.waitForTimeout(2000);

  // Take a screenshot of the mobile UI
  await page.screenshot({ path: 'mobile_ui_main.png' });

  // Simulate a scroll/swipe to another quadrant if possible
  // In matrix.js, navigation might be via touch or specific functions
  await page.evaluate(() => {
    if (window.MatrixNavigation) {
        window.MatrixNavigation.scrollTo(1, 1);
    }
  });
  await page.waitForTimeout(1000);
  await page.screenshot({ path: 'mobile_ui_skills.png' });

  await browser.close();
})();
