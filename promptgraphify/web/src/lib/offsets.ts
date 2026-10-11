// Offset conversion at the editor boundary (docs/DECISIONS.md D-003).
//
// The backend measures spans in Unicode code points. JavaScript strings and CodeMirror use UTF-16 code
// units, so the two differ after every character outside the Basic Multilingual Plane (emoji, some CJK).
// This is the only place that converts. CRLF and BOM need no special handling: each is counted as the
// code points it really is, on both sides.

export interface OffsetIndex {
  /** UTF-16 offset of the code point at `cp` (0 <= cp <= number of code points). */
  toUtf16(cp: number): number;
  /** Code point offset of a UTF-16 offset; an offset inside a surrogate pair rounds down. */
  toCodePoint(u16: number): number;
  readonly codePoints: number;
  readonly utf16Length: number;
}

export function buildOffsetIndex(text: string): OffsetIndex {
  // Positions of astral characters, both as code point index and as UTF-16 index.
  const astralCp: number[] = [];
  const astralU16: number[] = [];
  let cp = 0;
  for (let u = 0; u < text.length; u++) {
    const c = text.charCodeAt(u);
    if (c >= 0xd800 && c <= 0xdbff && u + 1 < text.length) {
      const d = text.charCodeAt(u + 1);
      if (d >= 0xdc00 && d <= 0xdfff) {
        astralCp.push(cp);
        astralU16.push(u);
        u++;
      }
    }
    cp++;
  }
  const countBelow = (arr: number[], x: number) => {
    let lo = 0;
    let hi = arr.length;
    while (lo < hi) {
      const mid = (lo + hi) >> 1;
      if (arr[mid] < x) lo = mid + 1;
      else hi = mid;
    }
    return lo;
  };
  const hasAt = (arr: number[], x: number) => {
    const i = countBelow(arr, x);
    return i < arr.length && arr[i] === x;
  };
  return {
    codePoints: cp,
    utf16Length: text.length,
    toUtf16: (c) => c + countBelow(astralCp, c),
    toCodePoint: (u) => u - countBelow(astralU16, u - 1) - (hasAt(astralU16, u - 1) ? 1 : 0),
  };
}

/** Convenience for one-off conversions. */
export function cpToUtf16(text: string, cp: number): number {
  return buildOffsetIndex(text).toUtf16(cp);
}
