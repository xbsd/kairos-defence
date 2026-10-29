// The recall text resolving from glyphs (SPEC §17.8, D-131): deterministic, no random draws.
// Each character resolves at a time set by its index; until then it shows a glyph chosen from a
// fixed set by its index and the frame. Spaces and line breaks never scramble, so the layout
// (and the clue span positions) holds from the first frame.
export const GLYPHS = "▖▗▘▙▚▛▜▝▞▟░▒";
export const RESOLVE_MS = 600;

/** The text `t` ms into the resolve (t ≥ RESOLVE_MS is the plain text). Same length always. */
export function scrambled(text: string, t: number, ms = RESOLVE_MS): string {
  if (t >= ms) return text;
  const frame = Math.floor(Math.max(0, t) / 50);
  let out = "";
  for (let i = 0; i < text.length; i++) {
    const ch = text[i] as string;
    // left to right with a little stagger: character i is done at (i / n) * 0.8 ms + 0.2 ms
    const doneAt = ((i / Math.max(1, text.length)) * 0.8 + 0.2) * ms;
    if (t >= doneAt || /\s/.test(ch)) out += ch;
    else out += GLYPHS[(i * 7 + frame * 3) % GLYPHS.length];
  }
  return out;
}
