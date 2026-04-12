/**
 * HTML to PNG screenshot script using Playwright
 * 
 * Usage: node screenshot.mjs input.html output.png
 */

import { chromium } from 'playwright';
import { resolve } from 'path';

async function screenshot(inputPath, outputPath) {
  const browser = await chromium.launch({
    args: ['--force-device-scale-factor=1']
  });
  const context = await browser.newContext({
    viewport: { width: 820, height: 2000 },  // 高度设大，让内容自然展开
    deviceScaleFactor: 1,
    isMobile: false,
    hasTouch: false
  });
  const page = await context.newPage();
  
  // Resolve absolute path for input
  const absoluteInput = inputPath.startsWith('/') ? inputPath : resolve(process.cwd(), inputPath);
  const absoluteOutput = outputPath.startsWith('/') ? outputPath : resolve(process.cwd(), outputPath);
  
  await page.goto(`file://${absoluteInput}`);
  
  // Wait for fonts to load
  await page.waitForTimeout(2000);
  
  // 获取页面实际高度（使用 body.scrollHeight 包含水印区域）
  const height = await page.evaluate(() => document.body.scrollHeight);
  
  // Take screenshot with clip to force 820px width
  await page.screenshot({
    path: absoluteOutput,
    clip: { x: 0, y: 0, width: 820, height: height }
  });
  
  await browser.close();
  console.log(`Screenshot saved: ${absoluteOutput}`);
}

// Parse args
const args = process.argv.slice(2);
if (args.length < 2) {
  console.log('Usage: node screenshot.mjs input.html output.png');
  process.exit(1);
}

screenshot(args[0], args[1]);