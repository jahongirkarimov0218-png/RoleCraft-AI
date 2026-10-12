import type { Metadata } from "next";
import { notFound } from "next/navigation";
import {
  NICHE_REPORT,
  isNicheReportEnabled,
  weightedScore,
  type Evidence,
  type EvidenceKind,
  type Source,
} from "@/lib/niche-report";
import { PrintButton } from "@/components/niche-report/print-button";
import { cn } from "@/lib/utils";

export const metadata: Metadata = {
  title: NICHE_REPORT.meta.title,
  robots: { index: false, follow: false },
};

const KIND_LABEL: Record<EvidenceKind, string> = {
  fact: "FACT",
  assumption: "ASSUMPTION",
  unknown: "UNKNOWN",
};

const KIND_STYLE: Record<EvidenceKind, string> = {
  fact: "border-status-positive-border bg-status-positive-bg text-status-positive-text",
  assumption: "border-status-neutral-border bg-status-neutral-bg text-status-neutral-text",
  unknown: "border-status-negative-border bg-status-negative-bg text-status-negative-text",
};

function KindBadge({ kind }: { kind: EvidenceKind }) {
  return (
    <span
      className={cn(
        "inline-flex shrink-0 items-center self-start rounded border px-1.5 py-px text-[10px] font-semibold tracking-wide",
        KIND_STYLE[kind]
      )}
    >
      {KIND_LABEL[kind]}
    </span>
  );
}

const sectionClass =
  "print-clean print-break-inside-avoid rounded-lg border border-slate-200/80 bg-white p-4 shadow-card sm:p-6 print:!mt-2";
const h2Class = "text-sm font-semibold tracking-tight text-slate-950";

