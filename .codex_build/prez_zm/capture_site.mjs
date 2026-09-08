import { chromium } from "playwright";

const outDir = "C:/Users/deniss.boka/MESLI_PROJECT/KIRI/.codex_build/prez_zm";
const browser = await chromium.launch({
  headless: true,
  executablePath: "C:/Program Files/Google/Chrome/Application/chrome.exe",
});
const page = await browser.newPage({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 1 });
await page.goto("http://127.0.0.1:8765/", { waitUntil: "networkidle" });
await page.waitForFunction(() => {
  const overlay = document.querySelector("#bootOverlay");
  return overlay && overlay.classList.contains("is-complete");
}, { timeout: 30000 });
await page.waitForTimeout(1200);
await page.screenshot({ path: `${outDir}/kiri_overview_calendar.png`, fullPage: true });

await page.click("#calendarToggle");
await page.waitForTimeout(300);
await page.screenshot({ path: `${outDir}/kiri_overview_clean.png`, fullPage: true });

const paths = await page.locator("path.leaflet-interactive").elementHandles();
let clicked = false;
for (const pathEl of paths) {
  const box = await pathEl.boundingBox();
  if (box && box.width > 20 && box.height > 20 && box.x > 120 && box.y > 140) {
    await page.mouse.click(box.x + box.width / 2, box.y + box.height / 2);
    clicked = true;
    break;
  }
}
if (!clicked) {
  await page.mouse.click(720, 450);
}

await page.waitForSelector("#detailPanel:not([hidden])", { timeout: 30000 });
await page.waitForTimeout(1600);
await page.screenshot({ path: `${outDir}/kiri_detail_grid.png`, fullPage: true });

await page.mouse.click(620, 455);
await page.waitForTimeout(800);
await page.screenshot({ path: `${outDir}/kiri_detail_cell.png`, fullPage: true });

await browser.close();
console.log(JSON.stringify({
  screenshots: [
    `${outDir}/kiri_overview_calendar.png`,
    `${outDir}/kiri_overview_clean.png`,
    `${outDir}/kiri_detail_grid.png`,
    `${outDir}/kiri_detail_cell.png`
  ]
}, null, 2));
