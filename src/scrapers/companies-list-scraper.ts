import { Page } from 'playwright';
import { prisma } from '../utils/database.js';
import { BrowserManager } from '../utils/browser.js';
import { cleanText, randomDelay, logProgress } from '../utils/helpers.js';
import { fetchIsyatirimUniverse } from '../utils/isyatirim.js';

interface CompanyBasicInfo {
  code: string;
  name: string;
  detailUrl: string;
}

const BASE_URL = 'https://www.kap.org.tr/tr/bist-sirketler';

export class CompaniesListScraper {
  private browser: BrowserManager;

  constructor(browser: BrowserManager) {
    this.browser = browser;
  }

  /**
   * BIST şirketler listesini kazı ve temel bilgileri veritabanına kaydet
   */
  async scrapeAll(): Promise<void> {
    console.log('\n🏢 Şirket listesi kazınıyor...');
    
    let allowedCodes: Set<string>;

    try {
      const universe = await fetchIsyatirimUniverse(this.browser);
      allowedCodes = universe.codeSet;
      if (!allowedCodes.size) {
        throw new Error('İş Yatırım listesi boş döndü');
      }
      console.log(`✅ İş Yatırım Ulusal-Tüm listesi yüklendi (${allowedCodes.size} kod)`);
    } catch (error) {
      const reason = error instanceof Error ? error.message : String(error);
      console.error(`❌ İş Yatırım Ulusal-Tüm listesi alınamadı: ${reason}`);
      throw new Error('İş Yatırım fihristi yüklenmeden şirket listesi kazınamaz');
    }

    const page = await this.browser.newPage();
    
    try {
      await page.goto(BASE_URL, { waitUntil: 'domcontentloaded' });
      await page.waitForSelector('tbody', { timeout: 20000 });
      await randomDelay(1000, 2000);

      // Şirket listesini al
  const companies = await this.parseCompaniesTable(page, allowedCodes);
      console.log(`✅ ${companies.length} şirket listelendi`);

      if (allowedCodes && allowedCodes.size > 0) {
        const kapCodes = new Set(companies.map(company => company.code.toUpperCase()));
        const missingCodes = Array.from(allowedCodes).filter(code => !kapCodes.has(code));

        if (missingCodes.length > 0) {
          const sample = missingCodes.slice(0, 10).join(', ');
          console.warn(`⚠️  İş Yatırım listesinde olup KAP tablosunda bulunamayan ${missingCodes.length} kod var. Örnek: ${sample}`);
        }
      }

      // Her şirketi veritabanına kaydet
      for (let i = 0; i < companies.length; i++) {
        const company = companies[i];
        logProgress(i + 1, companies.length, `${company.code} - ${company.name}`);

        // Şirketi veritabanına kaydet (sadece temel bilgiler)
        // Detaylar ayrı bir scraper'da doldurulacak
        await prisma.company.upsert({
          where: { code: company.code },
          update: {
            name: company.name,
            detailUrl: company.detailUrl,
            updatedAt: new Date()
          },
          create: {
            code: company.code,
            name: company.name,
            detailUrl: company.detailUrl
          }
        });

        await randomDelay(50, 150);
      }

      console.log('✅ Şirketler başarıyla kaydedildi');

    } catch (error) {
      console.error('❌ Şirketler listesi kazınırken hata:', error);
      throw error;
    } finally {
      await page.close();
    }
  }

  /**
   * Şirketler tablosunu parse et
   */
  private async parseCompaniesTable(page: Page, allowedCodes?: Set<string>): Promise<CompanyBasicInfo[]> {
    const entries: CompanyBasicInfo[] = [];
    const seen = new Set<string>();

    const tableBody = await page.$('tbody');
    if (!tableBody) {
      console.warn('⚠️  Şirketler tablosu bulunamadı');
      return entries;
    }

    // Tablo satırlarını al (border-b class'ı olan satırlar)
    const rows = await tableBody.$$('tr.border-b');

    for (const row of rows) {
      try {
        const cells = await row.$$('td');
        if (cells.length < 4) continue;

        // İlk hücredeki link'i al
        const linkTag = await cells[0].$('a');
        if (!linkTag) continue;

        // Kod metni (birden fazla kod olabilir, örn: "ASELS ASELX")
        const fullCodeText = cleanText(await linkTag.textContent());
        if (!fullCodeText) continue;

  // Şirket adı ve URL (önce al)
  const name = cleanText(await cells[1].textContent());
        const href = await linkTag.getAttribute('href');
        
        if (!name || !href) continue;
        
        // Kodları ayır ve işle
        const potentialCodes = fullCodeText.split(' ').filter(c => c.length > 0);
        
        /**
         * YENİ MULTIPLE TICKER STRATEJİSİ:
         * 1. Halka açık hisseler genellikle 4-5 karakter (örn: ASELS, ISCTR, THYAO)
         * 2. Eski şirketler 4 karakter (örn: ASYA, MAVI)
         * 3. Yeni şirketler 5 karakter (örn: ASELS)
         * 4. 3 karakter ve altı: Genellikle ayrıcalıklı hisseler (örn: ISA, ISB, ISC)
         * 
         * Strateji:
         * - 4-5 karakterli kodları filtrele (halka açık işlem gören)
         * - Birden fazla 4-5 karakterli varsa, hepsini kaydet
         * - Gelecekte hacim bazlı filtreleme eklenecek (Algolab API)
         */
        
        // 4-5 karakterli kodları filtrele (halka açık hisseler)
        const tradableTickerCodes = potentialCodes
          .map(code => code.toUpperCase())
          .filter(code => code.length >= 4 && code.length <= 5);

        let codesToProcess = tradableTickerCodes.length > 0 ? tradableTickerCodes : potentialCodes.map(code => code.toUpperCase());

        if (allowedCodes && allowedCodes.size > 0) {
          const filtered = codesToProcess.filter(code => allowedCodes.has(code));
          if (filtered.length === 0) {
            continue;
          }
          codesToProcess = filtered;
        }
        const detailUrl = href.startsWith('http') ? href : `https://www.kap.org.tr${href}`;

        if (codesToProcess.length > 1) {
          console.log(`  ℹ️  ${name}: Çoklu hisse kodu tespit edildi → ${codesToProcess.join(', ')}`);
        }

        for (const code of codesToProcess) {
          if (seen.has(code)) {
            continue;
          }
          seen.add(code);
          entries.push({
            code,
            name,
            detailUrl
          });
        }

      } catch (error) {
        console.warn('⚠️  Bir şirket satırı okunamadı:', error);
      }
    }

    return entries;
  }
}

// Standalone çalıştırma
if (import.meta.url === `file://${process.argv[1]}`) {
  const browser = new BrowserManager();
  
  (async () => {
    try {
      await browser.launch(false);
      const scraper = new CompaniesListScraper(browser);
      await scraper.scrapeAll();
    } catch (error) {
      console.error('Fatal error:', error);
      process.exit(1);
    } finally {
      await browser.close();
      await prisma.$disconnect();
    }
  })();
}