export default function NicheReportPage() {
  if (!isNicheReportEnabled()) notFound();

  const report = NICHE_REPORT;
  const { meta, verdict, criteria, candidates, test, unknowns } = report;
  const labelOf = (id: string) => candidates.find((c) => c.id === id)?.label ?? id;
  const criterionLabel = (id: string) => criteria.find((c) => c.id === id)?.label ?? id;
  const chosen = candidates.find((c) => c.id === verdict.candidateId)!;

  // Number each distinct piece of evidence once, in matrix order; identical claims share a number.
  const evidenceList: Evidence[] = [];
  const evidenceIndex = new Map<Evidence, number>();
  const keyOf = (e: Evidence) => `${e.kind}|${e.claim}|${e.source?.url ?? ""}`;
  const indexByKey = new Map<string, number>();
  for (const candidate of candidates) {
    for (const score of candidate.scores) {
      for (const evidence of score.evidence) {
        const key = keyOf(evidence);
        if (!indexByKey.has(key)) {
          evidenceList.push(evidence);
          indexByKey.set(key, evidenceList.length);
        }
        evidenceIndex.set(evidence, indexByKey.get(key)!);
      }
    }
  }

  const sources: Source[] = [];
  for (const evidence of evidenceList) {
    // Only https links are rendered, even for drafts where V-08 is not enforced (no javascript:/data: hrefs).
    const source = evidence.source;
    if (evidence.kind === "fact" && source && source.url.startsWith("https://") && !sources.some((s) => s.url === source.url)) {
      sources.push(source);
    }
  }

  return (
    <div className="mx-auto max-w-3xl space-y-4 px-4 py-8 sm:px-6 sm:py-12 print:max-w-none print:space-y-0 print:p-0 print:text-[9pt] print:leading-snug print:[&_.text-sm]:text-[9pt] print:[&_.text-sm]:leading-tight print:[&_.text-xs]:leading-tight print:[&_.text-base]:text-[10pt] print:[&_.mt-3]:mt-1">
      <div className="flex items-start justify-between gap-4">
        <p className="text-xs text-slate-500 tabular-nums">
          {meta.author} · Статус: {meta.status === "draft" ? "черновик" : "финальный"} · {meta.generatedAt} · v
          {meta.version}
        </p>
        <PrintButton />
      </div>

      {meta.status === "draft" && (
        <p
          role="note"
          data-testid="draft-banner"
          className="print-break-inside-avoid rounded-lg border border-status-neutral-border bg-status-neutral-bg px-4 py-3 text-sm text-status-neutral-text"
        >
          Черновик: тестовые данные для проверки вёрстки. Это не вердикт. Реальный отчёт появится после ответов
          на открытые вопросы и исследования с источниками.
        </p>
      )}

      <section data-testid="verdict" aria-labelledby="verdict-title" className={sectionClass}>
        <p className="text-xs font-medium uppercase tracking-wide text-slate-500">Вердикт</p>
        <h1 id="verdict-title" className="mt-1 text-2xl font-bold tracking-tight text-slate-950 print:text-lg">
          {chosen.label}
        </h1>
        <ol className="mt-4 space-y-2 print:mt-1 print:space-y-0.5">
          {verdict.reasons.map((reason, i) => (
            <li key={i} className="flex gap-2 text-sm text-slate-700">
              <span className="font-semibold text-slate-400 tabular-nums">{i + 1}.</span>
              <span>
                {reason.text}{" "}
                {reason.criterionIds.map((id) => (
                  <span
                    key={id}
                    className="ml-1 inline-flex rounded border border-slate-200/80 bg-slate-50 px-1.5 py-px text-[11px] font-medium text-slate-600"
                  >
                    {criterionLabel(id)}
                  </span>
                ))}
              </span>
            </li>
          ))}
        </ol>
      </section>

      <section data-testid="validation-test" aria-labelledby="test-title" className={sectionClass}>
        <h2 id="test-title" className={h2Class}>
          Тест на <span className="tabular-nums">{test.durationDays}</span> дней
        </h2>
        <dl className="mt-3 grid gap-x-4 gap-y-2 text-sm sm:grid-cols-[8rem_1fr] print:mt-1 print:grid-cols-[8rem_1fr] print:gap-y-0 print:text-[9pt]">
          <dt className="text-slate-500">Аудитория</dt>
          <dd className="text-slate-800">{test.audience}</dd>
          <dt className="text-slate-500">Действие</dt>
          <dd className="text-slate-800">{test.action}</dd>
          <dt className="text-slate-500">Метрика</dt>
          <dd className="text-slate-800">{test.metric}</dd>
        </dl>
        <p className="mt-4 text-base font-semibold text-slate-950 print:mt-1">
          Порог: ≥{" "}
          <span data-testid="threshold-value" className="tabular-nums">
            {test.threshold.value}
          </span>{" "}
          <span className="font-normal text-slate-600">{test.threshold.unit}</span>
        </p>
        <p className="mt-1 text-sm text-slate-700">{test.goRule}</p>
        <p className="mt-1 text-sm text-slate-700">
          Иначе → <span className="font-medium text-slate-950">{labelOf(test.fallbackCandidateId)}</span>
        </p>
      </section>

      <section aria-labelledby="matrix-title" className={sectionClass}>
        <h2 id="matrix-title" className={h2Class}>
          Матрица критериев
        </h2>
        <div className="custom-scrollbar mt-3 overflow-x-auto">
          <table className="w-full table-fixed text-left text-sm print:text-[8.5pt] print:[&_td]:py-0.5 print:[&_th]:py-0.5">
            <caption className="sr-only">Оценки ниш по взвешенным критериям, от 1 до 5</caption>
            <thead>
              <tr className="border-b border-slate-200/80 text-xs text-slate-500">
                <th scope="col" className="py-2 pr-3 font-medium">
                  Критерий
                </th>
                <th scope="col" className="w-12 py-2 pr-2 text-right font-medium sm:w-16 sm:pr-3">
                  Вес
                </th>
                {candidates.map((c) => (
                  <th key={c.id} scope="col" className="w-20 py-2 pl-2 text-right font-medium [overflow-wrap:anywhere] sm:w-32 sm:pl-3">
                    {c.label}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {criteria.map((criterion) => (
                <tr key={criterion.id} className="border-b border-slate-100 align-top">
                  <th scope="row" className="py-2 pr-3 font-normal text-slate-800">
                    {criterion.label}
                    <span className="mt-0.5 block text-xs text-slate-500 print:text-[7.5pt]">{criterion.rationale}</span>
                  </th>
                  <td className="py-2 pr-2 text-right text-slate-600 tabular-nums sm:pr-3">
                    {criterion.weight.toFixed(2)}
                  </td>
                  {candidates.map((c) => {
                    const score = c.scores.find((s) => s.criterionId === criterion.id)!;
                    return (
                      <td key={c.id} className="py-2 pl-2 text-right text-slate-900 tabular-nums sm:pl-3">
                        {score.value}
                        <sup className="ml-0.5 text-[10px] text-slate-400">
                          {score.evidence.map((e) => evidenceIndex.get(e)).join(",")}
                        </sup>
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
            <tfoot>
              <tr className="text-slate-950">
                <th scope="row" className="py-2 pr-3 font-semibold">
                  Итого, взвешенно
                </th>
                <td />
                {candidates.map((c) => (
                  <td key={c.id} className="py-2 pl-2 text-right font-semibold tabular-nums sm:pl-3">
                    {weightedScore(c, criteria).toFixed(2)}
                  </td>
                ))}
              </tr>
            </tfoot>
          </table>
        </div>
        <ol className="mt-4 space-y-1.5 text-xs text-slate-600 print:mt-2 print:space-y-0.5 print:text-[7.5pt]">
          {evidenceList.map((evidence, i) => (
            <li key={i} className="flex items-start gap-2">
              <span className="w-5 shrink-0 text-right text-slate-400 tabular-nums">{i + 1}</span>
              <KindBadge kind={evidence.kind} />
              <span>{evidence.claim}</span>
            </li>
          ))}
        </ol>
      </section>

      <section aria-labelledby="unknowns-title" className={sectionClass}>
        <h2 id="unknowns-title" className={h2Class}>
          Что осталось неизвестным
        </h2>
        <ul className="mt-3 list-disc space-y-1 pl-5 text-sm text-slate-700">
          {unknowns.map((item) => (
            <li key={item}>{item}</li>
          ))}
        </ul>
      </section>

      <section aria-labelledby="sources-title" className={sectionClass}>
        <h2 id="sources-title" className={h2Class}>
          Источники
        </h2>
        {sources.length === 0 ? (
          <p className="mt-3 text-sm text-slate-600">
            Источников пока нет: в данных нет утверждений с пометкой FACT.
          </p>
        ) : (
          <ol className="mt-3 list-decimal space-y-1 pl-5 text-sm text-slate-700">
            {sources.map((source) => (
              <li key={source.url}>
                <a
                  href={source.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="focus-ring rounded-sm text-slate-900 underline decoration-slate-300 underline-offset-2 hover:decoration-slate-900"
                >
                  {source.title}
                </a>{" "}
                <span className="text-slate-500">
                  — {source.publisher}, обращение <span className="tabular-nums">{source.accessedAt}</span>
                </span>
              </li>
            ))}
          </ol>
        )}
      </section>
    </div>
  );
}
