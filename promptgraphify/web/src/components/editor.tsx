"use client";

import { useEffect, useImperativeHandle, useRef, forwardRef } from "react";
import { EditorState, StateEffect, StateField, type Range } from "@codemirror/state";
import {
  Decoration,
  type DecorationSet,
  EditorView,
  drawSelection,
  highlightActiveLine,
  highlightActiveLineGutter,
  keymap,
  lineNumbers,
} from "@codemirror/view";
import { defaultKeymap, history, historyKeymap } from "@codemirror/commands";

// CodeMirror 6 stands in for Monaco (docs/DECISIONS.md D-014): same editing model and decorations, but it
// bundles offline without a worker/CDN loader. Its offsets are UTF-16; callers pass UTF-16 ranges.

export type HighlightKind = "primary" | "evidence" | "uncovered";
export interface Highlight {
  from: number;
  to: number;
  kind: HighlightKind;
}

export interface EditorHandle {
  setText(text: string): void;
  getText(): string;
  focus(): void;
}

const setHighlights = StateEffect.define<Highlight[]>();

const highlightField = StateField.define<DecorationSet>({
  create: () => Decoration.none,
  update(value, tr) {
    value = value.map(tr.changes);
    for (const e of tr.effects) {
      if (e.is(setHighlights)) {
        const len = tr.state.doc.length;
        const ranges: Range<Decoration>[] = e.value
          .filter((h) => h.to > h.from && h.from >= 0 && h.to <= len)
          .map((h) => Decoration.mark({ class: `cm-hl-${h.kind}` }).range(h.from, h.to));
        value = Decoration.set(ranges, true);
      }
    }
    return value;
  },
  provide: (f) => EditorView.decorations.from(f),
});

interface Props {
  initialText: string;
  highlights: Highlight[];
  /** UTF-16 offset to scroll to (start of the primary highlight). */
  reveal?: { offset: number; nonce: number } | null;
  onChange(text: string): void;
  onCaretClick(utf16Offset: number): void;
  onSubmit(): void;
}

export const Editor = forwardRef<EditorHandle, Props>(function Editor(
  { initialText, highlights, reveal, onChange, onCaretClick, onSubmit },
  ref,
) {
  const host = useRef<HTMLDivElement>(null);
  const view = useRef<EditorView | null>(null);
  const cb = useRef({ onChange, onCaretClick, onSubmit });
  cb.current = { onChange, onCaretClick, onSubmit };

  useEffect(() => {
    if (!host.current) return;
    const state = EditorState.create({
      doc: initialText,
      extensions: [
        lineNumbers(),
        highlightActiveLine(),
        highlightActiveLineGutter(),
        drawSelection(),
        history(),
        EditorView.lineWrapping,
        highlightField,
        keymap.of([
          { key: "Mod-Enter", run: () => (cb.current.onSubmit(), true) },
          ...defaultKeymap,
          ...historyKeymap,
        ]),
        EditorView.contentAttributes.of({
          "aria-label": "Prompt source",
          "aria-multiline": "true",
          "data-testid": "editor-content",
          spellcheck: "false",
        }),
        EditorView.updateListener.of((u) => {
          if (u.docChanged) cb.current.onChange(u.state.doc.toString());
        }),
        EditorView.domEventHandlers({
          mouseup: (_e, v) => {
            const sel = v.state.selection.main;
            if (sel.empty) cb.current.onCaretClick(sel.head);
            return false;
          },
        }),
      ],
    });
    const v = new EditorView({ state, parent: host.current });
    view.current = v;
    return () => {
      v.destroy();
      view.current = null;
    };
    // The editor owns its document after mount; `initialText` is intentionally read once.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useImperativeHandle(ref, () => ({
    setText(text) {
      const v = view.current;
      if (!v) return;
      v.dispatch({ changes: { from: 0, to: v.state.doc.length, insert: text } });
    },
    getText: () => view.current?.state.doc.toString() ?? "",
    focus: () => view.current?.focus(),
  }));

  useEffect(() => {
    view.current?.dispatch({ effects: setHighlights.of(highlights) });
  }, [highlights]);

  useEffect(() => {
    const v = view.current;
    if (!v || !reveal) return;
    const pos = Math.min(Math.max(reveal.offset, 0), v.state.doc.length);
    v.dispatch({ effects: EditorView.scrollIntoView(pos, { y: "center" }) });
  }, [reveal]);

  return <div ref={host} className="h-full min-h-0 overflow-hidden" data-testid="editor" />;
});
