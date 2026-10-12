# ADR 0004: Niche Report — alohida root layout'dagi statik sahifa

## Kontekst
Muallifga (Roma Rayt) bitta brauzer sahifasidagi hisobot kerak: bitta nisha bo'yicha verdikt, 1–3 sabab va chegarasi oldindan belgilangan 14 kunlik test (`intent/niche-analysis-intent.md`). Hisobot shaxsiy hujjat: unda asoschining shaxsiy cheklovlari bor. Talablar va arxitektura — `intent/spec.md`, ish rejasi — `intent/plan.md`.

Ilovada autentifikatsiya yo'q, root layout esa har bir sahifada "Customer Feedback AI" Header/Footer va `<html lang="en">` ni chiqaradi.

## Yechim
1. **Route groups.** Mavjud `layout.tsx` va `page.tsx` `src/app/(main)/` ga ko'chirildi (URL'lar o'zgarmadi). Hisobot `src/app/(report)/niche-report/` da, o'zining root layout'i bilan: `lang="ru"`, Header/Footer yo'q.
2. **Statik ma'lumot, runtime generatsiyasi yo'q.** Kontent `src/lib/niche-report/report-data.ts` dagi tiplangan obyekt. `validateNicheReport` (V-01…V-12) Vitest'da tekshiriladi: noto'g'ri kontent `npm test` ni buzadi va sahifaga chiqmaydi.
3. **Ko'rinish bayrog'i.** `NICHE_REPORT_ENABLED !== "true"` bo'lsa sahifa `notFound()` qaytaradi; `robots: noindex, nofollow`. Sahifa statik, shuning uchun bayroq build vaqtida o'qiladi.

## Nega (va nimalar rad etildi)
- Rad etildi: LLM orqali runtime generatsiya — tekshirib bo'lmaydigan faktlar, yangi hujum yuzasi, kalitlar va xarajat.
- Rad etildi: ADR 0002 dagi fallback dvigatel — nisha haqidagi evristik verdikt verdiktning yo'qligidan yomonroq. **ADR 0002 ("har doim natija ber") bu sahifaga qo'llanilmaydi:** isbotlanmagan raqamdan ko'ra halol "UNKNOWN" afzal.
- Rad etildi: Markdown/MDX — invariantlarni mashina tekshira olmaydi, ortiqcha bog'liqlik.
- Rad etildi: mavjud root layout ostidagi sahifa — shaxsiy hujjatda mahsulot brendi va noto'g'ri `lang`.
- Rad etildi: autentifikatsiya — bitta shaxsiy sahifa uchun juda og'ir.

## Oqibatlar
- `NICHE_REPORT_ENABLED` **maxfiylik mexanizmi emas**: ommaviy deployda yoqilgan sahifani URL ni bilgan har kim ochadi. Production'da yoqilmaydi; hisobot lokal `npm run dev` orqali ko'riladi.
- Bayroqni o'zgartirish uchun qayta build kerak.
- `(main)` va `(report)` orasidagi o'tish to'liq sahifa yuklanishiga olib keladi (ular orasida havola yo'q).
- Chop etish versiyasi bitta A4 varaqqa sig'ishi kerak (E2E Chromium PDF sahifalarini sanaydi).
