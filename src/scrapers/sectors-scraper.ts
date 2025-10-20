import { Page } from 'playwright';
import { prisma } from '../utils/database.js';
import { BrowserManager } from '../utils/browser.js';
import { cleanText, randomDelay, logProgress } from '../utils/helpers.js';

interface SubSectorData {
  name: string;
  companies: { code: string; name: string }[];
}

interface MainSectorData {
  name: string;
  subSectors: SubSectorData[];
}

const BASE_URL = 'https://www.kap.org.tr/tr/Sektorler';

export class SectorsScraper {
  private browser: BrowserManager;

  constructor(browser: BrowserManager) {
    this.browser = browser;
  }

  /**
   * Tüm sektörleri kazı ve veritabanına kaydet
   */
  async scrapeAll(): Promise<void> {
    console.log('\n🏭 Sektörler kazınıyor...');
    
    const page = await this.browser.newPage();
    
    try {
      await page.goto(BASE_URL, { waitUntil: 'domcontentloaded' });
      await page.waitForSelector('#sectorsTable', { timeout: 20000 });
      await randomDelay(1000, 2000);

      // Tablodaki tüm sektör verilerini parse et
      const sectors = await this.parseSectorsTable(page);
      console.log(`✅ ${sectors.length} ana sektör bulundu`);

      // Her sektörü veritabanına kaydet
      for (let i = 0; i < sectors.length; i++) {
        const sector = sectors[i];
        logProgress(i + 1, sectors.length, sector.name);

        // Ana sektörü kaydet
        const mainSector = await prisma.mainSector.upsert({
          where: { name: sector.name },
          update: { updatedAt: new Date() },
          create: { name: sector.name }
        });

        // Alt sektörleri kaydet
        for (const subSectorData of sector.subSectors) {
          await prisma.subSector.upsert({
            where: {
              name_mainSectorId: {
                name: subSectorData.name,
                mainSectorId: mainSector.id
              }
            },
            update: { updatedAt: new Date() },
            create: {
              name: subSectorData.name,
              mainSectorId: mainSector.id
            }
          });

          console.log(`   📁 Alt sektör: ${subSectorData.name} (${subSectorData.companies.length} şirket)`);
        }

        await randomDelay(200, 500);
      }

      console.log('✅ Sektörler başarıyla kaydedildi');

    } catch (error) {
      console.error('❌ Sektörler kazınırken hata:', error);
      throw error;
    } finally {
      await page.close();
    }
  }

  /**
   * Sektörler tablosunu parse ederek ana sektör ve alt sektörleri al
   */
  private async parseSectorsTable(page: Page): Promise<MainSectorData[]> {
    const sectors: MainSectorData[] = [];
    let currentSector: MainSectorData | null = null;
    let currentSubSector: SubSectorData | null = null;

    const table = await page.$('#sectorsTable tbody');
    if (!table) {
      console.warn('⚠️  Sektör tablosu bulunamadı');
      return sectors;
    }

    const rows = await table.$$('tr');

    for (const row of rows) {
      const classList = await row.getAttribute('class');
      const classes = classList?.split(' ') || [];

      // Ana Sektör Başlığı (static class'ı olan)
      if (classes.includes('static')) {
        // Mevcut sektörü kaydet
        if (currentSector) {
          sectors.push(currentSector);
        }

        const headerSpan = await row.$('span.px-4.font-semibold');
        if (headerSpan) {
          const name = cleanText(await headerSpan.textContent());
          if (name && name.toLowerCase() !== 'diğer') { // "DİĞER" sektörünü atla
            currentSector = { name, subSectors: [] };
            currentSubSector = null;
          } else {
            currentSector = null;
          }
        }
      }
      // Alt Sektör Başlığı (bg-gray-200 class'ı olan)
      else if (classes.includes('bg-gray-200')) {
        const td = await row.$('td');
        if (td && currentSector) {
          const subSectorName = cleanText(await td.textContent());
          if (subSectorName) {
            currentSubSector = { name: subSectorName, companies: [] };
            currentSector.subSectors.push(currentSubSector);
          }
        }
      }
      // Şirket Satırı (border-b class'ı olan)
      else if (classes.includes('border-b')) {
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
              const company = { code, name };
              
              // Alt sektöre ekle
              if (currentSubSector) {
                currentSubSector.companies.push(company);
              }
              // Eğer alt sektör yoksa doğrudan ana sektöre ekle (bu durum çok nadir)
              else if (currentSector) {
                // Ana sektöre doğrudan bağlı şirketler için genel bir alt sektör oluştur
                if (currentSector.subSectors.length === 0 || currentSector.subSectors[0].name !== 'Genel') {
                  currentSector.subSectors.unshift({ name: 'Genel', companies: [] });
                }
                currentSector.subSectors[0].companies.push(company);
              }
            }
          }
        }
      }
    }

    // Son sektörü ekle
    if (currentSector) {
      sectors.push(currentSector);
    }

    return sectors;
  }
}

// Standalone çalıştırma
if (import.meta.url === `file://${process.argv[1]}`) {
  const browser = new BrowserManager();
  
  (async () => {
    try {
      await browser.launch(false);
      const scraper = new SectorsScraper(browser);
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

