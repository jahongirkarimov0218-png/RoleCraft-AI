"use client";

import React, { useMemo } from "react";
import { ShieldAlert, Rocket, CheckCircle2, Calendar, Sparkles } from "lucide-react";

export interface StreamingMarkdownViewProps {
  markdown: string;
  isStreaming?: boolean;
}

interface ParsedSection {
  title: string;
  level: number;
  contentLines: string[];
  type: "default" | "anti-persona" | "value-prop" | "impact" | "track-record";
}

function parseMarkdownIntoSections(markdown: string): {
  headerLines: string[];
  sections: ParsedSection[];
} {
  const lines = markdown.split("\n");
  const headerLines: string[] = [];
  const sections: ParsedSection[] = [];

  let currentSection: ParsedSection | null = null;
  let inHeader = true;

  for (const line of lines) {
    if (line.startsWith("## ")) {
      inHeader = false;
      const title = line.replace(/^##\s+/, "").trim();
      let type: ParsedSection["type"] = "default";

      if (title.includes("Anti-Persona") || title.includes("🛑")) {
        type = "anti-persona";
      } else if (title.includes("Value Proposition") || title.includes("🚀") || title.includes("Va'dasi")) {
        type = "value-prop";
      } else if (title.includes("Biznes Ta'siri") || title.includes("Impact")) {
        type = "impact";
      } else if (title.includes("Track Record") || title.includes("Talablar")) {
        type = "track-record";
      }

      currentSection = {
        title,
        level: 2,
        contentLines: [],
        type,
      };
      sections.push(currentSection);
    } else if (inHeader) {
      headerLines.push(line);
    } else if (currentSection) {
      currentSection.contentLines.push(line);
    }
  }

  return { headerLines, sections };
}

function renderFormattedText(text: string) {
  // Simple inline parser for **bold**, `code`, *italic*
  const parts: React.ReactNode[] = [];
  let remaining = text;
  let keyIndex = 0;

  while (remaining.length > 0) {
    const boldMatch = remaining.match(/\*\*(.*?)\*\*/);
    const codeMatch = remaining.match(/`([^`]+)`/);

    let firstMatchIndex = -1;
    let matchType: "bold" | "code" | null = null;
    let matchLength = 0;
    let matchContent = "";

    if (boldMatch && boldMatch.index !== undefined) {
      firstMatchIndex = boldMatch.index;
      matchType = "bold";
      matchLength = boldMatch[0].length;
      matchContent = boldMatch[1];
    }

    if (codeMatch && codeMatch.index !== undefined) {
      if (firstMatchIndex === -1 || codeMatch.index < firstMatchIndex) {
        firstMatchIndex = codeMatch.index;
        matchType = "code";
        matchLength = codeMatch[0].length;
        matchContent = codeMatch[1];
      }
    }

    if (firstMatchIndex === -1 || matchType === null) {
      parts.push(remaining);
      break;
    }

    if (firstMatchIndex > 0) {
      parts.push(remaining.slice(0, firstMatchIndex));
    }

    if (matchType === "bold") {
      parts.push(
        <strong key={`b-${keyIndex++}`} className="font-semibold text-slate-900">
          {matchContent}
        </strong>
      );
    } else if (matchType === "code") {
      parts.push(
        <code
          key={`c-${keyIndex++}`}
          className="rounded bg-slate-100 px-1 py-0.5 font-mono text-[11px] text-slate-800 border border-slate-200"
        >
          {matchContent}
        </code>
      );
    }

    remaining = remaining.slice(firstMatchIndex + matchLength);
  }

  return parts;
}

export function StreamingMarkdownView({
  markdown,
  isStreaming = false,
}: StreamingMarkdownViewProps) {
  const { headerLines, sections } = useMemo(() => {
    return parseMarkdownIntoSections(markdown || "");
  }, [markdown]);

  if (!markdown) return null;

  return (
    <div className="print-clean rounded-xl border border-slate-200/90 bg-white p-6 shadow-2xs space-y-6">
      {/* Header / Meta Block */}
      <div className="space-y-3 border-b border-slate-200 pb-5">
        {headerLines.map((line, idx) => {
          const trimmed = line.trim();
          if (trimmed.startsWith("# ")) {
            return (
              <h1
                key={idx}
                className="text-xl sm:text-2xl font-bold tracking-tight text-slate-950"
              >
                {trimmed.replace(/^#\s+/, "")}
              </h1>
            );
          }
          if (trimmed.startsWith("> ")) {
            return (
              <blockquote
                key={idx}
                className="border-l-2 border-slate-300 pl-3 text-xs text-slate-600 italic bg-slate-50/50 py-1 rounded-r"
              >
                {renderFormattedText(trimmed.replace(/^>\s+/, ""))}
              </blockquote>
            );
          }
          if (trimmed === "---") {
            return null;
          }
          if (!trimmed) {
            return null;
          }
          return (
            <p key={idx} className="text-xs text-slate-600 leading-relaxed">
              {renderFormattedText(trimmed)}
            </p>
          );
        })}
      </div>

      {/* Sections */}
      <div className="space-y-6">
        {sections.map((section, sIdx) => {
          // Special View: Anti-Persona
          if (section.type === "anti-persona") {
            return (
              <div
                key={sIdx}
                className="rounded-xl border border-rose-200 bg-rose-50/30 p-5 space-y-3 print-break-inside-avoid"
              >
                <div className="flex items-center gap-2">
                  <div className="flex h-6 w-6 items-center justify-center rounded-md bg-rose-600 text-white">
                    <ShieldAlert className="h-3.5 w-3.5" />
                  </div>
                  <h3 className="text-sm font-semibold text-rose-950">
                    {section.title}
                  </h3>
                  <span className="rounded-full bg-rose-100 border border-rose-200 px-2 py-0.5 text-[10px] font-semibold text-rose-800 ml-auto">
                    Self-Filter Gate
                  </span>
                </div>
                <div className="space-y-2 text-xs leading-relaxed text-rose-900/90 pl-1">
                  {section.contentLines.map((line, lIdx) => {
                    const trimmed = line.trim();
                    if (!trimmed) return null;
                    if (trimmed.startsWith("- ")) {
                      return (
                        <div key={lIdx} className="flex items-start gap-2">
                          <span className="text-rose-500 font-bold shrink-0 mt-0.5">&times;</span>
                          <span>{renderFormattedText(trimmed.replace(/^-\s+/, ""))}</span>
                        </div>
                      );
                    }
                    return <p key={lIdx}>{renderFormattedText(trimmed)}</p>;
                  })}
                </div>
              </div>
            );
          }

          // Special View: Value Proposition
          if (section.type === "value-prop") {
            return (
              <div
                key={sIdx}
                className="rounded-xl border border-emerald-200 bg-emerald-50/30 p-5 space-y-3 print-break-inside-avoid"
              >
                <div className="flex items-center gap-2">
                  <div className="flex h-6 w-6 items-center justify-center rounded-md bg-emerald-600 text-white">
                    <Rocket className="h-3.5 w-3.5" />
                  </div>
                  <h3 className="text-sm font-semibold text-emerald-950">
                    {section.title}
                  </h3>
                  <span className="rounded-full bg-emerald-100 border border-emerald-200 px-2 py-0.5 text-[10px] font-semibold text-emerald-800 ml-auto">
                    A-Player Promise
                  </span>
                </div>
                <div className="space-y-2 text-xs leading-relaxed text-emerald-900/90 pl-1">
                  {section.contentLines.map((line, lIdx) => {
                    const trimmed = line.trim();
                    if (!trimmed) return null;
                    if (trimmed.startsWith("- ")) {
                      return (
                        <div key={lIdx} className="flex items-start gap-2">
                          <CheckCircle2 className="h-3.5 w-3.5 text-emerald-600 shrink-0 mt-0.5" />
                          <span>{renderFormattedText(trimmed.replace(/^-\s+/, ""))}</span>
                        </div>
                      );
                    }
                    return <p key={lIdx}>{renderFormattedText(trimmed)}</p>;
                  })}
                </div>
              </div>
            );
          }

          // Special View: 6-Month Business Impact
          if (section.type === "impact") {
            return (
              <div
                key={sIdx}
                className="rounded-xl border border-slate-200 bg-slate-50/40 p-5 space-y-3 print-break-inside-avoid"
              >
                <div className="flex items-center gap-2">
                  <div className="flex h-6 w-6 items-center justify-center rounded-md bg-indigo-600 text-white">
                    <Calendar className="h-3.5 w-3.5" />
                  </div>
                  <h3 className="text-sm font-semibold text-slate-950">
                    {section.title}
                  </h3>
                  <span className="rounded-full bg-indigo-50 border border-indigo-200 px-2 py-0.5 text-[10px] font-semibold text-indigo-700 ml-auto">
                    Lou Adler Outcome Matrix
                  </span>
                </div>
                <div className="space-y-2.5 text-xs leading-relaxed text-slate-700">
                  {section.contentLines.map((line, lIdx) => {
                    const trimmed = line.trim();
                    if (!trimmed) return null;
                    if (trimmed.startsWith("- ")) {
                      const itemText = trimmed.replace(/^-\s+/, "");
                      return (
                        <div
                          key={lIdx}
                          className="flex items-start gap-2 rounded-lg border border-slate-200/80 bg-white p-3 shadow-2xs"
                        >
                          <div className="h-1.5 w-1.5 rounded-full bg-indigo-500 mt-1.5 shrink-0" />
                          <div>{renderFormattedText(itemText)}</div>
                        </div>
                      );
                    }
                    return <p key={lIdx} className="text-slate-600">{renderFormattedText(trimmed)}</p>;
                  })}
                </div>
              </div>
            );
          }

          // Default Sections (Hierarchy, Track Record, Tech Stack, etc.)
          return (
            <div key={sIdx} className="space-y-2.5 print-break-inside-avoid">
              <h3 className="text-sm font-bold text-slate-950 border-b border-slate-100 pb-1.5 flex items-center gap-2">
                <span className="flex h-1.5 w-1.5 rounded-full bg-slate-800" />
                {section.title}
              </h3>
              <div className="space-y-1.5 text-xs text-slate-600 leading-relaxed pl-1">
                {section.contentLines.map((line, lIdx) => {
                  const trimmed = line.trim();
                  if (!trimmed) return null;
                  if (trimmed.startsWith("- ")) {
                    return (
                      <div key={lIdx} className="flex items-start gap-2">
                        <span className="text-slate-400 font-bold shrink-0 mt-0.5">&bull;</span>
                        <span>{renderFormattedText(trimmed.replace(/^-\s+/, ""))}</span>
                      </div>
                    );
                  }
                  if (trimmed.startsWith("*") && trimmed.endsWith("*")) {
                    return (
                      <p key={lIdx} className="text-[11px] text-slate-400 italic pt-2">
                        {trimmed.replace(/^\*|\*$/g, "")}
                      </p>
                    );
                  }
                  return <p key={lIdx}>{renderFormattedText(trimmed)}</p>;
                })}
              </div>
            </div>
          );
        })}
      </div>

      {/* Streaming blinking cursor */}
      {isStreaming && (
        <div className="flex items-center gap-1.5 text-xs text-slate-500 font-mono pt-2 no-print">
          <span className="inline-block h-3.5 w-2 animate-pulse bg-slate-900" />
          <span>Matn uzluksiz oqimda shakllanmoqda...</span>
        </div>
      )}
    </div>
  );
}

export default StreamingMarkdownView;
