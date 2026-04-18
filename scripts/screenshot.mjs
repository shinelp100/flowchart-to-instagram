/**
 * HTML to PNG screenshot script using Playwright
 * 
 * Usage: node screenshot.mjs input.html output.png [width]
 */

import { chromium } from 'playwright';
import { resolve } from 'path';

async function screenshot(inputPath, outputPath, customWidth = 820) {
  const minWidth = parseInt(customWidth) || 820;
  const browser = await chromium.launch({
    args: ['--force-device-scale-factor=1']
  });
  // 初始 viewport，加载后会根据内容调整
  const context = await browser.newContext({
    viewport: { width: minWidth, height: 2000 },
    deviceScaleFactor: 1,
    isMobile: false,
    hasTouch: false
  });
  const page = await context.newPage();
  
  const absoluteInput = inputPath.startsWith('/') ? inputPath : resolve(process.cwd(), inputPath);
  const absoluteOutput = outputPath.startsWith('/') ? outputPath : resolve(process.cwd(), outputPath);
  
  // 使用 domcontentloaded 等待 DOM 解析完成
  await page.goto(`file://${absoluteInput}`, { waitUntil: 'domcontentloaded', timeout: 30000 });
  
  // 等待字体和样式加载
  await page.waitForTimeout(2000);
  
  // 确保内容元素存在
  await page.waitForSelector('#content', { timeout: 5000 }).catch(() => null);
  
  const dimensions = await page.evaluate(() => {
    const content = document.getElementById('content');
    if (content) {
      return {
        width: Math.min(2400, Math.max(content.scrollWidth, document.body.scrollWidth)),
        height: Math.max(content.scrollHeight, document.body.scrollHeight)
      };
    }
    return {
      width: Math.min(2400, document.body.scrollWidth),
      height: document.body.scrollHeight
    };
  });
  
  // 调整 viewport 到实际内容大小
  const finalWidth = Math.max(minWidth, dimensions.width);
  const finalHeight = dimensions.height + 20;
  
  await page.setViewportSize({ width: finalWidth, height: finalHeight });
  
  console.log(`Content: ${dimensions.width}x${dimensions.height}`);
  console.log(`Screenshot: ${finalWidth}x${finalHeight}`);
  
  await page.screenshot({
    path: absoluteOutput,
    clip: { x: 0, y: 0, width: finalWidth, height: finalHeight },
    animations: 'disabled'  // 禁用动画以加速截图
  });
  
  await browser.close();
  console.log(`Saved: ${absoluteOutput}`);
}

const args = process.argv.slice(2);
if (args.length < 2) {
  console.log('Usage: node screenshot.mjs input.html output.png [width]');
  process.exit(1);
}

screenshot(args[0], args[1], args[2]);
