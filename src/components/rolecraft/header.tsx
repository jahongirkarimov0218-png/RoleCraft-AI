"use client";

import React, { useState } from "react";
import { Sparkles, Compass, ShieldCheck, Info, X, ExternalLink } from "lucide-react";

export interface RoleCraftHeaderProps {
  status?: "idle" | "generating" | "ready";
}

export function RoleCraftHeader({ status = "idle" }: RoleCraftHeaderProps) {
  const [showMethodologyModal, setShowMethodologyModal] = useState(false);

  return (
    <div className="w-full border-b border-slate-200/80 bg-white/70 backdrop-blur-md">
      <div className="mx-auto flex max-w-5xl items-center justify-between px-4 py-3 sm:px-6">
        {/* Brand Identity */}
        <div className="flex items-center gap-3">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-slate-950 text-white shadow-xs">
            <Sparkles className="h-4 w-4 text-emerald-400" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="text-sm font-bold tracking-tight text-slate-950">
                RoleCraft AI
              </span>
              <span className="rounded-full bg-slate-100 px-2 py-0.5 font-mono text-[10px] font-semibold text-slate-700 border border-slate-200">
                Lou Adler Framework
              </span>
            </div>
            <p className="text-[11px] text-slate-500 hidden sm:block">
              Outcome-Driven Enterprise Job Spec & Thinking Partner
            </p>
          </div>
        </div>

        {/* Status Indicator & Methodology Link */}
        <div className="flex items-center gap-2.5 sm:gap-3.5">
          {/* Live Status Pill */}
          <div className="inline-flex items-center gap-1.5 rounded-full border border-slate-200 bg-slate-50 px-2.5 py-1 text-[11px] font-medium text-slate-700">
            {status === "generating" ? (
              <>
                <span className="relative flex h-2 w-2">
                  <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-amber-400 opacity-75" />
                  <span className="relative inline-flex h-2 w-2 rounded-full bg-amber-500" />
                </span>
                <span className="text-amber-800 font-mono">Sintez qilinmoqda...</span>
              </>
            ) : status === "ready" ? (
              <>
                <span className="h-2 w-2 rounded-full bg-emerald-500" />
                <span className="text-emerald-800 font-medium">Thinking Partner: Tayyor</span>
              </>
            ) : (
              <>
                <span className="h-2 w-2 rounded-full bg-slate-400" />
                <span className="text-slate-600 font-medium">Thinking Partner: Faol</span>
              </>
            )}
          </div>

          {/* Methodology Info Button */}
          <button
            type="button"
            onClick={() => setShowMethodologyModal(true)}
            className="inline-flex items-center gap-1 rounded-md border border-slate-200 bg-white px-2.5 py-1 text-xs font-medium text-slate-700 hover:border-slate-300 hover:bg-slate-50 active:scale-[0.98] transition-[transform,background-color,border-color] duration-150 ease-out focus-ring"
            title="Metodika haqida ma'lumot"
          >
            <Compass className="h-3.5 w-3.5 text-slate-600" />
            <span className="hidden md:inline">Metodika</span>
          </button>
        </div>
      </div>

      {/* Methodology Explainer Modal */}
      {showMethodologyModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/40 p-4 backdrop-blur-xs animate-in fade-in duration-150">
          <div className="w-full max-w-lg rounded-xl border border-slate-200 bg-white p-6 shadow-xl animate-modal-enter">
            <div className="flex items-start justify-between border-b border-slate-100 pb-3">
              <div className="flex items-center gap-2">
                <div className="flex h-7 w-7 items-center justify-center rounded-md bg-slate-900 text-white">
                  <ShieldCheck className="h-4 w-4 text-emerald-400" />
                </div>
                <div>
                  <h3 className="text-base font-semibold text-slate-950">
                    RoleCraft AI Metodologiyasi
                  </h3>
                  <p className="text-xs text-slate-500">
                    Lou Adler Performance-based Hiring va /prompt-nenujna
                  </p>
                </div>
              </div>
              <button
                type="button"
                onClick={() => setShowMethodologyModal(false)}
                className="rounded-md p-1 text-slate-400 hover:bg-slate-100 hover:text-slate-600 active:scale-95 transition-[transform,background-color] duration-100"
              >
                <X className="h-4 w-4" />
              </button>
            </div>

            <div className="mt-4 space-y-3.5 text-xs leading-relaxed text-slate-600">
              <div className="rounded-lg border border-slate-200/80 bg-slate-50/60 p-3">
                <h4 className="font-semibold text-slate-900 mb-1 flex items-center gap-1.5">
                  <Info className="h-3.5 w-3.5 text-slate-700" />
                  1. Nega standart vakansiyalar ishlamaydi?
                </h4>
                <p>
                  Klishelarga to&apos;la («dinamik jamoa», «5+ yil staj», «stressga chidamli») e&apos;lonlar kuchli A-player mutaxassislarni cho&apos;chitadi va zaif kadrlarni jalb qiladi.
                </p>
              </div>

              <div className="rounded-lg border border-emerald-200/80 bg-emerald-50/40 p-3">
                <h4 className="font-semibold text-emerald-950 mb-1">
                  2. Lou Adler: Performance-based Hiring
                </h4>
                <p>
                  Nomzoddan «necha yil ishlaganligi» emas, balki «dastlabki 6 oyda hal qilinishi shart bo&apos;lgan aniq biznes natijalari (Impact)» va «o&apos;xshash masshtabdagi isbotlangan yutuqlari (Track Record)» talab etiladi.
                </p>
              </div>

              <div className="rounded-lg border border-slate-200/80 bg-slate-50/60 p-3">
                <h4 className="font-semibold text-slate-900 mb-1">
                  3. 🛑 Anti-Persona va 🚀 Value Proposition
                </h4>
                <p>
                  Rol kimlarga to&apos;g&apos;ri kelmasligini ochiq aytish orqali nomzodlarning o&apos;zlarini saralashiga (self-filter) erishiladi va haqiqiy avtonomiya va&apos;da qilinadi.
                </p>
              </div>
            </div>

            <div className="mt-5 flex justify-end border-t border-slate-100 pt-3">
              <button
                type="button"
                onClick={() => setShowMethodologyModal(false)}
                className="rounded-lg bg-slate-900 px-3.5 py-1.5 text-xs font-semibold text-white hover:bg-slate-800 active:scale-[0.98] transition-[transform,background-color] duration-150"
              >
                Tushundim
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default RoleCraftHeader;
