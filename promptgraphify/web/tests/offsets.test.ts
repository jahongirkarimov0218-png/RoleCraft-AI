import { describe, expect, it } from "vitest";
import { buildOffsetIndex, cpToUtf16 } from "@/lib/offsets";

// Hand-derived expectations: emoji is 1 code point and 2 UTF-16 units; CRLF is 2 of each; BOM is 1 of each.
const SMILE = String.fromCodePoint(0x1f600);
const BOM = String.fromCodePoint(0xfeff);

describe("offset index", () => {
  it("is the identity on BMP-only text", () => {
    const idx = buildOffsetIndex("hello\r\nworld");
    for (let i = 0; i <= 12; i++) {
      expect(idx.toUtf16(i)).toBe(i);
      expect(idx.toCodePoint(i)).toBe(i);
    }
  });

  it("counts an emoji as one code point and two UTF-16 units", () => {
    const text = `a${SMILE}b`; // code points: a=0, emoji=1, b=2, end=3
    const idx = buildOffsetIndex(text);
    expect(idx.codePoints).toBe(3);
    expect(idx.utf16Length).toBe(4);
    expect([0, 1, 2, 3].map(idx.toUtf16)).toEqual([0, 1, 3, 4]);
    expect([0, 1, 2, 3, 4].map(idx.toCodePoint)).toEqual([0, 1, 1, 2, 3]); // 2 is inside the pair -> rounds down
  });

  it("handles BOM, CRLF and several emoji together", () => {
    const text = `${BOM}x${SMILE}${SMILE}\r\ny`;
    const idx = buildOffsetIndex(text);
    // code points: BOM0 x1 e2 e3 CR4 LF5 y6 end7 ; utf16: BOM0 x1 e2-3 e4-5 CR6 LF7 y8 end9
    expect([0, 1, 2, 3, 4, 5, 6, 7].map(idx.toUtf16)).toEqual([0, 1, 2, 4, 6, 7, 8, 9]);
    expect(idx.toCodePoint(9)).toBe(7);
    expect(idx.toCodePoint(8)).toBe(6);
  });

  it("agrees with Array.from for random mixed text", () => {
    const pool = ["a", "b", "\n", "\r\n", SMILE, "я", BOM, " ", String.fromCodePoint(0x1d11e)];
    let seed = 12345;
    const rnd = () => (seed = (seed * 1103515245 + 12345) & 0x7fffffff) / 0x7fffffff;
    for (let round = 0; round < 200; round++) {
      let text = "";
      for (let i = 0; i < 30; i++) text += pool[Math.floor(rnd() * pool.length)];
      const cps = Array.from(text);
      const idx = buildOffsetIndex(text);
      expect(idx.codePoints).toBe(cps.length);
      for (let cp = 0; cp <= cps.length; cp++) {
        const u16 = cps.slice(0, cp).join("").length;
        expect(idx.toUtf16(cp)).toBe(u16);
        expect(idx.toCodePoint(u16)).toBe(cp);
      }
    }
  });

  it("one-off helper", () => {
    expect(cpToUtf16(`${SMILE}${SMILE}x`, 2)).toBe(4);
  });
});
