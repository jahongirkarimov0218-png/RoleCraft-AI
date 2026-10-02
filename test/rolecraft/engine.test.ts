import { describe, it, expect } from 'vitest';
import { ROLECRAFT_PRESETS } from '../../src/lib/rolecraft/presets';
import { cleanAntiSlopText, SLOP_DICTIONARY } from '../../src/lib/rolecraft/anti-slop-filter';
import { generateRoleCraftOutcome } from '../../src/lib/rolecraft/prompt-nenujna-engine';
import { POST } from '../../src/app/api/rolecraft/generate/route';

describe('RoleCraft Presets', () => {
  it('should export exactly 4 enterprise benchmarks covering all required sectors', () => {
    expect(ROLECRAFT_PRESETS).toHaveLength(4);
    
    const ids = ROLECRAFT_PRESETS.map(p => p.id);
    expect(ids).toContain('staff-ai-engineer');
    expect(ids).toContain('head-of-growth');
    expect(ids).toContain('lead-product-designer');
    expect(ids).toContain('director-engineering');

    for (const preset of ROLECRAFT_PRESETS) {
      expect(preset.name.length).toBeGreaterThan(5);
      expect(preset.badge.length).toBeGreaterThan(2);
      expect(preset.input.roleTitle.length).toBeGreaterThan(3);
      expect(preset.input.companyContext.length).toBeGreaterThan(10);
      expect(preset.input.coreBusinessPain.length).toBeGreaterThan(10);
      expect(preset.input.techStackAndSkills.length).toBeGreaterThan(5);
    }
  });
});

describe('Anti-Slop Filter', () => {
  it('should have at least 15 distinct toxic HR cliché definitions', () => {
    expect(SLOP_DICTIONARY.length).toBeGreaterThanOrEqual(15);
  });

  it('should detect and replace toxic clichés with outcome-driven phrases in Russian and Uzbek', () => {
    const dirtyText = 'Bizning dinamik jamoa uchun 5+ yillik tajriba va stressga chidamlilik talab qilinadi. Shuningdek pechene va kofe beriladi.';
    const result = cleanAntiSlopText(dirtyText);

    expect(result.replacedPhrases.length).toBeGreaterThanOrEqual(3);
    expect(result.cleaned).not.toContain('dinamik jamoa');
    expect(result.cleaned).not.toContain('5+ yillik tajriba');
    expect(result.cleaned).not.toContain('stressga chidamlilik');
    expect(result.cleaned).not.toContain('pechene va kofe');
  });

  it('should handle clean outcome-driven text without modifications', () => {
    const cleanText = 'Biznes maqsadi: LLM kechikishini 40% ga qisqartirish va 99.9% uptime ta\'minlash.';
    const result = cleanAntiSlopText(cleanText);

    expect(result.replacedPhrases).toHaveLength(0);
    expect(result.cleaned).toBe(cleanText);
  });
});

