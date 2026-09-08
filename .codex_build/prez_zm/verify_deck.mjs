import fs from "node:fs/promises";
import path from "node:path";
import { FileBlob, PresentationFile } from "@oai/artifact-tool";

const workspaceDir = "C:/Users/deniss.boka/MESLI_PROJECT/KIRI";
const finalPath = path.join(workspaceDir, "outputs", "zm_prez_20260909", "PREZ_ZM_KIRI_2026-09-09.pptx");
const outDir = path.join(workspaceDir, ".codex_build", "prez_zm", "final_render");
await fs.mkdir(outDir, { recursive: true });

const presentation = await PresentationFile.importPptx(await FileBlob.load(finalPath));
const snapshot = await presentation.inspect({
  kind: "presentation,slide,textbox,shape,image,table,chart,notes",
  maxChars: 24000,
});
await fs.writeFile(path.join(outDir, "final_snapshot.ndjson"), snapshot.ndjson, "utf8");

for (let i = 0; i < presentation.slides.items.length; i += 1) {
  const slide = presentation.slides.items[i];
  const png = await slide.export({ format: "png", scale: 1 });
  await fs.writeFile(path.join(outDir, `slide_${String(i + 1).padStart(2, "0")}.png`), new Uint8Array(await png.arrayBuffer()));
}

const montage = await presentation.export({ format: "webp", montage: true, scale: 1 });
await fs.writeFile(path.join(outDir, "montage.webp"), new Uint8Array(await montage.arrayBuffer()));

console.log(JSON.stringify({
  slides: presentation.slides.items.length,
  snapshot: path.join(outDir, "final_snapshot.ndjson"),
  montage: path.join(outDir, "montage.webp"),
}, null, 2));
