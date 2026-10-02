"use client";

import React from "react";
import { ROLECRAFT_PRESETS } from "@/lib/rolecraft/presets";
import { RoleCraftPreset } from "@/lib/rolecraft/types";
import { Cpu, TrendingUp, Palette, Server, Sparkles } from "lucide-react";

export interface PresetsBarProps {
  onSelectPreset: (preset: RoleCraftPreset) => void;
  activePresetId?: string | null;
  disabled?: boolean;
}

const PRESET_ICONS: Record<string, React.ReactNode> = {
  "staff-ai-engineer": <Cpu className="h-3.5 w-3.5 text-indigo-500" />,
  "head-of-growth": <TrendingUp className="h-3.5 w-3.5 text-emerald-500" />,
  "lead-product-designer": <Palette className="h-3.5 w-3.5 text-amber-500" />,
  "director-engineering": <Server className="h-3.5 w-3.5 text-blue-500" />,
};

export function PresetsBar({
  onSelectPreset,
  activePresetId,
  disabled = false,
}: PresetsBarProps) {
  return (
    <div className="rolecraft-presets-bar space-y-2">
      <div className="flex items-center justify-between">
        <span className="flex items-center gap-1.5 font-mono text-[11px] font-semibold tracking-wider text-slate-500 uppercase">
          <Sparkles className="h-3 w-3 text-slate-400" />
          Enterprise Namunaviy Keyslar (1-klikda to&apos;ldirish)
        </span>
        <span className="text-[11px] text-slate-400 hidden sm:inline">
          Lou Adler Benchmark Rollari
        </span>
      </div>

      <div className="grid grid-cols-1 gap-2 sm:grid-cols-2 lg:grid-cols-4">
        {ROLECRAFT_PRESETS.map((preset) => {
          const isActive = activePresetId === preset.id;
          return (
            <button
              key={preset.id}
              type="button"
              disabled={disabled}
              onClick={() => onSelectPreset(preset)}
              className={`group flex flex-col justify-between rounded-lg border p-3 text-left transition-[transform,border-color,background-color,box-shadow] duration-150 ease-out active:scale-[0.98] focus-ring disabled:cursor-not-allowed disabled:opacity-60 ${
                isActive
                  ? "border-slate-900 bg-slate-900/5 shadow-2xs"
                  : "border-slate-200/80 bg-white hover:border-slate-300 hover:bg-slate-50/70"
              }`}
            >
              <div className="flex items-center justify-between gap-1 mb-1.5">
                <div className="flex items-center gap-1.5">
                  <div className="flex h-5 w-5 items-center justify-center rounded-md bg-slate-100">
                    {PRESET_ICONS[preset.id] || <Sparkles className="h-3 w-3 text-slate-600" />}
                  </div>
                  <span className="text-xs font-semibold text-slate-900 line-clamp-1 group-hover:text-slate-950">
                    {preset.name}
                  </span>
                </div>
              </div>

              <div className="flex items-center justify-between gap-2 mt-auto pt-1">
                <span className="rounded-md bg-slate-100 px-1.5 py-0.5 font-mono text-[10px] font-medium text-slate-600 border border-slate-200/60">
                  {preset.badge}
                </span>
                <span className="text-[10px] text-slate-400 group-hover:text-slate-600">
                  Tanlash &rarr;
                </span>
              </div>
            </button>
          );
        })}
      </div>
    </div>
  );
}

export default PresetsBar;
