// Run with: npm test
import { test } from "node:test";
import assert from "node:assert/strict";
import { buildMusicGenPrompt } from "../src/melody.js";

test("prompt includes every selection and forces instrumental", () => {
  const p = buildMusicGenPrompt({
    genre: "Lo-fi Hip Hop", mood: "Dreamy", instrument: ["Rhodes Piano", "Upright Bass"],
    style: "dusty vinyl crackle", reference: "rainy late night", bpm: 82, key: "F minor",
  });
  for (const s of ["Lo-fi Hip Hop instrumental", "Dreamy mood", "Rhodes Piano, Upright Bass",
    "dusty vinyl crackle", "rainy late night", "82 bpm", "F minor", "no vocals"]) {
    assert.ok(p.includes(s), `missing: ${s}\n${p}`);
  }
});

test("bad bpm is ignored and empty input still works", () => {
  const p = buildMusicGenPrompt({ bpm: 9999 });
  assert.ok(!p.includes("bpm"));
  assert.ok(p.includes("instrumental only"));
});
