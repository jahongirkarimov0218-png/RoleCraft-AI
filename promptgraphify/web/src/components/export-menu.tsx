"use client";

import { useEffect, useRef, useState } from "react";
import { Download } from "lucide-react";
import { Button } from "@/components/ui/button";
import { EXPORTS, exportUrl } from "@/lib/exports";

/** Download menu for the last analysis. Plain links with the `download` attribute: no script touches the data. */
export function ExportMenu({ graphId }: { graphId: string | null }) {
  const [open, setOpen] = useState(false);
  const root = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const away = (e: MouseEvent) => {
      if (root.current && !root.current.contains(e.target as Node)) setOpen(false);
    };
    const esc = (e: KeyboardEvent) => e.key === "Escape" && setOpen(false);
    document.addEventListener("mousedown", away);
    document.addEventListener("keydown", esc);
    return () => {
      document.removeEventListener("mousedown", away);
      document.removeEventListener("keydown", esc);
    };
  }, [open]);

  return (
    <div ref={root} className="relative">
      <Button
        variant="outline"
        size="sm"
        disabled={!graphId}
        aria-expanded={open}
        aria-haspopup="true"
        aria-controls="export-list"
        onClick={() => setOpen((o) => !o)}
        data-testid="export-button"
        title={graphId ? "Download the last analysis" : "Analyze a prompt first"}
      >
        <Download className="size-4" aria-hidden /> Export
      </Button>
      {open && graphId && (
        <ul
          id="export-list"
          className="absolute right-0 z-20 mt-1 w-72 rounded-md border border-border bg-surface p-1 text-sm shadow-lg"
          data-testid="export-list"
        >
          {EXPORTS.map((o) => (
            <li key={o.label}>
              <a
                href={exportUrl(graphId, o)}
                download={o.label}
                onClick={() => setOpen(false)}
                className="block rounded px-2 py-1.5 hover:bg-surface-2 focus-visible:bg-surface-2"
                data-testid={`export-${o.label}`}
              >
                <span className="font-medium">{o.label}</span>
                <span className="block text-xs text-muted">{o.hint}</span>
              </a>
            </li>
          ))}
          <li className="px-2 py-1 text-xs text-muted">Exports the last analysis, not unsaved edits.</li>
        </ul>
      )}
    </div>
  );
}
