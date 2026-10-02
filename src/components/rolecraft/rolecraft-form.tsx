"use client";

import React, { useState, useEffect } from "react";
import { RoleCraftInput } from "@/lib/rolecraft/types";
import { Sparkles, AlertCircle, RotateCcw, Briefcase, Building2, Flame, Layers } from "lucide-react";

export interface RoleCraftFormProps {
  values: RoleCraftInput;
  onChange: (values: RoleCraftInput) => void;
  onSubmit: () => void;
  isLoading: boolean;
  error?: string | null;
  onReset?: () => void;
}

export function RoleCraftForm({
  values,
  onChange,
  onSubmit,
  isLoading,
  error,
  onReset,
}: RoleCraftFormProps) {
  const [touched, setTouched] = useState<Record<string, boolean>>({});
  const [formValidationError, setFormValidationError] = useState<string | null>(null);

  const handleChange = (field: keyof RoleCraftInput, val: string) => {
    setFormValidationError(null);
    onChange({
      ...values,
      [field]: val,
    });
  };

  const handleBlur = (field: string) => {
    setTouched((prev) => ({ ...prev, [field]: true }));
  };

  const isRoleTitleValid = values.roleTitle.trim().length >= 3;
  const isCompanyContextValid = values.companyContext.trim().length >= 10;
  const isCoreBusinessPainValid = values.coreBusinessPain.trim().length >= 10;
  const isTechStackValid = values.techStackAndSkills.trim().length >= 3;

  const isFormValid =
    isRoleTitleValid &&
    isCompanyContextValid &&
    isCoreBusinessPainValid &&
    isTechStackValid;

  useEffect(() => {
    if (isFormValid) {
      setFormValidationError(null);
    }
  }, [isFormValid]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setTouched({
      roleTitle: true,
      companyContext: true,
      coreBusinessPain: true,
      techStackAndSkills: true,
    });

    if (!isFormValid || isLoading) {
      setFormValidationError(
        "Iltimos, barcha majburiy maydonlarni to'liq to'ldiring (kamida belgilangan minimal belgilar soni)."
      );
      return;
    }
    setFormValidationError(null);
    onSubmit();
  };

  return (
    <form
      id="rolecraft-workspace-form"
      onSubmit={handleSubmit}
      className="space-y-4 rounded-xl border border-slate-200/80 bg-white p-5 shadow-2xs"
    >
      <div className="flex items-center justify-between border-b border-slate-100 pb-3">
        <div className="flex items-center gap-2">
          <span className="flex h-2 w-2 rounded-full bg-slate-900" />
          <h2 className="text-sm font-semibold text-slate-950">
            Rol Parametrlari va Biznes Konteksti
          </h2>
        </div>
        {onReset && (
          <button
            type="button"
            onClick={() => {
              setTouched({});
              setFormValidationError(null);
              onReset();
            }}
            disabled={isLoading}
            className="inline-flex items-center gap-1 rounded-md px-2 py-1 text-[11px] font-medium text-slate-500 hover:bg-slate-100 hover:text-slate-800 disabled:opacity-50 active:scale-[0.98] transition-[transform,background-color,color] duration-150"
          >
            <RotateCcw className="h-3 w-3" />
            <span>Tozalash</span>
          </button>
        )}
      </div>

      {/* Field 1: Role Title */}
      <div className="space-y-1.5">
        <div className="flex items-center justify-between">
          <label
            htmlFor="roleTitle"
            className="flex items-center gap-1.5 text-xs font-semibold text-slate-800"
          >
            <Briefcase className="h-3.5 w-3.5 text-slate-500" />
            1. Lavozim Nomi (Role Title)
          </label>
          <span className="font-mono text-[11px] text-slate-400 tabular-nums">
            {values.roleTitle.length} / min 3
          </span>
        </div>
        <input
          id="roleTitle"
          type="text"
          value={values.roleTitle}
          onChange={(e) => handleChange("roleTitle", e.target.value)}
          onBlur={() => handleBlur("roleTitle")}
          placeholder="Masalan: Staff AI / LLM Architect, Head of Growth"
          disabled={isLoading}
          className={`w-full rounded-lg border px-3 py-2 text-xs text-slate-900 placeholder-slate-400 focus-ring disabled:bg-slate-50 ${
            touched.roleTitle && !isRoleTitleValid
              ? "border-rose-400 bg-rose-50/20"
              : "border-slate-200 bg-white"
          }`}
        />
        {touched.roleTitle && !isRoleTitleValid && (
          <p className="text-[11px] text-rose-600 flex items-center gap-1">
            <AlertCircle className="h-3 w-3" />
            Lavozim nomi kamida 3 ta belgidan iborat bo&apos;lishi kerak.
          </p>
        )}
      </div>

      {/* Field 2: Company Context */}
      <div className="space-y-1.5">
        <div className="flex items-center justify-between">
          <label
            htmlFor="companyContext"
            className="flex items-center gap-1.5 text-xs font-semibold text-slate-800"
          >
            <Building2 className="h-3.5 w-3.5 text-slate-500" />
            2. Kompaniya Konteksti va O&apos;sish Bosqichi
          </label>
          <span className="font-mono text-[11px] text-slate-400 tabular-nums">
            {values.companyContext.length} / min 10
          </span>
        </div>
        <textarea
          id="companyContext"
          rows={2}
          value={values.companyContext}
          onChange={(e) => handleChange("companyContext", e.target.value)}
          onBlur={() => handleBlur("companyContext")}
          placeholder="Masalan: Series B B2B SaaS, 65 kishi, oylik 10x ARR o'sishi, 30M$ investitsiya jalb qilingan enterprise ekotizimi..."
          disabled={isLoading}
          className={`w-full rounded-lg border px-3 py-2 text-xs text-slate-900 placeholder-slate-400 focus-ring disabled:bg-slate-50 resize-y ${
            touched.companyContext && !isCompanyContextValid
              ? "border-rose-400 bg-rose-50/20"
              : "border-slate-200 bg-white"
          }`}
        />
        {touched.companyContext && !isCompanyContextValid && (
          <p className="text-[11px] text-rose-600 flex items-center gap-1">
            <AlertCircle className="h-3 w-3" />
            Kompaniya konteksti kamida 10 ta belgidan iborat bo&apos;lishi kerak.
          </p>
        )}
      </div>

      {/* Field 3: Core Business Pain (Root Cause) */}
      <div className="space-y-1.5">
        <div className="flex items-center justify-between">
          <label
            htmlFor="coreBusinessPain"
            className="flex items-center gap-1.5 text-xs font-semibold text-slate-800"
          >
            <Flame className="h-3.5 w-3.5 text-rose-500" />
            3. Asosiy Biznes Dardi / To&apos;siq (Root Cause)
          </label>
          <span className="font-mono text-[11px] text-slate-400 tabular-nums">
            {values.coreBusinessPain.length} / min 10
          </span>
        </div>
        <textarea
          id="coreBusinessPain"
          rows={2}
          value={values.coreBusinessPain}
          onChange={(e) => handleChange("coreBusinessPain", e.target.value)}
          onBlur={() => handleBlur("coreBusinessPain")}
          placeholder="Masalan: MVP va prototip PoC tuzog'ida tiqilib qolgan: kechikish > 2.5s, token xarajatlari yuqori, production darajasidagi eval va guardrails yo'q..."
          disabled={isLoading}
          className={`w-full rounded-lg border px-3 py-2 text-xs text-slate-900 placeholder-slate-400 focus-ring disabled:bg-slate-50 resize-y ${
            touched.coreBusinessPain && !isCoreBusinessPainValid
              ? "border-rose-400 bg-rose-50/20"
              : "border-slate-200 bg-white"
          }`}
        />
        {touched.coreBusinessPain && !isCoreBusinessPainValid && (
          <p className="text-[11px] text-rose-600 flex items-center gap-1">
            <AlertCircle className="h-3 w-3" />
            Biznes dardi kamida 10 ta belgidan iborat bo&apos;lishi kerak.
          </p>
        )}
      </div>

      {/* Field 4: Tech Stack & Skills */}
      <div className="space-y-1.5">
        <div className="flex items-center justify-between">
          <label
            htmlFor="techStackAndSkills"
            className="flex items-center gap-1.5 text-xs font-semibold text-slate-800"
          >
            <Layers className="h-3.5 w-3.5 text-slate-500" />
            4. Texnologik Stak va Amaliy Ko&apos;nikmalar
          </label>
          <span className="font-mono text-[11px] text-slate-400 tabular-nums">
            {values.techStackAndSkills.length} / min 3
          </span>
        </div>
        <input
          id="techStackAndSkills"
          type="text"
          value={values.techStackAndSkills}
          onChange={(e) => handleChange("techStackAndSkills", e.target.value)}
          onBlur={() => handleBlur("techStackAndSkills")}
          placeholder="Masalan: Python 3.12, FastAPI, LangGraph, vLLM, PostgreSQL, pgvector, Redis, Kubernetes"
          disabled={isLoading}
          className={`w-full rounded-lg border px-3 py-2 text-xs text-slate-900 placeholder-slate-400 focus-ring disabled:bg-slate-50 ${
            touched.techStackAndSkills && !isTechStackValid
              ? "border-rose-400 bg-rose-50/20"
              : "border-slate-200 bg-white"
          }`}
        />
        {touched.techStackAndSkills && !isTechStackValid && (
          <p className="text-[11px] text-rose-600 flex items-center gap-1">
            <AlertCircle className="h-3 w-3" />
            Texnologik stak kamida 3 ta belgidan iborat bo&apos;lishi kerak.
          </p>
        )}
      </div>

      {/* Global Error Banner if any */}
      {(formValidationError || error) && (
        <div
          role="alert"
          aria-live="polite"
          className="rounded-lg border border-rose-200 bg-rose-50/60 p-3 text-xs text-rose-700 flex items-start gap-2"
        >
          <AlertCircle className="h-4 w-4 shrink-0 text-rose-600 mt-0.5" />
          <span>{formValidationError || error}</span>
        </div>
      )}

      {/* Submit CTA */}
      <div className="pt-2">
        <button
          type="submit"
          disabled={isLoading}
          className="group relative flex w-full items-center justify-center gap-2 rounded-lg bg-slate-950 px-4 py-2.5 text-xs font-semibold text-white shadow-xs hover:bg-slate-800 active:scale-[0.98] transition-[transform,background-color,box-shadow,opacity] duration-150 ease-out disabled:cursor-not-allowed disabled:opacity-50 focus-ring"
        >
          {isLoading ? (
            <>
              <div className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-white/30 border-t-white" />
              <span>Thinking Partner sintez qilmoqda...</span>
            </>
          ) : (
            <>
              <Sparkles className="h-3.5 w-3.5 text-emerald-400 transition-transform duration-150 group-hover:scale-110" />
              <span>Enterprise Rolni Sintez Qilish (Thinking Partner)</span>
            </>
          )}
        </button>
      </div>
    </form>
  );
}

export default RoleCraftForm;
