// Encodes the recorder's frames (demo/record.spec.ts) into the demo video (D-168). Each frame was
// captured in slow motion with its wall-clock time; dividing by the slow-motion factor gives its
// time in the video, so motion plays back at the app's real pace at a steady 30 fps.
//   node demo/encode.mjs [out.mp4]      (from web/; make demo-video runs it)
import { spawnSync } from "node:child_process";
import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { dirname, resolve } from "node:path";

const FRAMES = resolve("../data/cache/demo/frames");
const OUT = resolve(process.argv[2] ?? "../docs/demo/kairos-defense-demo.mp4");
const m = JSON.parse(readFileSync(`${FRAMES}/manifest.json`, "utf8"));
const mark = (name, fallback) => m.marks.find((x) => x.name === name)?.t ?? fallback;
const start = mark("start", m.t0);
const end = mark("end", m.t1);
const k = m.k;

// the frame on screen at `start` opens the video; every later frame until `end` follows
const before = m.frames.filter((f) => f.t <= start).at(-1);
const frames = [
  ...(before ? [{ ...before, t: start }] : []),
  ...m.frames.filter((f) => f.t > start && f.t < end),
];
if (frames.length < 2) throw new Error("no frames between the start and end marks");
const lines = ["ffconcat version 1.0"];
frames.forEach((f, i) => {
  const next = i + 1 < frames.length ? frames[i + 1].t : end;
  lines.push(`file '${f.file}'`, `duration ${Math.max(0.0005, (next - f.t) / k).toFixed(6)}`);
});
lines.push(`file '${frames.at(-1).file}'`);
writeFileSync(`${FRAMES}/list.ffconcat`, lines.join("\n") + "\n");

const seconds = (end - start) / k;
mkdirSync(dirname(OUT), { recursive: true });
const vf = [
  "fps=30",
  "fade=t=in:st=0:d=0.5",
  `fade=t=out:st=${(seconds - 0.8).toFixed(3)}:d=0.8`,
  "format=yuv420p",
].join(",");
const args = ["-y", "-hide_banner", "-loglevel", "error", "-f", "concat", "-safe", "0"];
args.push("-i", `${FRAMES}/list.ffconcat`, "-vf", vf, "-c:v", "libx264", "-preset", "slow");
args.push("-crf", process.env.DEMO_CRF ?? "20", "-profile:v", "high", "-movflags", "+faststart");
args.push("-an", OUT);
const r = spawnSync("ffmpeg", args, { stdio: "inherit" });
if (r.status !== 0) throw new Error(`ffmpeg exited ${r.status}`);

// the chapter marks in video time, for the docs and the review
const chapters = m.marks.map((x) => ({ name: x.name, at_s: +((x.t - start) / k).toFixed(2) }));
writeFileSync(OUT.replace(/\.mp4$/, ".chapters.json"), JSON.stringify(chapters, null, 1) + "\n");
const wall = (m.frames.at(-1).t - m.frames[0].t) / m.frames.length;
console.log(
  `wrote ${OUT}: ${seconds.toFixed(1)} s from ${frames.length} frames ` +
    `(captured every ${(wall * 1000).toFixed(0)} ms of wall time, slow motion ×${k}: ` +
    `${(k / wall).toFixed(1)} frames per video second)`,
);
