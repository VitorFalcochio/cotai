import { mkdir, writeFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const projectRoot = path.resolve(__dirname, "..");
const outputPath = path.join(projectRoot, "frontend", "assets", "js", "runtime-config.js");

const runtimeConfig = {
  API_BASE_URL: process.env.COTAI_API_BASE_URL || "",
  SUPABASE_URL: process.env.COTAI_SUPABASE_URL || "",
  SUPABASE_ANON_KEY: process.env.COTAI_SUPABASE_ANON_KEY || "",
  WHATSAPP_NUMBER: process.env.COTAI_WHATSAPP_NUMBER || "",
};

const fileContents = `export const RUNTIME_CONFIG = ${JSON.stringify(runtimeConfig, null, 2)};\n`;

await mkdir(path.dirname(outputPath), { recursive: true });
await writeFile(outputPath, fileContents, "utf8");

console.log(`Runtime config written to ${outputPath}`);
