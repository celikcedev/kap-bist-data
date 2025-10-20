import { Page } from 'playwright';
import { prisma } from '../utils/database.js';
import { BrowserManager } from '../utils/browser.js';
import { cleanText, randomDelay, logProgress } from '../utils/helpers.js';

interface SubMarketData {
  name: string;
  companyCount: number;
  companies: { code: string; name: string }[];
}

const BASE_URL = 'https://www.kap.org.tr/tr/Pazarlar';

export class MarketsScraper {
  private browser: BrowserManager;

  constructor(browser: BrowserManager) {
    this.browser = browser;
  }

  /**
   * Sadece Pay Piyasası alt pazarlarını kazı ve veritabanına kaydet
   */
  async scrapeAll(): Promise<void> {
    console.log('\n💼 Pazarlar kazınıyor (Sadece Pay Piyasası alt pazarları)...');
    
    const page = await this.browser.newPage();
    
    try {
      await page.goto(BASE_URL, { waitUntil: 'domcontentloaded' });
      await page.waitForSelector('#marketsTable', { timeout: 20000 });
      await randomDelay(1000, 2000);

      // Tablodaki Pay Piyasası alt pazarlarını parse et
      const subMarkets = await this.parseMarketsTable(page);
      console.log(`✅ ${subMarkets.length} alt pazar (Pay Piyasası) bulundu`);

      // Her alt pazarı veritabanına kaydet
      for (let i = 0; i < subMarkets.length; i++) {
        const market = subMarkets[i];
        logProgress(i + 1, subMarkets.length, `${market.name} (${market.companyCount} şirket)`);

        await prisma.market.upsert({
          where: { name: market.name },
          update: { updatedAt: new Date() },
          create: { name: market.name }
        });

        await randomDelay(200, 500);
      }

      console.log('✅ Pazarlar başarıyla kaydedildi');

    } catch (error) {
      console.error('❌ Pazarlar kazınırken hata:', error);
      throw error;
    } finally {
      await page.close();
    }
  }

  /**
   * Pazarlar tablosunu parse ederek SADECE Pay Piyasası alt pazarlarını al
   */
  private async parseMarketsTable(page: Page): Promise<SubMarketData[]> {
    const subMarkets: SubMarketData[] = [];
    let inPayMarket = false; // Pay Piyasası içinde miyiz?
    let currentSubMarket: SubMarketData | null = null;

    const table = await page.$('#marketsTable tbody');
    if (!table) {
      console.warn('⚠️  Pazar tablosu bulunamadı');
      return subMarkets;
    }

    const rows = await table.$$('tr');

    for (const row of rows) {
      // Başlık satırı (colspan="4" olan)
      const headerCell = await row.$('td[colspan="4"]');
      
      if (headerCell) {
        const classList = await headerCell.getAttribute('class');
        const classes = classList?.split(' ') || [];

        // Ana Pazar Başlığı (active class'ı olan)
        if (classes.includes('active')) {
          const nameDiv = await headerCell.$('div.px-4.font-semibold');
          if (nameDiv) {
            const marketName = cleanText(await nameDiv.textContent());
            
            // Pay Piyasası'na girdiğimizde flag'i aç
            if (marketName?.toUpperCase() === 'PAY PİYASASI') {
              inPayMarket = true;
              console.log('   📊 Pay Piyasası bulundu, alt pazarlar kazınıyor...');
            }
            // Başka bir ana pazara geçildiğinde flag'i kapat
            else if (inPayMarket) {
              inPayMarket = false;
              console.log('   ⏭  Pay Piyasası dışına çıkıldı, kazıma durduruluyor');
              break; // Pay Piyasası bittiyse döngüden çık
            }
          }
        }
        // Alt Pazar Başlığı (Pay Piyasası içindeyken)
        else if (inPayMarket) {
          const nameSpan = await headerCell.$('span.px-4.font-semibold');
          const countSpan = await headerCell.$('span.font-normal.text-sm');

          if (nameSpan && countSpan) {
            const name = cleanText(await nameSpan.textContent());
            const countText = cleanText(await countSpan.textContent());
            
            // "X Şirket Bulundu" metninden sayıyı çıkar
            const match = countText?.match(/(\d+)/);
            const companyCount = match ? parseInt(match[1]) : 0;

            if (name) {
              // Girişim Sermayesi Pazarı'nı atla (Nitelikli yatırımcı pazarı)
              if (name.toUpperCase().includes('GİRİŞİM SERMAYESİ')) {
                console.log(`   ⏭  "${name}" atlandı (Nitelikli yatırımcı pazarı)`);
                currentSubMarket = null;
                continue;
              }
              
              currentSubMarket = { name, companyCount, companies: [] };
              subMarkets.push(currentSubMarket);
            }
          }
        }
      }
      // Şirket Satırı
      else if (inPayMarket && currentSubMarket) {
        const classList = await row.getAttribute('class');
        const classes = classList?.split(' ') || [];

        if (classes.includes('border-b')) {
          const cells = await row.$$('td');
          if (cells.length >= 3) {
            const rankText = cleanText(await cells[0].textContent());
            
            if (rankText && /^\d+$/.test(rankText)) {
              const codeTag = await cells[1].$('a');
              const nameTag = await cells[2].$('a');

              const code = codeTag 
                ? cleanText(await codeTag.textContent())
                : cleanText(await cells[1].textContent());
              
              const name = nameTag
                ? cleanText(await nameTag.textContent())
                : cleanText(await cells[2].textContent());

              if (code && name) {
                currentSubMarket.companies.push({ code, name });
              }
            }
          }
        }
      }
    }

    return subMarkets;
  }
}

// Standalone çalıştırma
if (import.meta.url === `file://${process.argv[1]}`) {
  const browser = new BrowserManager();
  
  (async () => {
    try {
      await browser.launch(false);
      const scraper = new MarketsScraper(browser);
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

