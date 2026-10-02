"use client";

import React, { useState, useRef } from "react";
import { Sparkles, Layers, RotateCcw, ArrowRight } from "lucide-react";
import { ROLECRAFT_PRESETS } from "@/lib/rolecraft/presets";
import { RoleCraftInput, RoleCraftOutput, RoleCraftPreset } from "@/lib/rolecraft/types";
import {
  RoleCraftHeader,
  PresetsBar,
  RoleCraftForm,
  ThinkingPartnerCard,
  ShimmerLoader,
  StreamingMarkdownView,
  ActionBar,
} from "@/components/rolecraft";

// Existing Customer Feedback AI components (preserved in Tab 2)
import { FeedbackInput } from "@/components/feedback-input";
import { SkeletonLoader } from "@/components/skeleton-loader";
import { ErrorAlert, ErrorType } from "@/components/error-alert";
import {
  SummaryCard,
  SentimentCard,
  TopInsights,
  ProblemsTable,
} from "@/components/results";
import { EvidenceModal } from "@/components/results/evidence-modal";
import { FeedbackPreset } from "@/components/presets";
import { AnalysisResponse, ProblemSolutionItem } from "@/types/analyzer";
import { BENCHMARK_ANALYSIS_DATA } from "@/lib/benchmark-data";

