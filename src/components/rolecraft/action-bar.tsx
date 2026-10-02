"use client";

import React, { useState } from "react";
import { Copy, Check, Printer, FileText, CheckCircle2 } from "lucide-react";
import { RawMetrics } from "@/lib/rolecraft/types";
import { triggerCleanPdfExport } from "@/lib/rolecraft/export-pdf";

export interface ActionBarProps {
  markdown: string;
  roleTitle?: string;
  rawMetrics?: RawMetrics;
  onCopy?: () => void;
  onExportPdf?: () => void;
}

export function ActionBar({
  markdown,
  roleTitle,
  rawMetrics,
  onCopy,
  onExportPdf,
}: ActionBarProps) {
  const [copied, setCopied] = useState(false);
  const [toastMessage, setToastMessage] = useState<string | null>(null);

  const handleCopy = async () => {
    try {
      if (navigator?.clipboard?.writeText) {
        await navigator.clipboard.writeText(markdown);
      }
      setCopied(true);
      setToastMessage("Markdown nusxalandi!");
      if (onCopy) onCopy();

      setTimeout(() => {
        setCopied(false);
        setToastMessage(null);
      }, 2000);
    } catch {
      // Fallback
      setToastMessage("Nusxalashda xatolik yuz berdi");
      setTimeout(() => setToastMessage(null), 2000);
    }
  };

  const handleExport = () => {
    if (onExportPdf) {
      onExportPdf();
    } else {
      triggerCleanPdfExport(roleTitle);
    }
  };

  return (
    <div className="no-print relative flex flex-col gap-3 rounded-xl border border-slate-200/90 bg-white p-4 shadow-xs sm:flex-row sm:items-center sm:justify-between">
      {/* Left: Quality Metrics / Status */}
      <div className="flex flex-wrap items-center gap-2">
        <div className="flex items-center gap-1.5 rounded-full bg-slate-100 px-2.5 py-1 text-[11px] font-medium text-slate-700 border border-slate-200/60">
          <FileText className="h-3 w-3 text-slate-500" />
          <span className="font-mono">Lou Adler Spec</span>
        </div>

        {rawMetrics && (
          <>
            <span className="rounded-full bg-emerald-50 border border-emerald-200 px-2 py-0.5 text-[10px] font-semibold text-emerald-700">
              0% Klishe (Anti-Slop Clean)
            </span>
            <span className="rounded-full bg-indigo-50 border border-indigo-200 px-2 py-0.5 text-[10px] font-semibold text-indigo-700">
              {rawMetrics.impactDeliverablesCount} ta Biznes Marra (Impact)
            </span>
          </>
        )}
      </div>

      {/* Right: Tactile Action Buttons */}
      <div className="flex items-center gap-2">
        {/* Copy Markdown Button */}
        <button
          type="button"
          onClick={handleCopy}
          className={`inline-flex items-center gap-1.5 rounded-lg border px-3 py-1.5 text-xs font-semibold shadow-2xs active:scale-[0.98] transition-[transform,background-color,border-color,color] duration-150 ease-out focus-ring ${
            copied
              ? "border-emerald-500 bg-emerald-50 text-emerald-800"
              : "border-slate-200 bg-white text-slate-800 hover:border-slate-300 hover:bg-slate-50"
          }`}
        >
          {copied ? (
            <>
              <Check className="h-3.5 w-3.5 text-emerald-600 animate-in zoom-in-75 duration-150" />
              <span>Nusxalandi!</span>
            </>
          ) : (
            <>
              <Copy className="h-3.5 w-3.5 text-slate-500" />
              <span>Copy Markdown</span>
            </>
          )}
        </button>

        {/* Clean PDF Export Button */}
        <button
          type="button"
          onClick={handleExport}
          className="inline-flex items-center gap-1.5 rounded-lg bg-slate-900 px-3 py-1.5 text-xs font-semibold text-white shadow-2xs hover:bg-slate-800 active:scale-[0.98] transition-[transform,background-color] duration-150 ease-out focus-ring"
        >
          <Printer className="h-3.5 w-3.5 text-slate-200" />
          <span>Export Clean PDF</span>
        </button>
      </div>

      {/* Ephemeral Toast Notification */}
      {toastMessage && (
        <div className="absolute -top-10 right-4 z-50 flex items-center gap-1.5 rounded-lg bg-slate-900 px-3 py-1 text-xs text-white shadow-lg animate-in fade-in slide-in-from-bottom-2 duration-150">
          <CheckCircle2 className="h-3.5 w-3.5 text-emerald-400" />
          <span>{toastMessage}</span>
        </div>
      )}
    </div>
  );
}

export default ActionBar;
