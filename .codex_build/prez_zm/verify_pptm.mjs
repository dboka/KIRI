import fs from "node:fs/promises";
import path from "node:path";
import { FileBlob, PresentationFile } from "@oai/artifact-tool";

const workspaceDir = "C:/Users/deniss.boka/MESLI_PROJECT/KIRI";
const sourcePath = path.join(workspaceDir, "PREZ.pptm");
const outDir = path.join(workspaceDir, ".codex_build", "prez_zm", "pptm_verify");
await fs.mkdir(outDir, { recursive: true });

const presentation = await PresentationFile.importPptx(await FileBlob.load(sourcePath));
const snapshot = await presentation.inspect({ kind: "slide,notes,table,chart", maxChars: 8000 });
await fs.writeFile(path.join(outDir, "pptm_snapshot.ndjson"), snapshot.ndjson, "utf8");
const png = await presentation.slides.items[0].export({ format: "png", scale: 1 });
await fs.writeFile(path.join(outDir, "slide_01.png"), new Uint8Array(await png.arrayBuffer()));
console.log(JSON.stringify({ slides: presentation.slides.items.length, preview: path.join(outDir, "slide_01.png") }, null, 2));