describe('Prompt-Nenujna & Lou Adler Semantic Engine', () => {
  it('should generate complete RoleCraftOutput for all 4 benchmark presets', async () => {
    for (const preset of ROLECRAFT_PRESETS) {
      const output = await generateRoleCraftOutcome(preset.input);

      // Verify Thinking Partner structure
      expect(output.thinkingPartner).toBeDefined();
      expect(output.thinkingPartner.rootProblemAnalysis.length).toBeGreaterThan(20);
      expect(output.thinkingPartner.candidateFearsAndDrivers.length).toBeGreaterThan(20);
      expect(output.thinkingPartner.strategicAngle.length).toBeGreaterThan(20);

      // Verify Lou Adler Outcome-driven Markdown sections
      const md = output.jobDescriptionMarkdown;
      expect(md).toContain('## 1. Lavozim va Hisobot Ierarxiyasi');
      expect(md).toContain('## 2. Asosiy Vazifalar va 6 Oylik Biznes Ta\'siri (Impact)');
      expect(md).toContain('## 3. Talablar va Amaliy Natijalar (Track Record)');
      expect(md).toContain('## 4. Texnik va Amaliy Ko\'nikmalar');
      expect(md).toContain('## 5. 🛑 Ushbu Rol Kimlarga To\'g\'ri Kelmaydi (Anti-Persona)');
      expect(md).toContain('## 6. 🚀 Kompaniya Va\'dasi (Value Proposition)');

      // Verify Anti-Slop in output
      expect(md).not.toContain('dinamik jamoa');
      expect(md).not.toContain('stressga chidamlilik');
      expect(md).not.toContain('pechene va kofe');
      expect(md).not.toContain('5+ yillik tajriba');

      // Verify Raw Metrics
      expect(output.rawMetrics.impactDeliverablesCount).toBeGreaterThanOrEqual(3);
      expect(output.rawMetrics.antiPersonaCriteriaCount).toBeGreaterThanOrEqual(2);
      expect(output.rawMetrics.readabilityScore).toBeGreaterThanOrEqual(60);
    }
  });

  it('should synthesize personalized response for custom non-preset input', async () => {
    const customInput = {
      roleTitle: 'Principal Security Architect',
      companyContext: 'Series C MedTech startup, 150 employees, HIPAA compliance and zero-trust migration',
      coreBusinessPain: 'Legacy patient data pipelines need zero-trust encryption without increasing query latency',
      techStackAndSkills: 'Rust, Go, AWS KMS, HashiCorp Vault, Kubernetes, eBPF, OIDC',
    };

    const output = await generateRoleCraftOutcome(customInput);
    expect(output.thinkingPartner.rootProblemAnalysis).toContain('zero-trust');
    expect(output.jobDescriptionMarkdown).toContain('Principal Security Architect');
    expect(output.jobDescriptionMarkdown).toContain('## 5. 🛑 Ushbu Rol Kimlarga To\'g\'ri Kelmaydi (Anti-Persona)');
    expect(output.jobDescriptionMarkdown).toContain('## 6. 🚀 Kompaniya Va\'dasi (Value Proposition)');
  });
});

describe('POST /api/rolecraft/generate Route Handler', () => {
  it('should return 400 when input fields are missing or below minimum length', async () => {
    // Missing role title
    const req1 = new Request('http://localhost:3000/api/rolecraft/generate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        roleTitle: 'AB',
        companyContext: 'Valid company context long enough',
        coreBusinessPain: 'Valid business pain long enough',
        techStackAndSkills: 'Valid stack',
      }),
    });
    const res1 = await POST(req1);
    expect(res1.status).toBe(400);
    const body1 = await res1.json();
    expect(body1.error).toBeDefined();

    // Short company context
    const req2 = new Request('http://localhost:3000/api/rolecraft/generate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        roleTitle: 'Senior Dev',
        companyContext: 'Too short',
        coreBusinessPain: 'Valid business pain long enough',
        techStackAndSkills: 'Valid stack',
      }),
    });
    const res2 = await POST(req2);
    expect(res2.status).toBe(400);
  });

  it('should return 200 with JSON payload when non-streaming request is sent', async () => {
    const validPreset = ROLECRAFT_PRESETS[0];
    const req = new Request('http://localhost:3000/api/rolecraft/generate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(validPreset.input),
    });

    const res = await POST(req);
    expect(res.status).toBe(200);
    const data = await res.json();
    expect(data.success).toBe(true);
    expect(data.data.thinkingPartner).toBeDefined();
    expect(data.data.jobDescriptionMarkdown).toContain('Staff AI');
  });

  it('should return 200 with SSE stream when text/event-stream header or stream:true is requested', async () => {
    const validPreset = ROLECRAFT_PRESETS[1];
    const req = new Request('http://localhost:3000/api/rolecraft/generate', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Accept': 'text/event-stream',
      },
      body: JSON.stringify({ ...validPreset.input, stream: true }),
    });

    const res = await POST(req);
    expect(res.status).toBe(200);
    expect(res.headers.get('content-type')).toContain('text/event-stream');

    const reader = res.body?.getReader();
    expect(reader).toBeDefined();
    if (reader) {
      let chunksReceived = 0;
      let fullText = '';
      const decoder = new TextDecoder();
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        chunksReceived++;
        fullText += decoder.decode(value);
      }
      expect(chunksReceived).toBeGreaterThan(0);
      expect(fullText).toContain('data:');
    }
  });
});



