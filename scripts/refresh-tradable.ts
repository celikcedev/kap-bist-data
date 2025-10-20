import 'dotenv/config';
import { connectDatabase, disconnectDatabase, prisma } from '../src/utils/database.js';
import { BrowserManager } from '../src/utils/browser.js';
import { CompaniesDetailScraper } from '../src/scrapers/companies-detail-scraper.js';

async function main(): Promise<void> {
  await connectDatabase();

  const targets = await prisma.company.findMany({
    where: {
      isTradable: false,
      freeFloatTicker: { not: null }
    },
    select: {
      id: true,
      code: true,
      name: true,
      detailUrl: true
    },
    orderBy: { code: 'asc' }
  });

  if (!targets.length) {
    console.log('✅ Yenilenecek kayıt bulunamadı.');
    await disconnectDatabase();
    return;
  }

  console.log(`🔄 ${targets.length} şirket yeniden kazınacak...`);

  const browser = new BrowserManager();
  await browser.launch(true);
  const scraper = new CompaniesDetailScraper(browser);

  let processed = 0;

  for (const company of targets) {
    processed += 1;
    if (!company.detailUrl) {
      console.warn(`⚠️  ${company.code}: detail URL eksik, atlanıyor`);
      continue;
    }

    console.log(`
════════════════════════════════════════════════════════════
🔄 (${processed}/${targets.length}) ${company.code} - ${company.name}
════════════════════════════════════════════════════════════`);

    try {
      await scraper.scrapeCompanyDetail(company.id, company.code, company.detailUrl);
    } catch (error) {
      console.error(`❌ ${company.code} yeniden kazınırken hata:`, error);
    }
  }

  await browser.close();
  await disconnectDatabase();
  console.log('✅ Yeniden kazıma tamamlandı.');
}

main().catch(async error => {
  console.error('❌ refresh-tradable çalışması başarısız:', error);
  await disconnectDatabase();
  process.exit(1);
});
