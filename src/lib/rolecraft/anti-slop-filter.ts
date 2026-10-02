export interface SlopRule {
  id: string;
  label: string;
  regex: RegExp;
  replacement: string;
  explanation: string;
}

export const SLOP_DICTIONARY: SlopRule[] = [
  {
    id: 'dynamic-team',
    label: 'Dinamik jamoa / Динамичный коллектив',
    regex: /(?:dinamik(?:\s+rivojlanayotgan)?\s+jamoa|динамичн(?:ый|ая|ое)\s+(?:коллектив|команда|компания)|fast-paced\s+(?:dynamic\s+)?environment)/gi,
    replacement: 'tezkor avtonom qarorlar va o\'lchanadigan natijalar muhiti',
    explanation: 'Bo\'sh sifat so\'z o\'rniga real ish madaniyati va natijaga yo\'naltirilganlik ko\'rsatildi',
  },
  {
    id: 'stress-resistance',
    label: 'Stressga chidamlilik / Стрессоустойчивость',
    regex: /(?:stressga\s+chidamli(?:lik)?|стрессоустойчивост(?:ь|и)|стрессоустойчивый|high\s+stress\s+tolerance)/gi,
    replacement: 'aniq operatsion chegaralar va noaniqlik sharoitida tizimli muammolarni hal qilish',
    explanation: 'Toksik yuklama o\'rniga tizimli yondashuv va aniq jarayonlar ko\'rsatildi',
  },
  {
    id: 'cookies-and-coffee',
    label: 'Pechene va kofe / Печеньки и кофе',
    regex: /(?:pechene\s+va\s+kofe|pechanye\s+va\s+kofe|печеньки\s+(?:и\s+кофе|чай)|чай,\s*кофе,\s*печеньки|ping-pong\s+(?:and|&)\s+snacks|free\s+snacks)/gi,
    replacement: 'chuqur diqqatni jamlash (deep work) uchun ergonomik uskunalar va professional erkinlik',
    explanation: 'Arzon maishiy va\'dalar o\'rniga professional muhit va ish qurollari belgilandi',
  },
  {
    id: 'years-of-experience',
    label: '5+ yillik tajriba / 5+ лет опыта',
    regex: /(?:\d+\+?\s*(?:yillik\s+tajriba|yil\s+tajriba|лет(?:\s+опыта)?|года\s+опыта|years(?:\s+of)?\s+experience))/gi,
    replacement: 'amalda murakkab tizimlarni noldan production masshtabiga olib chiqqan tasdiqlangan tajriba',
    explanation: 'Yillar soni emas, balki erishilgan biznes va texnik natijalar ko\'rsatildi',
  },
  {
    id: 'active-position',
    label: 'Faol xodim / Активная жизненная позиция',
    regex: /(?:faol\s+hayotiy\s+pozitsiya|faol\s+xodim|активн(?:ая|ый)\s+(?:жизненная\s+позиция|сотрудник)|energetic\s+self-starter)/gi,
    replacement: 'tashabbuskorlik va loyihaning to\'liq egasi (full ownership) sifatida javobgarlikni olish',
    explanation: 'Mavhum faollik o\'rniga loyiha uchun to\'liq javobgarlik (ownership) talabi qo\'yildi',
  },
  {
    id: 'like-a-family',
    label: 'Ahil oila / Дружная семья',
    regex: /(?:ahil\s+oila|biz\s+bir\s+oilamiz|дружн(?:ая|ый)\s+семья|мы\s+одна\s+семья|we\s+are\s+like\s+a\s+family)/gi,
    replacement: 'yuqori standartlarga ega, bir-birini professional qo\'llab-quvvatlovchi yetuk muhandislik jamoasi',
    explanation: 'Shaxsiy chegaralarni buzuvchi klishe o\'rniga professional jamoa standarti berildi',
  },
  {
    id: 'burning-eyes',
    label: 'Yonayotgan ko\'zlar / Горящие глаза',
    regex: /(?:yonib\s+turgan\s+ko['`’]?zlar|yonayotgan\s+ko['`’]?zlar|горящие\s+глаза|burning\s+eyes|passionate\s+zeal)/gi,
    replacement: 'muhandislik intizomi va murakkab masalalarni yechimga yetkazish qat\'iyati',
    explanation: 'Hissiy talab o\'rniga professional intizom va natijadorlik belgilandi',
  },
  {
    id: 'multitasking',
    label: 'Ko\'p vazifalilik / Многозадачность',
    regex: /(?:ko['`’]?p\s+vazifalilik|многозадачност(?:ь|и)|многозадачный|multitasking)/gi,
    replacement: 'aniq ustuvorliklarni (ruthless prioritization) belgilay olish va asosiy maqsadga chuqur fokus',
    explanation: 'Chalg\'ish o\'rniga asosiy vazifalarga diqqatni jamlash ko\'rsatildi',
  },
  {
    id: 'competitive-salary',
    label: 'Raqobatbardosh maosh / Конкурентная зарплата',
    regex: /(?:raqobatbardosh\s+(?:maosh|ish\s+haqi)|конкурентн(?:ая|ый)\s+(?:зарплата|оклад|зп)|competitive\s+salary)/gi,
    replacement: 'bozorning yuqori kvartiliga mos va biznesga qo\'shilgan real hissaga bog\'langan shaffof kompensatsiya',
    explanation: 'Yashirin noaniq va\'da o\'rniga shaffof va adolatli moliya modeli keltirildi',
  },
  {
    id: 'comfortable-office',
    label: 'Shinam ofis / Комфортный офис',
    regex: /(?:shinam\s+ofis|qulay\s+ofis|комфортн(?:ый|ая)\s+офис|cozy\s+office|comfortable\s+office)/gi,
    replacement: 'chuqur konsentratsiya uchun qulay ish maydoni yoki to\'liq moslashuvchan masofaviy (remote) erkinlik',
    explanation: 'Shunchaki devorlar emas, balki konsentratsiya va erkinlik ta\'kidlandi',
  },
  {
    id: 'team-player',
    label: 'Jamoada ishlash / Умение работать в команде',
    regex: /(?:jamoada\s+ishlash\s+qobiliyati|умени(?:е|я)\s+работать\s+в\s+команде|team\s+player)/gi,
    replacement: 'arxitektura va mahsulot yechimlarini asoslash, ochiq kod tahlili (code review) orqali jamoani o\'stirish',
    explanation: 'Mavhum ko\'nikma o\'rniga aniq muloqot va ochiq tahlil madaniyati berildi',
  },
  {
    id: 'overtime-ready',
    label: 'Ishdan keyin qolish / Готовность к переработкам',
    regex: /(?:ishdan\s+keyin\s+qolishga\s+tayyorlik|готовност(?:ь|и)\s+к\s+переработкам|willingness\s+to\s+work\s+overtime)/gi,
    replacement: 'aniq rejalashtirilgan sprintlar va ortiqcha charchashsiz barqaror mahsuldorlik sur\'ati (sustainable pace)',
    explanation: 'Noto\'g\'ri rejalashtirish o\'rniga sog\'lom ish sur\'ati belgilandi',
  },
  {
    id: 'strict-instructions',
    label: 'Ijrochilik / Исполнительность',
    regex: /(?:ijrochilik|исполнительност(?:ь|и)|must\s+follow\s+instructions)/gi,
    replacement: 'muammoni mustaqil tushunish, yechim taklif qilish va yakuniy biznes oqibati uchun to\'liq mas\'uliyat',
    explanation: 'Boshqariladigan buyruq bajaruvchisi emas, balki avtonom muhandis izlanadi',
  },
  {
    id: 'initiative-welcomed',
    label: 'Tashabbuskorlik ma\'qullanadi / Инициативность приветствуется',
    regex: /(?:tashabbuskorlik\s+ma['`’]qullanadi|инициативност(?:ь|и)\s+приветствуется|initiative\s+is\s+welcome)/gi,
    replacement: 'mahsulot strategiyasi va arxitekturaviy qarorlarni to\'g\'ridan-to\'g\'ri shakllantirish vakolati',
    explanation: 'Tashabbus shunchaki qabul qilinmaydi, balki to\'g\'ridan-to\'g\'ri vakolat beriladi',
  },
  {
    id: 'leadership-qualities',
    label: 'Yetakchilik qobiliyatlari / Лидерские качества',
    regex: /(?:yetakchilik\s+qobiliyatlari|лидерск(?:ие|их)\s+качеств(?:а|о)|strong\s+leadership\s+skills)/gi,
    replacement: 'muhandislik madaniyati darajasini (engineering bar) oshirish va yosh mutaxassislarga murabbiylik qilish',
    explanation: 'Amaliy murabbiylik va standartlarni ko\'tarish ta\'kidlandi',
  },
  {
    id: 'conflict-free',
    label: 'Nizo chiqarmaslik / Неконфликтность',
    regex: /(?:nizo\s+chiqarmaslik|неконфликтност(?:ь|и)|conflict-free)/gi,
    replacement: 'asosli professional bahslar, dalillarga asoslangan konsensus va ayblashsiz tahlil (blameless postmortems)',
    explanation: 'Sokin sukut emas, balki sog\'lom muhandislik munozarasi rag\'batlantiriladi',
  },
];

export function cleanAntiSlopText(text: string): { cleaned: string; replacedPhrases: string[] } {
  if (!text || typeof text !== 'string') {
    return { cleaned: '', replacedPhrases: [] };
  }

  let cleaned = text;
  const replacedPhrases: string[] = [];

  for (const rule of SLOP_DICTIONARY) {
    const matches = text.match(rule.regex);
    if (matches && matches.length > 0) {
      for (const m of matches) {
        if (!replacedPhrases.includes(m.trim())) {
          replacedPhrases.push(m.trim());
        }
      }
      cleaned = cleaned.replace(rule.regex, rule.replacement);
    }
  }

  return { cleaned, replacedPhrases };
}
