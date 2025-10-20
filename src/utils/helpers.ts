/**
 * Metni temizler, fazla boşlukları kaldırır
 */
export function cleanText(text: string | null | undefined): string | null {
  if (!text) return null;
  const cleaned = text.replace(/\s+/g, ' ').trim();
  if (cleaned === '' || cleaned === '-' || cleaned.toLowerCase() === 'bilgi mevcut değil') {
    return null;
  }
  return cleaned;
}

/**
 * Türkçe sayı formatını (1.234,56) ondalık sayıya çevirir
 */
export function parseTurkishNumber(value: string | null | undefined): number | null {
  if (!value) return null;
  const cleaned = cleanText(value);
  if (!cleaned) return null;
  // Nokta (.) binlik ayracı, virgül (,) ondalık ayracı
  const normalized = cleaned
    .replace(/\./g, '')  // Binlik ayraçları kaldır
    .replace(',', '.');  // Virgülü noktaya çevir

  const num = parseFloat(normalized);
  return isNaN(num) ? null : num;
}

/**
 * Türkçe tarih formatını (DD/MM/YYYY) ISO formatına çevirir
 */
export function parseTurkishDate(dateStr: string | null | undefined): Date | null {
  if (!dateStr) return null;
  const cleaned = cleanText(dateStr);
  if (!cleaned) return null;

  const lower = cleaned.toLowerCase();

  // 1) YYYY-MM-DD formatı zaten ISO, diğer formatlardan önce kontrol edilir
  const isoMatch = lower.match(/(\d{4})-(\d{2})-(\d{2})/);
  if (isoMatch) {
    const [, year, month, day] = isoMatch;
    const date = new Date(`${year}-${month}-${day}`);
    return isNaN(date.getTime()) ? null : date;
  }

  // 2) Gün/Ay/Yıl -> 01/06/1990, 14.11.1975, 14-11-1975
  const dayMonthYear = lower.match(/(\d{1,2})[\.\/-](\d{1,2})[\.\/-](\d{2,4})/);
  if (dayMonthYear) {
    let [, day, month, year] = dayMonthYear;
    if (year.length === 2) {
      const numericYear = parseInt(year, 10);
      const century = numericYear > 50 ? 1900 : 2000;
      year = String(century + numericYear);
    }
    const iso = `${year.padStart(4, '0')}-${month.padStart(2, '0')}-${day.padStart(2, '0')}`;
    const date = new Date(iso);
    return isNaN(date.getTime()) ? null : date;
  }

  // 3) Gün AyAdı Yıl -> 1 Ocak 2024, 30 Eyl 2023
  const monthMap: Record<string, string> = {
    'ocak': '01',
    'şubat': '02',
    'mart': '03',
    'nisan': '04',
    'mayıs': '05',
    'haziran': '06',
    'haz': '06',
    'temmuz': '07',
    'ağustos': '08',
    'ağu': '08',
    'eylül': '09',
    'eyl': '09',
    'ekim': '10',
    'kasım': '11',
    'aralık': '12'
  };

  const naturalLang = lower.match(/(\d{1,2})\s+([a-zçğıöşü]+)\s+(\d{4})/);
  if (naturalLang) {
    const [, day, monthName, year] = naturalLang;
    const normalizedMonth = monthMap[monthName];
    if (normalizedMonth) {
      const iso = `${year}-${normalizedMonth}-${day.padStart(2, '0')}`;
      const date = new Date(iso);
      return isNaN(date.getTime()) ? null : date;
    }
  }

  return null;
}

/**
 * Boolean değeri parse eder (Türkçe)
 */
export function parseBoolean(value: string | null | undefined): boolean | null {
  if (!value) return null;
  const cleaned = cleanText(value);
  if (!cleaned) return null;

  const lower = cleaned.toLowerCase();
  if (lower === 'evet' || lower === 'yes' || lower === 'true') return true;
  if (lower === 'hayır' || lower === 'no' || lower === 'false') return false;
  return null;
}

/**
 * Tablo başlıklarını normalize eder (büyük/küçük harf, özel karakter farklarını yok sayar)
 */
export function normalizeHeaderLabel(label: string): string {
  return label
    .toLowerCase()
    .replace(/[^a-z0-9çğıöşü]+/g, ' ')
    .trim();
}

/**
 * Başlık listesinde belirtilen adaylardan ilk eşleşmenin index'ini döner
 */
export function findHeaderIndex(headers: string[], candidates: string[]): number {
  if (!headers.length) return -1;
  const normalized = headers.map(h => normalizeHeaderLabel(h));
  for (const candidate of candidates) {
    const target = normalizeHeaderLabel(candidate);
    const idx = normalized.indexOf(target);
    if (idx !== -1) {
      return idx;
    }
  }
  return -1;
}

/**
 * Rastgele gecikme ekler (rate limiting için)
 */
export async function randomDelay(min: number = 500, max: number = 1500): Promise<void> {
  const delay = Math.floor(Math.random() * (max - min + 1)) + min;
  await new Promise(resolve => setTimeout(resolve, delay));
}

/**
 * Progress logger
 */
export function logProgress(current: number, total: number, message: string = ''): void {
  const percentage = ((current / total) * 100).toFixed(1);
  console.log(`[${current}/${total}] (${percentage}%) ${message}`);
}

