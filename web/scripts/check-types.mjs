// Fails when src/api/types.gen.ts is not what openapi-typescript generates from openapi.json
// (SPEC §16.5: never hand-edit generated types). Run by `npm run check`.
import { execFileSync } from "node:child_process";
import { mkdtempSync, readFileSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

const dir = mkdtempSync(join(tmpdir(), "kd-types-"));
const out = join(dir, "types.gen.ts");
try {
  execFileSync("npx", ["openapi-typescript", "openapi.json", "-o", out], { stdio: "pipe" });
  execFileSync("npx", ["prettier", "--write", out], { stdio: "pipe" });
  const want = readFileSync(out, "utf8");
  const have = readFileSync("src/api/types.gen.ts", "utf8");
  if (want !== have) {
    console.error("src/api/types.gen.ts is stale: run `npm run gen:types`.");
    process.exit(1);
  }
  console.log("src/api/types.gen.ts is current.");
} finally {
  rmSync(dir, { recursive: true, force: true });
}
