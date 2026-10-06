// Run with: npm test
import { test } from "node:test";
import assert from "node:assert/strict";
import { buildMusicGenPrompt } from "../src/melody.js";
import { pickDrums } from "../src/drums.js";

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

test("reference songs add a 'follow the reference' instruction", () => {
  const p = buildMusicGenPrompt({ genre: "House", reference_id: "a".repeat(64) });
  assert.ok(p.includes("following the melody, groove and feel of the reference track"));
  assert.ok(!buildMusicGenPrompt({ genre: "House" }).includes("reference track"));
});

test("no_drums asks MusicGen to leave room for copied drums", () => {
  assert.ok(buildMusicGenPrompt({ genre: "Trap", no_drums: true }).includes("no drums, no percussion"));
});

test("pickDrums finds the drums stem in every output shape", () => {
  const u = "https://x/drums.wav";
  assert.equal(pickDrums(u), u);
  assert.equal(pickDrums(["https://x/no_drums.wav", u, "https://x/bass.wav"]), u);
  assert.equal(pickDrums({ drums: u, no_drums: "https://x/no_drums.wav" }), u);
  assert.equal(pickDrums({ Drums_stem: u }), u);
  assert.equal(pickDrums(null), undefined);
});
