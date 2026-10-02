import React from "react";
import { Layers, Github, ArrowUpRight } from "lucide-react";

export function Header() {
  return (
    <header className="sticky top-0 z-40 w-full border-b border-slate-200/80 bg-white/80 backdrop-blur-md">
      <div className="mx-auto flex h-13 max-w-5xl items-center justify-between px-4 sm:px-6">
        {/* Brand */}
        <div className="flex items-center gap-2.5">
          <a
            href="/"
            className="group flex items-center gap-2.5 rounded-md focus-ring"
            aria-label="Customer Feedback AI Home"
          >
            <div className="flex h-7 w-7 items-center justify-center rounded-md bg-slate-950 text-white shadow-xs transition-transform duration-150 group-hover:scale-105 active:scale-[0.98] ease-emil">
              <Layers className="h-3.5 w-3.5 text-slate-100" />
            </div>
            <span className="text-sm font-semibold tracking-tight text-slate-950 transition-colors group-hover:text-slate-800">
              Customer Feedback AI
            </span>
          </a>
        </div>

        {/* Navigation Action: Clean GitHub Link */}
        <div className="flex items-center gap-3">
          <a
            href="https://github.com/jahongirkarimov0218-png/customer-feedback-ai"
            target="_blank"
            rel="noopener noreferrer"
            className="group inline-flex items-center gap-1.5 rounded-md border border-slate-200/80 bg-white px-2.5 py-1 text-xs font-medium text-slate-700 shadow-xs transition-[color,background-color,border-color] duration-150 ease-out hover:border-slate-300 hover:bg-slate-50 hover:text-slate-950 active-press focus-ring"
          >
            <Github className="h-3.5 w-3.5 text-slate-600" />
            <span className="hidden sm:inline">GitHub</span>
            <ArrowUpRight className="h-3 w-3 text-slate-400 transition-transform duration-150 group-hover:-translate-y-0.5 group-hover:translate-x-0.5 group-hover:text-slate-700" />
          </a>
        </div>
      </div>
    </header>
  );
}

export default Header;
