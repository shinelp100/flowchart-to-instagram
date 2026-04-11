/**
 * HTML to PNG screenshot script using Playwright
 * 
 * Usage: node screenshot.mjs input.html output.png
 */

import { chromium } from 'playwright';
import { resolve } from 'path';

async function screenshot(inputPath, outputPath) {
  const browser = await chromium.launch();
  const page = await browser.newPage({
    viewport: { width: 820, height: 1200 }
  });
  
  // Resolve absolute path for input
  const absoluteInput = inputPath.startsWith('/') ? inputPath : resolve(process.cwd(), inputPath);
  const absoluteOutput = outputPath.startsWith('/') ? outputPath : resolve(process.cwd(), outputPath);
  
  await page.goto(`file://${absoluteInput}`);
  
  // Wait for fonts to load
  await page.waitForTimeout(2000);
  
  // Take full page screenshot
  await page.screenshot({
    path: absoluteOutput,
    fullPage: true
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