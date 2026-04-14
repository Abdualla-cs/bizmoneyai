import { rm } from "node:fs/promises";
import { join } from "node:path";
import { spawn } from "node:child_process";

const projectRoot = process.cwd();
const distDirName = ".next-typecheck";
const distDirPath = join(projectRoot, distDirName);

const child = spawn("npx next build", {
  cwd: projectRoot,
  env: {
    ...process.env,
    NEXT_DIST_DIR: distDirName,
  },
  shell: true,
  stdio: "inherit",
});

child.on("exit", async (code) => {
  try {
    await rm(distDirPath, { recursive: true, force: true });
  } finally {
    process.exit(code ?? 1);
  }
});
