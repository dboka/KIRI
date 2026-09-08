import fs from "node:fs/promises";
import { FileBlob, PresentationFile } from "@oai/artifact-tool";

const sourcePath = "C:/Users/deniss.boka/MESLI_PROJECT/KIRI/PREZ.pptm";
const outDir = "C:/Users/deniss.boka/MESLI_PROJECT/KIRI/.codex_build/prez_zm";

const presentation = await PresentationFile.importPptx(await FileBlob.load(sourcePath));
const snapshot = await presentation.inspect({
  kind: "presentation,slide,textbox,shape,image,table,chart,notes,layout",
  maxChars: 16000,
});
await fs.writeFile(`${outDir}/deck_snapshot.ndjson`, snapshot.ndjson, "utf8");

for (let i = 0; i < presentation.slides.items.length; i += 1) {
  const slide = presentation.slides.items[i];
  const png = await slide.export({ format: "png", scale: 1 });
  await fs.writeFile(`${outDir}/source_slide_${String(i + 1).padStart(2, "0")}.png`, new Uint8Array(await png.arrayBuffer()));
}

console.log(snapshot.ndjson.slice(0, 4000));
