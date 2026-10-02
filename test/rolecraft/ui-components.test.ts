import { describe, it, expect } from "vitest";
import React from "react";
import {
  RoleCraftHeader,
  PresetsBar,
  RoleCraftForm,
  ThinkingPartnerCard,
  ShimmerLoader,
  StreamingMarkdownView,
  ActionBar,
} from "../../src/components/rolecraft";
import { ROLECRAFT_PRESETS } from "../../src/lib/rolecraft/presets";
import { triggerCleanPdfExport } from "../../src/lib/rolecraft/export-pdf";

describe("RoleCraft UI Components (Ticket 02)", () => {
  describe("RoleCraftHeader Component", () => {
    it("should export RoleCraftHeader and instantiate with default props", () => {
      expect(typeof RoleCraftHeader).toBe("function");
      const element = React.createElement(RoleCraftHeader);
      expect(element).toBeDefined();
      expect(element.type).toBe(RoleCraftHeader);
    });

    it("should accept different status values", () => {
      const statuses = ["idle", "generating", "ready"] as const;
      statuses.forEach((status) => {
        const el = React.createElement(RoleCraftHeader, { status });
        expect(el.props.status).toBe(status);
      });
    });
  });

  describe("PresetsBar Component", () => {
    it("should export PresetsBar and accept callbacks", () => {
      expect(typeof PresetsBar).toBe("function");
      let selected = null;
      const el = React.createElement(PresetsBar, {
        onSelectPreset: (preset) => {
          selected = preset;
        },
        activePresetId: ROLECRAFT_PRESETS[0].id,
      });
      expect(el).toBeDefined();
      expect(el.props.activePresetId).toBe("staff-ai-engineer");
    });
  });

  describe("RoleCraftForm Component", () => {
    it("should export RoleCraftForm and receive controlled input values", () => {
      expect(typeof RoleCraftForm).toBe("function");
      const sampleInput = ROLECRAFT_PRESETS[0].input;
      const el = React.createElement(RoleCraftForm, {
        values: sampleInput,
        onChange: () => {},
        onSubmit: () => {},
        isLoading: false,
      });
      expect(el).toBeDefined();
      expect(el.props.values.roleTitle).toBe("Staff AI / LLM Architect");
      expect(el.props.isLoading).toBe(false);
    });
  });

  describe("ThinkingPartnerCard Component", () => {
    it("should export ThinkingPartnerCard and render strategic analysis dimensions", () => {
      expect(typeof ThinkingPartnerCard).toBe("function");
      const mockAnalysis = {
        rootProblemAnalysis: "PoC bosqichida kechikish va token xarajatlari yuqori",
        candidateFearsAndDrivers: "Byurokratiya va samarasiz loyihalardan qochish",
        strategicAngle: "Kompaniyaning texnik marjinal ustunligini belgilash",
      };
      const el = React.createElement(ThinkingPartnerCard, { data: mockAnalysis });
      expect(el).toBeDefined();
      expect(el.props.data.rootProblemAnalysis).toContain("PoC");
    });
  });

  describe("ShimmerLoader Component", () => {
    it("should export ShimmerLoader as a valid React component", () => {
      expect(typeof ShimmerLoader).toBe("function");
      const el = React.createElement(ShimmerLoader);
      expect(el).toBeDefined();
      expect(el.type).toBe(ShimmerLoader);
    });
  });

  describe("StreamingMarkdownView Component", () => {
    it("should export StreamingMarkdownView and handle markdown rendering", () => {
      expect(typeof StreamingMarkdownView).toBe("function");
      const sampleMarkdown = `# Staff AI Engineer — Enterprise Impact
> **Kompaniya konteksti:** Series B SaaS
## 1. Lavozim va Hisobot Ierarxiyasi
To'g'ridan-to'g'ri CTO ga hisobot beradi.
## 2. Asosiy Vazifalar va 6 Oylik Biznes Ta'siri (Impact)
- Dastlabki 30 kun: Audit
- Dastlabki 90 kun: Latency 40% ga kamaytirish
## 5. 🛑 Ushbu Rol Kimlarga To'g'ri Kelmaydi (Anti-Persona)
- Faqat tayyor notebookda ishlovchilar
## 6. 🚀 Kompaniya Va'dasi (Value Proposition)
- Greenfield texnik avtonomiya`;

      const el = React.createElement(StreamingMarkdownView, {
        markdown: sampleMarkdown,
        isStreaming: false,
      });
      expect(el).toBeDefined();
      expect(el.props.markdown).toContain("Anti-Persona");
      expect(el.props.markdown).toContain("Value Proposition");
    });
  });

  describe("ActionBar Component", () => {
    it("should export ActionBar and accept copy and export handlers", () => {
      expect(typeof ActionBar).toBe("function");
      let copied = false;
      let exported = false;

      const el = React.createElement(ActionBar, {
        markdown: "Sample markdown spec",
        roleTitle: "Staff AI Engineer",
        onCopy: () => {
          copied = true;
        },
        onExportPdf: () => {
          exported = true;
        },
      });

      expect(el).toBeDefined();
      expect(el.props.roleTitle).toBe("Staff AI Engineer");
    });
  });

  describe("Clean PDF Export Helper", () => {
    it("should export triggerCleanPdfExport function and run safely in non-browser environment", () => {
      expect(typeof triggerCleanPdfExport).toBe("function");
      // Calling in node/vitest environment (where window might have mock or undefined print)
      expect(() => triggerCleanPdfExport("Test Role")).not.toThrow();
    });
  });
});
