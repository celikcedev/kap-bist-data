import 'dotenv/config';
import { prisma, connectDatabase, disconnectDatabase } from '../src/utils/database.js';
import { BrowserManager } from '../src/utils/browser.js';
import { CompaniesDetailScraper } from '../src/scrapers/companies-detail-scraper.js';

const targetCodes = process.argv.slice(2).map(arg => arg.toUpperCase());

if (!targetCodes.length) {
  console.error('Usage: tsx scripts/targeted-company-detail.ts <CODE> [CODE...]');
  process.exit(1);
}

async function main(): Promise<void> {
  const browser = new BrowserManager();
  try {
    await connectDatabase();

    const companies = await prisma.company.findMany({
      where: { code: { in: targetCodes } },
      select: { id: true, code: true, detailUrl: true, name: true }
    });

    const missing = targetCodes.filter(code => !companies.some(c => c.code === code));
    if (missing.length) {
      console.warn(`⚠️  Not found in database: ${missing.join(', ')}`);
    }

    if (!companies.length) {
      console.error('No companies found to scrape.');
      return;
    }

    await browser.launch(true);
    const scraper = new CompaniesDetailScraper(browser);

    for (const company of companies) {
      if (!company.detailUrl) {
        console.warn(`⚠️  ${company.code}: detail URL missing, skipping.`);
        continue;
      }

      console.log(`
════════════════════════════════════════════════════════════
🔄 Target scrape starting for ${company.code} - ${company.name}
════════════════════════════════════════════════════════════`);

      await scraper.scrapeCompanyDetail(company.id, company.code, company.detailUrl);

      console.log(`✅ Target scrape finished for ${company.code}`);
    }
  } finally {
    await browser.close();
    await disconnectDatabase();
  }
}

main().catch(error => {
  console.error('❌ Target scrape failed:', error);
  process.exit(1);
});
