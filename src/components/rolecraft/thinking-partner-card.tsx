"use client";

import React from "react";
import { ThinkingPartnerAnalysis } from "@/lib/rolecraft/types";
import { Brain, Flame, Target, Compass } from "lucide-react";

export interface ThinkingPartnerCardProps {
  data: ThinkingPartnerAnalysis;
}

export function ThinkingPartnerCard({ data }: ThinkingPartnerCardProps) {
  if (!data) return null;

  return (
    <div className="rounded-xl border border-slate-200/90 bg-white p-5 shadow-2xs space-y-4">
      {/* Header */}
      <div className="flex flex-col gap-1 sm:flex-row sm:items-center sm:justify-between border-b border-slate-100 pb-3">
        <div className="flex items-center gap-2">
          <div className="flex h-6 w-6 items-center justify-center rounded-md bg-slate-900 text-white">
            <Brain className="h-3.5 w-3.5 text-emerald-400" />
          </div>
          <h3 className="text-sm font-semibold text-slate-950">
            Thinking Partner: Strategik Tahlil Matritsasi
          </h3>
        </div>
        <span className="font-mono text-[11px] font-medium text-slate-500 bg-slate-50 border border-slate-200 rounded-md px-2 py-0.5 self-start sm:self-auto">
          /prompt-nenujna Alignment
        </span>
      </div>

      {/* Grid of 3 Insight Dimensions */}
      <div className="grid grid-cols-1 gap-3.5 md:grid-cols-3">
        {/* Dimension 1: Root Cause / Business Pain */}
        <div className="flex flex-col justify-between rounded-lg border border-slate-200/80 bg-slate-50/50 p-3.5 space-y-2">
          <div className="flex items-center gap-2">
            <div className="flex h-5 w-5 items-center justify-center rounded-md bg-rose-100">
              <Flame className="h-3 w-3 text-rose-600" />
            </div>
            <span className="text-xs font-semibold text-slate-900">
              Biznes Dardi (Root Cause)
            </span>
          </div>
          <p className="text-xs leading-relaxed text-slate-600">
            {data.rootProblemAnalysis}
          </p>
          <div className="pt-1 mt-auto border-t border-slate-200/50">
            <span className="text-[10px] font-mono text-slate-500 uppercase">
              Asosiy to&apos;siq
            </span>
          </div>
        </div>

        {/* Dimension 2: Candidate Fears vs Drivers */}
        <div className="flex flex-col justify-between rounded-lg border border-slate-200/80 bg-slate-50/50 p-3.5 space-y-2">
          <div className="flex items-center gap-2">
            <div className="flex h-5 w-5 items-center justify-center rounded-md bg-amber-100">
              <Target className="h-3 w-3 text-amber-600" />
            </div>
            <span className="text-xs font-semibold text-slate-900">
              A-Player Psixologiyasi
            </span>
          </div>
          <p className="text-xs leading-relaxed text-slate-600">
            {data.candidateFearsAndDrivers}
          </p>
          <div className="pt-1 mt-auto border-t border-slate-200/50">
            <span className="text-[10px] font-mono text-slate-500 uppercase">
              Qo&apos;rquv vs Motivatsiya
            </span>
          </div>
        </div>

        {/* Dimension 3: Strategic Executive Angle */}
        <div className="flex flex-col justify-between rounded-lg border border-slate-200/80 bg-slate-50/50 p-3.5 space-y-2">
          <div className="flex items-center gap-2">
            <div className="flex h-5 w-5 items-center justify-center rounded-md bg-emerald-100">
              <Compass className="h-3 w-3 text-emerald-700" />
            </div>
            <span className="text-xs font-semibold text-slate-900">
              Strategik Pozitsiya
            </span>
          </div>
          <p className="text-xs leading-relaxed text-slate-600">
            {data.strategicAngle}
          </p>
          <div className="pt-1 mt-auto border-t border-slate-200/50">
            <span className="text-[10px] font-mono text-slate-500 uppercase">
              Lou Adler Positioning
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}

export default ThinkingPartnerCard;
