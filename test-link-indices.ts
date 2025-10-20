import { BrowserManager } from './src/utils/browser.js';
import { IndicesScraper } from './src/scrapers/indices-scraper.js';
import { prisma } from './src/utils/database.js';

async function main() {
  const browser = new BrowserManager();
  
  try {
    console.log('🚀 Endeks-Şirket ilişkilendirmesi test ediliyor...\n');
    
    // Browser'ı başlat
    await browser.launch(true);
    
    // Mevcut XUTUM ilişki sayısını kontrol et
    const xutumBefore = await prisma.companyIndex.count({
      where: { index: { code: 'XUTUM' } }
    });
    console.log(`📊 XUTUM mevcut şirket sayısı: ${xutumBefore}\n`);
    
    // Sadece XUTUM için test et
    const page = await browser.newPage();
    await page.goto('https://www.kap.org.tr/tr/Endeksler', { waitUntil: 'domcontentloaded' });
    await page.waitForSelector('#indicesTable', { timeout: 20000 });
    
    const indicesScraper = new IndicesScraper(browser);
    const xutumIndex = await prisma.index.findUnique({ where: { code: 'XUTUM' } });
    
    if (xutumIndex) {
      console.log('🔗 XUTUM ilişkilendiriliyor...\n');
      
      // Şirketleri al (dropdown seçimine gerek yok, tablo zaten sayfada)
      const companies = await (indicesScraper as any).getCompaniesByIndex(page, xutumIndex.name);
      console.log(`✅ ${companies.length} şirket bulundu`);
      
      // İlk 10 şirketi göster
      console.log('\nİlk 10 şirket:');
      companies.slice(0, 10).forEach((c: any) => {
        console.log(`  - ${c.code}: ${c.name}`);
      });
    }
    
    await page.close();
    
    const xutumAfter = await prisma.companyIndex.count({
      where: { index: { code: 'XUTUM' } }
    });
    
    console.log(`\n📊 XUTUM yeni şirket sayısı: ${xutumAfter}`);
    
  } catch (error) {
    console.error('❌ Hata:', error);
  } finally {
    await browser.close();
    await prisma.$disconnect();
  }
}

main();
