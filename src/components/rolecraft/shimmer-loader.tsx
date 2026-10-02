"use client";

import React from "react";

const shimmerBar =
  "bg-gradient-to-r from-slate-200/60 via-slate-100 to-slate-200/60 bg-[length:200%_100%] animate-shimmer";
const shimmerBarRose =
  "bg-gradient-to-r from-rose-200/60 via-rose-100 to-rose-200/60 bg-[length:200%_100%] animate-shimmer";
const shimmerBarEmerald =
  "bg-gradient-to-r from-emerald-200/60 via-emerald-100 to-emerald-200/60 bg-[length:200%_100%] animate-shimmer";

export function ShimmerLoader() {
  return (
    <div
      role="status"
      aria-label="Yuklanmoqda..."
      className="space-y-6"
    >
      {/* 1. Header & Thinking Partner Shimmer */}
      <div className="rounded-xl border border-slate-200/80 bg-white p-5 space-y-4">
        <div className="flex items-center justify-between border-b border-slate-100 pb-3">
          <div className="flex items-center gap-2">
            <div className={`h-6 w-6 rounded-md ${shimmerBar}`} />
            <div className={`h-4 w-48 rounded ${shimmerBar}`} />
          </div>
          <div className={`h-5 w-28 rounded ${shimmerBar}`} />
        </div>

        <div className="grid grid-cols-1 gap-3.5 md:grid-cols-3">
          <div className="rounded-lg border border-slate-200/60 bg-slate-50/50 p-3.5 space-y-2.5">
            <div className={`h-4 w-32 rounded ${shimmerBar}`} />
            <div className="space-y-1.5">
              <div className={`h-3 w-full rounded ${shimmerBar}`} />
              <div className={`h-3 w-4/5 rounded ${shimmerBar}`} />
              <div className={`h-3 w-3/4 rounded ${shimmerBar}`} />
            </div>
          </div>
          <div className="rounded-lg border border-slate-200/60 bg-slate-50/50 p-3.5 space-y-2.5">
            <div className={`h-4 w-36 rounded ${shimmerBar}`} />
            <div className="space-y-1.5">
              <div className={`h-3 w-full rounded ${shimmerBar}`} />
              <div className={`h-3 w-5/6 rounded ${shimmerBar}`} />
              <div className={`h-3 w-2/3 rounded ${shimmerBar}`} />
            </div>
          </div>
          <div className="rounded-lg border border-slate-200/60 bg-slate-50/50 p-3.5 space-y-2.5">
            <div className={`h-4 w-32 rounded ${shimmerBar}`} />
            <div className="space-y-1.5">
              <div className={`h-3 w-full rounded ${shimmerBar}`} />
              <div className={`h-3 w-4/5 rounded ${shimmerBar}`} />
              <div className={`h-3 w-1/2 rounded ${shimmerBar}`} />
            </div>
          </div>
        </div>
      </div>

      {/* 2. Job Description Markdown Shimmer */}
      <div className="rounded-xl border border-slate-200/80 bg-white p-6 space-y-6">
        {/* Title & Context Shimmer */}
        <div className="space-y-2.5 border-b border-slate-100 pb-4">
          <div className={`h-7 w-2/3 rounded ${shimmerBar}`} />
          <div className={`h-4 w-1/2 rounded ${shimmerBar}`} />
        </div>

        {/* Section 1: Hierarchy */}
        <div className="space-y-2">
          <div className={`h-5 w-48 rounded ${shimmerBar}`} />
          <div className={`h-3.5 w-full rounded ${shimmerBar}`} />
          <div className={`h-3.5 w-4/5 rounded ${shimmerBar}`} />
        </div>

        {/* Section 2: 6-Month Deliverables */}
        <div className="space-y-3">
          <div className={`h-5 w-64 rounded ${shimmerBar}`} />
          <div className="space-y-2 pl-3">
            <div className={`h-3.5 w-full rounded ${shimmerBar}`} />
            <div className={`h-3.5 w-11/12 rounded ${shimmerBar}`} />
            <div className={`h-3.5 w-10/12 rounded ${shimmerBar}`} />
          </div>
        </div>

        {/* Section 3: Track Record */}
        <div className="space-y-2">
          <div className={`h-5 w-56 rounded ${shimmerBar}`} />
          <div className="space-y-2 pl-3">
            <div className={`h-3.5 w-full rounded ${shimmerBar}`} />
            <div className={`h-3.5 w-4/5 rounded ${shimmerBar}`} />
          </div>
        </div>

        {/* Section 5: Anti-Persona (Red tinted shimmer) */}
        <div className="rounded-lg border border-rose-200/60 bg-rose-50/30 p-4 space-y-2">
          <div className={`h-5 w-52 rounded ${shimmerBarRose}`} />
          <div className={`h-3.5 w-full rounded ${shimmerBarRose}`} />
          <div className={`h-3.5 w-3/4 rounded ${shimmerBarRose}`} />
        </div>

        {/* Section 6: Value Proposition (Emerald tinted shimmer) */}
        <div className="rounded-lg border border-emerald-200/60 bg-emerald-50/30 p-4 space-y-2">
          <div className={`h-5 w-52 rounded ${shimmerBarEmerald}`} />
          <div className={`h-3.5 w-full rounded ${shimmerBarEmerald}`} />
          <div className={`h-3.5 w-4/5 rounded ${shimmerBarEmerald}`} />
        </div>
      </div>
    </div>
  );
}

export default ShimmerLoader;
