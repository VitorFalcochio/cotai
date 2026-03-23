import { cp, mkdir, readdir, readFile, rm, writeFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const projectRoot = path.resolve(__dirname, "..");
const frontendRoot = path.join(projectRoot, "frontend");
const pagesDir = path.join(frontendRoot, "pages");
const assetsDir = path.join(frontendRoot, "assets");
const outputDir = path.join(projectRoot, "frontend-dist");
const rootArtifacts = ["manifest.webmanifest", "sw.js"];

await rm(outputDir, { recursive: true, force: true });
await mkdir(outputDir, { recursive: true });
await cp(assetsDir, path.join(outputDir, "assets"), { recursive: true });
for (const fileName of rootArtifacts) {
  await cp(path.join(frontendRoot, fileName), path.join(outputDir, fileName));
}

const pageFiles = (await readdir(pagesDir)).filter((file) => file.endsWith(".html"));

for (const fileName of pageFiles) {
  const sourcePath = path.join(pagesDir, fileName);
  const destinationPath = path.join(outputDir, fileName);
  const rawHtml = await readFile(sourcePath, "utf8");
  const builtHtml = rawHtml.replaceAll("../assets/", "./assets/");
  await writeFile(destinationPath, builtHtml, "utf8");
}

console.log(`Frontend dist built at ${outputDir}`);
