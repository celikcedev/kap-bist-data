import { Page } from 'playwright';
import { prisma } from '../utils/database.js';
import { BrowserManager } from '../utils/browser.js';
import { cleanText, randomDelay, logProgress } from '../utils/helpers.js';

interface IndexData {
  name: string;
  code: string;
  details: string | null;
}

interface CompanyInIndex {
  code: string;
  name: string;
}

const BASE_URL = 'https://www.kap.org.tr/tr/Endeksler';

export class IndicesScraper {
  private browser: BrowserManager;

  constructor(browser: BrowserManager) {
    this.browser = browser;
  }

  /**
   * Tüm endeksleri kazı ve veritabanına kaydet
   */
  async scrapeAll(): Promise<void> {
    console.log('\n📊 Endeksler kazınıyor...');
    
    const page = await this.browser.newPage();
    
    try {
      await page.goto(BASE_URL, { waitUntil: 'domcontentloaded' });
      await page.waitForSelector('#indicesTable', { timeout: 20000 });
      await randomDelay(1000, 2000);

      // Endeks listesini al
      const indices = await this.getIndicesList(page);
      console.log(`✅ ${indices.length} endeks bulundu (${indices.filter(i => i.code !== '').length} geçerli endeks)`);

      // "Tüm Endeksler" seçeneğini filtrele
      const validIndices = indices.filter(i => i.code !== '');

      // Her endeks için şirketleri al ve METADATA olarak kaydet
      for (let i = 0; i < validIndices.length; i++) {
        const index = validIndices[i];
        logProgress(i + 1, validIndices.length, `${index.name} (${index.code})`);

        // Bu endeksteki şirketleri al
        const companies = await this.getCompaniesByIndex(page, index.name);
        console.log(`   📌 ${companies.length} şirket bulundu`);

        // Veritabanına kaydet ve şirket kodlarını JSON metadata olarak sakla
        await prisma.index.upsert({
          where: { code: index.code },
          update: {
            name: index.name,
            details: index.details,
            updatedAt: new Date(),
            // Şirket kodlarını JSON field'da sakla (sonra ilişkilendirme için)
            metadata: companies.length > 0 ? JSON.stringify({
              companyCodes: companies.map(c => c.code),
              lastScraped: new Date().toISOString()
            }) : null
          },
          create: {
            name: index.name,
            code: index.code,
            details: index.details,
            metadata: companies.length > 0 ? JSON.stringify({
              companyCodes: companies.map(c => c.code),
              lastScraped: new Date().toISOString()
            }) : null
          }
        });

        await randomDelay();
      }

      console.log('✅ Endeksler başarıyla kaydedildi');

    } catch (error) {
      console.error('❌ Endeksler kazınırken hata:', error);
      throw error;
    } finally {
      await page.close();
    }
  }

  /**
   * Endeks-Şirket ilişkilerini oluştur (metadata bazlı)
   * NOT: Bu fonksiyon companies scraper'dan SONRA çalıştırılmalı
   */
  async linkCompaniesToIndices(): Promise<void> {
    console.log('\n🔗 Endeks-Şirket ilişkileri oluşturuluyor (metadata bazlı)...');
    
    try {
      // Metadata içeren tüm endeksleri al
      const indices = await prisma.index.findMany({
        where: { metadata: { not: null } }
      });
      
      if (indices.length === 0) {
        console.log('⚠️  Metadata içeren endeks bulunamadı.');
        return;
      }

      console.log(`📋 ${indices.length} endeks için ilişkilendirme yapılacak`);

      let totalLinked = 0;
      let successCount = 0;

      for (let i = 0; i < indices.length; i++) {
        const index = indices[i];
        logProgress(i + 1, indices.length, `${index.name} (${index.code})`);

        try {
          // Metadata'dan şirket kodlarını al
          const metadata = JSON.parse(index.metadata!);
          const companyCodes: string[] = metadata.companyCodes || [];

          if (companyCodes.length === 0) {
            console.log(`   ⚠️  Şirket kodu yok, atlanıyor`);
            continue;
          }

          // Önce bu endeks için mevcut ilişkileri sil
          await prisma.companyIndex.deleteMany({
            where: { indexId: index.id }
          });

          // Her şirket kodu için ilişki oluştur
          let linkedCount = 0;
          for (const code of companyCodes) {
            const company = await prisma.company.findUnique({
              where: { code }
            });

            if (company) {
              await prisma.companyIndex.upsert({
                where: {
                  companyId_indexId: {
                    companyId: company.id,
                    indexId: index.id
                  }
                },
                update: {},
                create: {
                  companyId: company.id,
                  indexId: index.id
                }
              });
              linkedCount++;
            }
          }

          totalLinked += linkedCount;
          if (linkedCount > 0) {
            console.log(`   ✅ ${linkedCount}/${companyCodes.length} şirket ilişkilendirildi`);
            successCount++;
          }
        } catch (error) {
          console.warn(`   ⚠️  ${index.name} hatası:`, error);
        }

        await randomDelay(50, 100);
      }

      console.log(`\n✅ Toplam ${totalLinked} ilişki oluşturuldu`);
      console.log(`📊 Başarılı endeks sayısı: ${successCount}`);

    } catch (error) {
      console.error('❌ İlişkilendirme hatası:', error);
      throw error;
    }
  }

