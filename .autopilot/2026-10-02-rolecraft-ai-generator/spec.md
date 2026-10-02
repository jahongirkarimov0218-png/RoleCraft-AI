# Спецификация: RoleCraft AI — Enterprise Job Description Generator

> Версия: 1.0.0 · Дата: 2026-10-02 · Режим: full deep polish
> Основание: `2026-10-02-brief.md` · Манифест: `manifest.md` (R01–R25i)

---

## 1. Executive Summary & Vision

**RoleCraft AI** — bu /prompt-nenujna falsafasi va Lou Adler'ning "Performance-based Hiring" metodologiyasiga asoslangan, yuqori konversiyali, biznes ta’siriga (Impact) ega bo‘lgan va jahon darajasidagi dizayn injiniringiga ega bo‘lgan Enterprise Job Description Generator platformasi.

An'anaviy HR e'lonlari quruq klishelarga ("dinamik rivojlanayotgan jamoa", "stressga chidamli", "5+ yillik tajriba") to'la bo'lib, eng kuchli mutaxassislarni (A-players) cho'chitadi va zaif oqimni yuzaga keltiradi. RoleCraft AI ushbu muammoni tubdan hal qiladi:
1. **Thinking Partner yondashuvi:** Lavozimdan avval kompaniyaning eng og'riqli biznes muammosini (PoC tuzog'i, masshtablash blokeri, xarajatlar) va kuchli nomzodning ichki qo'rquvini (byurokratiya, mikromenejment) modellashtiradi.
2. **Outcome-Driven (Jarayon emas, Biznes Natijasi):** Dastlabki 6 oyda hal qilinishi shart bo'lgan aniq, o'lchanadigan biznes yutuqlarini belgilaydi.
3. **Anti-Persona (🛑) va Value Proposition (🚀):** Rol kimlarga to'g'ri kelmasligini ochiq aytish orqali saralash sifatini oshiradi va nomzod qo'rquvini sindiruvchi real erkinlik va masshtabni taqdim etadi.

---

## 2. /prompt-nenujna & Thinking Partner Arxitekturasi

- **Anti-Template Philosophy:** Standart 4 ta blokdan iborat zerikarli shablonlar qat'iyan taqiqlanadi. Har bir vakansiya biznes konteksti va dardi atrofida organik sintez qilinadi.
- **Thinking Partner Tahlili:** Generator foydalanuvchiga nafaqat tayyor matnni, balki fon rejimida biznes dardini va nomzod psixologiyasini tahlil qiluvchi "Strategic Alignment Matrix"ni namoyish etadi:
  - *Biznes Dardi (Root Cause):* Nima uchun bu rol aynan hozir zarur?
  - *A-Player Psixologiyasi:* Bu roldagi kuchli mutaxassis nimadan qo'rqadi (red flags) va nimaga intiladi (green flags)?
  - *Kontekst > Buyruqlar:* Nomzod nima uchun kompaniyaga qo'shilishi kerakligi (The "Why") birinchi o'ringa qo'yiladi.

---

## 3. Lou Adler Framework & Anti-Slop Qoidalari

- **Anti-Slop Lug'ati:** Matndan quyidagi klishelar 100% chiqarib tashlanadi yoki filtrlardan o'tkaziladi:
  - ❌ "Dinamik jamoa", "Stressga chidamlilik", "Faol xodim", "Ahil oila"
  - ❌ "X yillik tajriba talab qilinadi" (o'rniga: "Amalda X masshtabni bajargan bo'lishi shart")
- **6 Oylik Biznes Ta'siri (Impact Metrics):**
  - Vazifalar "kod yozish" yoki "yig'ilish qilish" emas, balki "10x yuklamada kechikishni 40% ga qisqartirish", "Q2 yakunigacha ARR o'sishiga 20% hissa qo'shish" kabi o'lchanadigan natijalar shaklida beriladi.
- **🛑 Anti-Persona Bloki:**
  - "Bu rol kimlarga to'g'ri kelmaydi" bo'limi nomzodlar self-filter qilishiga yordam beradi (masalan: aniq yo'riqnoma kutadiganlar, noaniqlikda ishlay olmaydiganlar uchun emas).
- **🚀 Value Proposition Bloki:**
  - Kompaniya va'dasi: real avtonomiya, arxitektura mustaqilligi, to'g'ridan-to'g'ri C-level bilan muloqot.

---

## 4. Vizual Dizayn va Emil Kowalski Muhandisligi (3 Design Skills)

1. **Emil Kowalski Design Engineering:**
   - Har bir mikromotion o'ylab qilingan. Hech qachon `transition: all` ishlatilmaydi.
   - Aniq CSS xususiyatlari: `transition: transform 150ms cubic-bezier(0.16, 1, 0.3, 1), opacity 150ms ease-out, border-color 150ms ease-out`.
   - Taktil sezgirlik: tugmalar uchun `:active { transform: scale(0.98); }`.
   - Popover va modallar ochilishi: `scale(0.96)` va `opacity: 0` dan silliq spring/ease-out bilan.
