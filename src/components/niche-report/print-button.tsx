"use client";

import React from "react";
import { Printer } from "lucide-react";

// triggerCleanPdfExport is not reused: it appends a RoleCraft suffix to the document title.
export function PrintButton() {
  return (
    <button
      type="button"
      onClick={() => window.print()}
      className="no-print tactile-btn focus-ring inline-flex items-center gap-1.5 rounded-md border border-slate-200/80 bg-white px-2.5 py-1 text-xs font-medium text-slate-700 shadow-subtle hover:border-slate-300 hover:bg-slate-50 hover:text-slate-950"
    >
      <Printer className="h-3.5 w-3.5 text-slate-500" aria-hidden="true" />
      Печать / PDF
    </button>
  );
}