  /**
   * Dropdown'dan endeks seç
   */
  private async selectIndex(page: Page, indexName: string): Promise<void> {
    try {
      // Dropdown'ı aç
      const dropdown = await page.$('div[class*="select__control"]');
      if (dropdown) {
        await dropdown.click();
        await randomDelay(300, 500);
      }

      // Endeks seçeneğini bul ve tıkla
      const options = await page.$$('div.select__option');
      for (const option of options) {
        const nameEl = await option.$('span.font-semibold');
        if (nameEl) {
          const name = cleanText(await nameEl.textContent());
          if (name === indexName) {
            await option.click();
            await randomDelay(500, 1000);
            return;
          }
        }
      }
    } catch (error) {
      console.warn(`⚠️  ${indexName} seçilemedi:`, error);
    }
  }

  /**
   * Dropdown'dan tüm endeks listesini al
   */
  private async getIndicesList(page: Page): Promise<IndexData[]> {
    const indices: IndexData[] = [];

    // Dropdown seçeneklerini al
    const options = await page.$$('div.select__option');
    
    for (const option of options) {
      try {
        const nameEl = await option.$('span.font-semibold');
        const codeEl = await option.$('span.font-medium');
        const detailsEl = await option.$('span.text-select-text');

        const name = nameEl ? cleanText(await nameEl.textContent()) : null;
        const code = codeEl ? cleanText(await codeEl.textContent()) : '';
        const details = detailsEl ? cleanText(await detailsEl.textContent()) : null;

        if (name) {
          indices.push({ name, code: code || '', details });
        }
      } catch (error) {
        console.warn('⚠️  Bir endeks okunamadı:', error);
      }
    }

    return indices;
  }

  /**
   * Belirli bir endeksteki şirketleri al
   */
  private async getCompaniesByIndex(page: Page, indexName: string): Promise<CompanyInIndex[]> {
    const companies: CompanyInIndex[] = [];

    try {
      const table = await page.$('#indicesTable');
      if (!table) return companies;

      const rows = await table.$$('tr');
      let startParsing = false;

      for (const row of rows) {
        // Başlık satırını kontrol et (colspan="12" olan satır)
        const headerCell = await row.$('td[colspan="12"]');
        
        if (headerCell) {
          const headerText = cleanText(await headerCell.textContent());
          
          // Başlıkta indexName'i ara (örn: "BIST 100100 Şirket Bulundu" → "BIST 100" ile eşleş)
          if (headerText?.toLowerCase().includes(indexName.toLowerCase())) {
            startParsing = true;
          } else if (startParsing) {
            // Bir sonraki başlığa gelindiğinde dur
            break;
          }
          continue;
        }

        // Şirket satırı
        if (startParsing) {
          const cells = await row.$$('td');
          if (cells.length >= 3) {
            const rankText = cleanText(await cells[0].textContent());
            if (rankText && /^\d+$/.test(rankText)) {
              const code = cleanText(await cells[1].textContent());
              const name = cleanText(await cells[2].textContent());
              
              if (code && name) {
                companies.push({ code, name });
              }
            }
          }
        }
      }
    } catch (error) {
      console.warn(`⚠️  ${indexName} endeksi için şirketler alınamadı:`, error);
    }

    return companies;
  }
}

// Standalone çalıştırma
if (import.meta.url === `file://${process.argv[1]}`) {
  const browser = new BrowserManager();
  
  (async () => {
    try {
      await browser.launch(false); // headless=false for debugging
      const scraper = new IndicesScraper(browser);
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