2. **Impeccable Design Standards:**
   - Qat'iy vizual ierarxiya, 8px ritmik grid, Geist / Inter shriftlari, `tabular-nums` raqamlar uchun.
   - Whitespace muvozanati, form inputlari va natija paneli nisbati.
   - Shimmer Skeletonlar: Kontekstual, silliq gradient harakatiga ega shimmerlar.
3. **Taste & Restraint:**
   - Slate & Zinc neytral tonlari, 1px nozik subyektiv chegaralar (`border-slate-800/40`), zamonaviy sof minimalizm. Arzon neon va ortiqcha gradientlardan xoli.

---

## 5. Tizim Tuzilishi va Komponentlar Ierarxiyasi

```
src/
├── app/
│   ├── api/rolecraft/generate/route.ts  # POST SSE Streaming / Fallback Route Handler
│   ├── globals.css                      # Tailwind, print styles, taktil motion
│   ├── layout.tsx                       # Metadata & fonts
│   └── page.tsx                         # Asosiy RoleCraft AI ekrani
├── components/
│   ├── rolecraft/
│   │   ├── header.tsx                   # Enterprise navigatsiya, status indikator
│   │   ├── presets-bar.tsx              # 4 ta sanoat keysi (AI, Fintech, SaaS, Platform)
│   │   ├── rolecraft-form.tsx           # Kirish formasi (Lavozim, Kontekst, Dard, Stak)
│   │   ├── thinking-partner-card.tsx    # Thinking Partner: Dard & A-player tahlili
│   │   ├── streaming-markdown-view.tsx  # Formatlangan, silliq Markdown oqimi
│   │   ├── action-bar.tsx               # 1-klik Nusxalash va Toza PDF Export
│   │   └── shimmer-loader.tsx           # Kontekstual yuklanish holatlari
│   └── ...
├── lib/
│   └── rolecraft/
│       ├── types.ts                     # Qat'iy TypeScript interfeyslari
│       ├── presets.ts                   # 4 ta Enterprise Benchmark keyslari
│       ├── anti-slop-filter.ts          # Klishelarni tekshirish va tozalash
│       ├── prompt-nenujna-engine.ts     # Semantik tahlil va generator
│       └── export-pdf.ts                # Print / Clean PDF eksport yordamchisi
```

---

## 6. Kirish va Chiqish Kontrakti

### Kirish Ma'lumotlari (`RoleCraftInput`):
- `roleTitle`: string (masalan: "Staff AI Engineer", "Head of Growth")
- `companyContext`: string (masalan: "Series B B2B SaaS, 60 kishi, 10x ARR o'sish bosqichi")
- `coreBusinessPain`: string (masalan: "AI prototipi PoC bosqichida tiqilib qolgan, productionga chiqa olmayapti")
- `techStackAndSkills`: string (masalan: "Python, FastAPI, Next.js, LangChain/LlamaIndex, PostgreSQL, pgvector")

### Chiqish Ma'lumotlari (`RoleCraftOutput`):
- `thinkingPartner`:
  - `rootProblemAnalysis`: string
  - `candidateFearsAndDrivers`: string
  - `strategicAngle`: string
- `jobDescriptionMarkdown`: string (Tarkibi):
  - `# [Lavozim] — [Kompaniya Biznes Missiyasi]`
  - `## 1. Lavozim va Hisobot Ierarxiyasi`
  - `## 2. Asosiy Vazifalar va 6 Oylik Biznes Ta'siri (Impact)`
  - `## 3. Talablar va Amaliy Natijalar (Track Record)`
  - `## 4. Texnik va Amaliy Ko'nikmalar`
  - `## 5. 🛑 Ushbu Rol Kimlarga To'g'ri Kelmaydi (Anti-Persona)`
  - `## 6. 🚀 Kompaniya Va'dasi (Value Proposition)`

---

## 7. Testlash va Sifat Kafolati (Vitest & Playwright)

1. **Vitest Unit Testlar:**
   - Anti-slop filtrlari to'g'ri ishlashini tekshirish.
   - Thinking Partner semantik generatorining kontraktga to'liq mosligini tekshirish.
   - Presetlarning to'g'ri to'ldirilishi va yuklanishi.
2. **Playwright E2E Testlar (`e2e/rolecraft.spec.ts`):**
   - Formani to'ldirish va generatsiyani boshlash.
   - Preset tugmasini bosganda formaning bir zumda to'ldirilishi.
   - Streaming Markdown render qilinishi va bo'limlar mavjudligi.
   - 1-klikli nusxalash (taktil ko'rsatkich va clipboard) tekshiruvi.
   - PDF export / print dialog chaqiruvi.
   - Mobil ekranda to'g'ri ko'rinish (375px) va klaviatura bilan boshqarish.
