// MapLibre draws the map in a Web Worker loaded from its own file. The bundler doesn't
// emit that file, so serve the installed version from /public (see campus-map.tsx).
import { copyFileSync, mkdirSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
mkdirSync(join(root, "public"), { recursive: true });
copyFileSync(
  join(root, "node_modules", "maplibre-gl", "dist", "maplibre-gl-worker.mjs"),
  join(root, "public", "maplibre-gl-worker.mjs"),
);
console.log("Copied maplibre-gl-worker.mjs to public/");