export default function HomePage() {
  // Navigation / Suite Mode: RoleCraft AI is primary flagship
  const [activeTab, setActiveTab] = useState<"rolecraft" | "feedback">("rolecraft");

  // --- RoleCraft AI State ---
  const [roleCraftInput, setRoleCraftInput] = useState<RoleCraftInput>(
    ROLECRAFT_PRESETS[0].input
  );
  const [activePresetId, setActivePresetId] = useState<string | null>(
    ROLECRAFT_PRESETS[0].id
  );
  const [isRoleCraftLoading, setIsRoleCraftLoading] = useState(false);
  const [isRoleCraftStreaming, setIsRoleCraftStreaming] = useState(false);
  const [streamingMarkdown, setStreamingMarkdown] = useState<string>("");
  const [roleCraftOutput, setRoleCraftOutput] = useState<RoleCraftOutput | null>(null);
  const [roleCraftError, setRoleCraftError] = useState<string | null>(null);

  const roleCraftResultsRef = useRef<HTMLDivElement>(null);

  // --- Customer Feedback AI State ---
  const [feedbackText, setFeedbackText] = useState("");
  const [isFeedbackLoading, setIsFeedbackLoading] = useState(false);
  const [feedbackData, setFeedbackData] = useState<AnalysisResponse | null>(null);
  const [feedbackError, setFeedbackError] = useState<{
    message: string;
    type: ErrorType;
  } | null>(null);
  const [selectedProblemForEvidence, setSelectedProblemForEvidence] =
    useState<ProblemSolutionItem | null>(null);
  const [isEvidenceModalOpen, setIsEvidenceModalOpen] = useState(false);
  const feedbackResultsRef = useRef<HTMLDivElement>(null);

  // --- RoleCraft Handlers ---
  const handleSelectRolePreset = (preset: RoleCraftPreset) => {
    setRoleCraftInput(preset.input);
    setActivePresetId(preset.id);
    setRoleCraftError(null);
  };

  const handleRoleCraftChange = (newValues: RoleCraftInput) => {
    setRoleCraftInput(newValues);
    setActivePresetId(null); // Custom edited
    setRoleCraftError(null);
  };

  const handleResetRoleCraft = () => {
    setRoleCraftOutput(null);
    setStreamingMarkdown("");
    setRoleCraftError(null);
  };

  const handleGenerateRoleCraft = async () => {
    setIsRoleCraftLoading(true);
    setIsRoleCraftStreaming(true);
    setRoleCraftError(null);
    setStreamingMarkdown("");
    setRoleCraftOutput(null);

    try {
      const response = await fetch("/api/rolecraft/generate", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Accept: "text/event-stream",
        },
        body: JSON.stringify({ ...roleCraftInput, stream: true }),
      });

      if (!response.ok) {
        const errorJson = await response.json().catch(() => null);
        throw new Error(errorJson?.error || "Generatsiya jarayonida xatolik yuz berdi");
      }

      const contentType = response.headers.get("content-type") || "";

      if (contentType.includes("text/event-stream") && response.body) {
        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let accumulatedMarkdown = "";
        let finalOutput: RoleCraftOutput | null = null;

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          const chunkText = decoder.decode(value, { stream: true });
          const lines = chunkText.split("\n");

          for (const line of lines) {
            const trimmed = line.trim();
            if (trimmed.startsWith("data: ")) {
              const dataContent = trimmed.replace(/^data:\s*/, "");
              if (dataContent === "[DONE]") continue;

              try {
                const parsed = JSON.parse(dataContent);
                if (parsed.type === "chunk" && parsed.chunk) {
                  accumulatedMarkdown += parsed.chunk;
                  setStreamingMarkdown(accumulatedMarkdown);
                } else if (parsed.type === "done" && parsed.output) {
                  finalOutput = parsed.output;
                }
              } catch {
                // Ignore parse errors on partial frames
              }
            }
          }
        }

        if (finalOutput) {
          setRoleCraftOutput(finalOutput);
          setStreamingMarkdown(finalOutput.jobDescriptionMarkdown);
        } else if (accumulatedMarkdown) {
          // If stream ended without done frame, synthesize fallback output object
          setStreamingMarkdown(accumulatedMarkdown);
        }
      } else {
        // Standard JSON response
        const data = await response.json();
        if (data.success && data.data) {
          setRoleCraftOutput(data.data);
          setStreamingMarkdown(data.data.jobDescriptionMarkdown);
        }
      }

      setTimeout(() => {
        roleCraftResultsRef.current?.scrollIntoView({
          behavior: "smooth",
          block: "start",
        });
      }, 100);
    } catch (err: unknown) {
      setRoleCraftError(
        err instanceof Error ? err.message : "Kutilmagan xatolik yuz berdi"
      );
    } finally {
      setIsRoleCraftLoading(false);
      setIsRoleCraftStreaming(false);
    }
  };

  // --- Feedback Handlers ---
  const handleAnalyzeFeedback = async () => {
    const trimmed = feedbackText.trim();
    if (trimmed.length < 10) {
      setFeedbackError({
        message:
          "Fikr matni kamida 10 ta belgidan iborat bo'lishi kerak. Iltimos, batafsilroq sharh yozing yoki namunalardan birini tanlang.",
        type: "validation",
      });
      return;
    }

    setIsFeedbackLoading(true);
    setFeedbackError(null);

    try {
      const response = await fetch("/api/analyze", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ feedback: trimmed }),
      });

      const data = await response.json();
      if (!response.ok) {
        throw new Error(data.error || "Tahlil jarayonida xatolik yuz berdi");
      }

      setFeedbackData(data as AnalysisResponse);
      setTimeout(() => {
        feedbackResultsRef.current?.scrollIntoView({
          behavior: "smooth",
          block: "start",
        });
      }, 100);
    } catch (err: unknown) {
      const errorMessage =
        err instanceof Error ? err.message : "Kutilmagan xatolik yuz berdi";
      setFeedbackError({
        message: errorMessage,
        type: errorMessage.toLowerCase().includes("network")
          ? "network"
          : "server",
      });
    } finally {
      setIsFeedbackLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-slate-50/50 pb-16">
      {/* Flagship Header */}
      <RoleCraftHeader
        status={
          isRoleCraftLoading
            ? "generating"
            : roleCraftOutput
            ? "ready"
            : "idle"
        }
      />

      <div className="mx-auto max-w-5xl px-4 py-8 sm:px-6 space-y-8">
        {/* Navigation Switcher: RoleCraft AI vs Feedback Intelligence */}
        <div className="no-print flex items-center justify-between border-b border-slate-200/80 pb-3">
          <div className="flex items-center gap-1.5 rounded-lg bg-slate-100 p-1 border border-slate-200/60">
            <button
              type="button"
              onClick={() => setActiveTab("rolecraft")}
              className={`flex items-center gap-2 rounded-md px-3 py-1.5 text-xs font-semibold active:scale-[0.98] transition-[transform,background-color,color] duration-150 ${
                activeTab === "rolecraft"
                  ? "bg-white text-slate-950 shadow-2xs"
                  : "text-slate-600 hover:text-slate-900"
              }`}
            >
              <Sparkles className="h-3.5 w-3.5 text-emerald-600" />
              <span>RoleCraft AI (Lou Adler Specs)</span>
            </button>
            <button
              type="button"
              onClick={() => setActiveTab("feedback")}
              className={`flex items-center gap-2 rounded-md px-3 py-1.5 text-xs font-semibold active:scale-[0.98] transition-[transform,background-color,color] duration-150 ${
                activeTab === "feedback"
                  ? "bg-white text-slate-950 shadow-2xs"
                  : "text-slate-600 hover:text-slate-900"
              }`}
            >
              <Layers className="h-3.5 w-3.5 text-slate-500" />
              <span>Customer Feedback AI</span>
            </button>
          </div>

          <div className="hidden sm:flex items-center gap-2">
            <span className="font-mono text-[11px] text-slate-500">
              No AI-Slop &bull; 100% Outcome Driven
            </span>
          </div>
        </div>

        {/* ======================================================== */}
        {/* TAB 1: RoleCraft AI (Primary Enterprise Generator)        */}
        {/* ======================================================== */}
        {activeTab === "rolecraft" && (
          <div className="space-y-8">
            {/* Hero Section */}
            <section className="no-print space-y-3 pt-2 text-center sm:text-left">
              <div className="inline-flex items-center gap-2 rounded-full border border-slate-200 bg-white px-3 py-1 font-mono text-[11px] font-medium text-slate-700 shadow-2xs">
                <span className="h-1.5 w-1.5 rounded-full bg-emerald-500" />
                <span>Lou Adler Performance-based Hiring + Thinking Partner</span>
              </div>

              <h1 className="text-3xl font-bold tracking-tight text-slate-950 sm:text-4xl leading-[1.15]">
                Klishelarsiz, Biznes Ta&apos;siriga (Impact) Asoslangan Rol Tavsifi
              </h1>

              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                <p className="max-w-2xl text-sm leading-relaxed text-slate-600">
                  Biznes dardi (Root Cause) va A-player psixologiyasini tahlil qiling. 6 oylik o&apos;lchanadigan marralar, 🛑 Anti-Persona va 🚀 Value Proposition bilan kuchli nomzodlarni jalb qiling.
                </p>

                <button
                  type="button"
                  onClick={handleGenerateRoleCraft}
                  disabled={isRoleCraftLoading}
                  className="inline-flex items-center gap-1.5 text-xs font-semibold text-slate-900 hover:text-slate-600 underline underline-offset-4 active:scale-[0.98] transition-[transform,color] duration-150 shrink-0 self-center sm:self-start"
                >
                  <span>Mavjud namunani sintezlash</span>
                  <ArrowRight className="h-3 w-3" />
                </button>
              </div>
            </section>

            {/* Presets Bar */}
            <section className="no-print">
              <PresetsBar
                onSelectPreset={handleSelectRolePreset}
                activePresetId={activePresetId}
                disabled={isRoleCraftLoading}
              />
            </section>

            {/* Form Workspace */}
            <section className="no-print">
              <RoleCraftForm
                values={roleCraftInput}
                onChange={handleRoleCraftChange}
                onSubmit={handleGenerateRoleCraft}
                isLoading={isRoleCraftLoading}
                error={roleCraftError}
                onReset={handleResetRoleCraft}
              />
            </section>

            {/* Shimmer Loader during generation */}
            {isRoleCraftLoading && !streamingMarkdown && (
              <section className="pt-2">
                <ShimmerLoader />
              </section>
            )}

            {/* Results Section */}
            {(streamingMarkdown || roleCraftOutput) && (
              <section
                ref={roleCraftResultsRef}
                id="rolecraft-results"
                className="space-y-6 pt-4 animate-in fade-in duration-300"
              >
                {/* Result Control Bar */}
                <div className="no-print flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between border-b border-slate-200 pb-3">
                  <div className="flex items-center gap-2">
                    <span className="flex h-2 w-2 rounded-full bg-emerald-500" />
                    <h2 className="text-base font-semibold text-slate-900 tracking-tight sm:text-lg">
                      Sintezlangan Rol va Strategik Matritsa
                    </h2>
                  </div>

                  <div className="flex items-center gap-2 self-start sm:self-center">
                    <button
                      type="button"
                      onClick={handleResetRoleCraft}
                      className="inline-flex items-center gap-1.5 rounded-lg border border-slate-200 bg-white px-2.5 py-1 text-xs font-medium text-slate-600 shadow-2xs hover:bg-slate-50 hover:text-slate-900 active:scale-[0.98] transition-[transform,background-color,color] duration-150"
                    >
                      <RotateCcw className="h-3 w-3" />
                      <span>Yangi Rol Yaratish</span>
                    </button>
                  </div>
                </div>

                {/* 1. Thinking Partner Card */}
                {roleCraftOutput?.thinkingPartner && (
                  <div className="print-clean">
                    <ThinkingPartnerCard data={roleCraftOutput.thinkingPartner} />
                  </div>
                )}

                {/* 2. Action Bar (Copy & Clean PDF Export) */}
                <ActionBar
                  markdown={
                    roleCraftOutput?.jobDescriptionMarkdown || streamingMarkdown
                  }
                  roleTitle={roleCraftInput.roleTitle}
                  rawMetrics={roleCraftOutput?.rawMetrics}
                />

                {/* 3. Streaming Markdown Viewer */}
                <div className="print-clean">
                  <StreamingMarkdownView
                    markdown={
                      roleCraftOutput?.jobDescriptionMarkdown || streamingMarkdown
                    }
                    isStreaming={isRoleCraftStreaming}
                  />
                </div>
              </section>
            )}
          </div>
        )}

        {/* ======================================================== */}
        {/* TAB 2: Customer Feedback AI (Preserved Backlog Analyzer)  */}
        {/* ======================================================== */}
        {activeTab === "feedback" && (
          <div className="space-y-8 animate-in fade-in duration-200">
            {/* Feedback Hero */}
            <section className="space-y-3.5 pt-2 text-center sm:text-left">
              <div className="inline-flex items-center gap-2 rounded-full border border-slate-200/90 bg-slate-50/80 px-3 py-1 font-mono text-[11px] font-medium text-slate-700 shadow-2xs">
                <span className="h-1.5 w-1.5 rounded-full bg-slate-900" />
                <span>Shunchaki sentiment emas: Linear va Jira uchun tayyor backlog</span>
              </div>

              <h1 className="text-3xl font-bold tracking-tight text-slate-950 sm:text-4xl leading-[1.12]">
                Mijoz fikrlarini ustuvor vazifalarga aylantiring
              </h1>

              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                <p className="max-w-2xl text-sm leading-relaxed text-slate-600">
                  Tarqoq sharhlardan tizimli muammolarni ajrating, biznesga ta&apos;sirini baholang va keyingi muhandislik qadamini belgilang.
                </p>

                <button
                  type="button"
                  onClick={() => {
                    setFeedbackError(null);
                    setFeedbackData(BENCHMARK_ANALYSIS_DATA);
                    if (!feedbackText) {
                      setFeedbackText(
                        "To'lov jarayonida 3D-Secure sekin ishlayapti va pul yechilgach buyurtma tasdiqlanmayapti. Kuryer tracking holati ham yangilanmadi."
                      );
                    }
                    setTimeout(() => {
                      feedbackResultsRef.current?.scrollIntoView({
                        behavior: "smooth",
                        block: "start",
                      });
                    }, 50);
                  }}
                  className="inline-flex items-center gap-1.5 text-xs font-semibold text-slate-900 hover:text-slate-600 underline underline-offset-4 active:scale-[0.98] transition-[transform,color] duration-150 shrink-0 self-center sm:self-start"
                >
                  <span>Jonli namunani ko&apos;rish</span>
                  <ArrowRight className="h-3 w-3" />
                </button>
              </div>
            </section>

            {/* Input Workspace */}
            <section id="feedback-workspace" className="space-y-4">
              <FeedbackInput
                value={feedbackText}
                onChange={setFeedbackText}
                onAnalyze={handleAnalyzeFeedback}
                isLoading={isFeedbackLoading}
                onSelectPreset={(preset: FeedbackPreset) => {
                  setFeedbackText(preset.fullText);
                  setFeedbackError(null);
                }}
                onInstantPreview={() => {
                  setFeedbackError(null);
                  setFeedbackData(BENCHMARK_ANALYSIS_DATA);
                  if (!feedbackText) {
                    setFeedbackText(
                      "To'lov jarayonida 3D-Secure sekin ishlayapti va pul yechilgach buyurtma tasdiqlanmayapti. Kuryer tracking holati ham yangilanmadi."
                    );
                  }
                }}
                hasResults={!!feedbackData}
                error={
                  feedbackError?.type === "validation"
                    ? feedbackError.message
                    : null
                }
              />
            </section>

            {/* Error Alert */}
            {feedbackError && feedbackError.type !== "validation" && (
              <section className="animate-in fade-in duration-200">
                <ErrorAlert
                  message={feedbackError.message}
                  type={feedbackError.type}
                  onRetry={handleAnalyzeFeedback}
                  onDismiss={() => setFeedbackError(null)}
                />
              </section>
            )}

            {/* Skeleton Loading */}
            {isFeedbackLoading && (
              <section className="pt-2">
                <SkeletonLoader />
              </section>
            )}

            {/* Feedback Results */}
            {feedbackData && !isFeedbackLoading && (
              <section
                ref={feedbackResultsRef}
                id="analysis-results"
                className="space-y-6 pt-4 animate-in fade-in slide-in-from-bottom-2 duration-300"
              >
                <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between border-b border-slate-200 pb-3">
                  <div className="flex items-center gap-2">
                    <span className="flex h-2 w-2 rounded-full bg-slate-900" />
                    <h2 className="text-base font-semibold text-slate-900 tracking-tight sm:text-lg">
                      Tahlil natijalari
                    </h2>
                  </div>

                  <button
                    type="button"
                    onClick={() => {
                      setFeedbackData(null);
                      setFeedbackError(null);
                    }}
                    className="inline-flex items-center gap-1.5 rounded-lg border border-slate-200 bg-white px-2.5 py-1 text-xs font-medium text-slate-600 shadow-2xs hover:bg-slate-50 hover:text-slate-900 active:scale-[0.98] transition-[transform,background-color,color] duration-150"
                  >
                    <RotateCcw className="h-3 w-3" />
                    <span>Yangi tahlil</span>
                  </button>
                </div>

                <div className="grid grid-cols-1 gap-6 lg:grid-cols-12">
                  <div className="lg:col-span-7">
                    <SummaryCard
                      data={feedbackData}
                      onScrollToMatrix={() => {
                        document
                          .getElementById("problems-matrix")
                          ?.scrollIntoView({ behavior: "smooth" });
                      }}
                    />
                  </div>
                  <div className="lg:col-span-5">
                    <SentimentCard sentiment={feedbackData.sentiment} />
                  </div>
                </div>

                <div>
                  <TopInsights insights={feedbackData.topInsights} />
                </div>

                <div id="problems-matrix">
                  <ProblemsTable
                    problems={feedbackData.problems}
                    fullAnalysis={feedbackData}
                    onOpenEvidence={(problem: ProblemSolutionItem) => {
                      setSelectedProblemForEvidence(problem);
                      setIsEvidenceModalOpen(true);
                    }}
                  />
                </div>
              </section>
            )}

            <EvidenceModal
              problem={selectedProblemForEvidence}
              isOpen={isEvidenceModalOpen}
              onClose={() => {
                setIsEvidenceModalOpen(false);
                setSelectedProblemForEvidence(null);
              }}
            />
          </div>
        )}
      </div>
    </div>
  );
}
