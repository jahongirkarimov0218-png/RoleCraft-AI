import { RoleCraftPreset } from './types';

export const ROLECRAFT_PRESETS: RoleCraftPreset[] = [
  {
    id: 'staff-ai-engineer',
    name: 'Staff AI / LLM Architect',
    badge: 'GenAI Platform',
    input: {
      roleTitle: 'Staff AI / LLM Architect',
      companyContext: 'Series B GenAI platform, 65 kishi, 12x oylik so\'rovlar o\'sishi, 30M$ investitsiya jalb qilingan enterprise SaaS ekotizimi',
      coreBusinessPain: 'Mavjud prototip va MVP PoC tuzog\'ida qolib ketgan: LLM kechikishi (latency > 2.5s), token xarajatlari yuqori, production darajasidagi eval/guardrails yo\'q, yuqori yuklamada xatoliklar ko\'paymoqda',
      techStackAndSkills: 'Python 3.12, FastAPI, LangGraph, vLLM, PostgreSQL, pgvector, Redis, Kubernetes, AWS, Semantic Caching, RAG evaluation',
    },
  },
  {
    id: 'head-of-growth',
    name: 'Head of Growth Engineering',
    badge: 'Hyper-growth SaaS',
    input: {
      roleTitle: 'Head of Growth Engineering',
      companyContext: 'Post-PMF B2B SaaS platformasi, 45 kishi, oyiga 250k faol foydalanuvchi, Series A dan Series B ga o\'tish bosqichida',
      coreBusinessPain: 'Konversiya voronkasining sign-up dan faol onboardinggacha bo\'lgan qismida 38% yo\'qotish kuzatilmoqda. A/B tajribalar sikli sekin (2 hafta), mahsulot va marketing ma\'lumotlari o\'rtasida integratsiya uzilgan',
      techStackAndSkills: 'Next.js, TypeScript, PostgreSQL, Segment, Mixpanel, Statsig, Growth Loops, Viral Mechanics, Reverse ETL, Stripe Billing',
    },
  },
  {
    id: 'lead-product-designer',
    name: 'Lead Product Designer (Design Systems)',
    badge: 'Enterprise Design',
    input: {
      roleTitle: 'Lead Product Designer (Design Systems)',
      companyContext: 'Enterprise Multi-product SaaS, 120+ kishi, 4 ta mustaqil mahsulot jamoasi, global enterprise mijozlar portfeli',
      coreBusinessPain: 'Mahsulotlar o\'rtasida UI fragmentatsiyasi va nomutanosiblik 3 barobar ortgan. Dizaynerlar va frontend muhandislari har bir yangi funksiyada g\'ildirakni qayta kashf qilmoqda, relizlar 40% ga sekinlashgan',
      techStackAndSkills: 'Figma Tokens, Design System Architecture, Auto-layout, Zeroheight, Storybook, React/Tailwind, WCAG 2.1 AAA, Micro-interactions',
    },
  },
  {
    id: 'director-engineering',
    name: 'Engineering Director (Platform & Reliability)',
    badge: 'High-load Fintech',
    input: {
      roleTitle: 'Engineering Director (Platform & Reliability)',
      companyContext: 'High-load Fintech neobank, kuniga 5M+ tranzaksiya, 24/7 moliyaviy regulyatsiyalar va PCI-DSS xavfsizlik talablari',
      coreBusinessPain: 'Eski monolit arxitektura tranzaksiyalar o\'sishida kutilmagan to\'xtashlarga (downtime) sabab bo\'lmoqda. Zero-downtime migratsiyasi, mikroservislar ajratilishi va 99.99% SLO ga erishish talab etiladi',
      techStackAndSkills: 'Go / Java, Kafka, Kubernetes, Distributed Systems, PostgreSQL HA, AWS Multi-region, Terraform, PCI-DSS, SLO/SLI Management',
    },
  },
];
