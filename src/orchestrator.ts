/**
 * KAP BIST Data Scraper - Ana Orchestrator
 * 
 * Tüm kazıma işlemlerini sırasıyla çalıştırır:
 * 1. Endeksler (indices)
 * 2. Sektörler (main_sectors + sub_sectors)
 * 3. Pazarlar (markets - sadece Pay Piyasası alt pazarları)
 * 4. Şirket Listesi (companies basic info)
 * 5. Şirket Detayları (companies full details + relations)
 */

import 'dotenv/config';
import { connectDatabase, disconnectDatabase } from './utils/database.js';
import { BrowserManager } from './utils/browser.js';
import { IndicesScraper } from './scrapers/indices-scraper.js';
import { SectorsScraper } from './scrapers/sectors-scraper.js';
import { MarketsScraper } from './scrapers/markets-scraper.js';
import { CompaniesListScraper } from './scrapers/companies-list-scraper.js';
import { CompaniesDetailScraper } from './scrapers/companies-detail-scraper.js';

type OrchestratorOptions = {
  skipTaxonomy: boolean;
  skipCompaniesList: boolean;
  skipCompanyDetails: boolean;
  headless: boolean;
};

const browser = new BrowserManager();
let isShuttingDown = false;

function printUsage(): void {
  console.log(`\nKullanım: npm run scrape:all -- [bayraklar]\n\nBayraklar:\n  --skip-taxonomy       Endeks / sektör / pazar adımlarını atlar\n  --skip-companies      Şirket listesini kazımaz\n  --skip-details        Şirket detay kazımasını atlar\n  --no-headless         Tarayıcıyı görünür modda açar\n  --headless=<true|false>  Headless modunu açık/kapalı ayarlar\n  --help, -h            Bu mesajı gösterir\n`);
}

function parseArgs(): OrchestratorOptions {
  const options: OrchestratorOptions = {
    skipTaxonomy: false,
    skipCompaniesList: false,
    skipCompanyDetails: false,
    headless: true
  };

  const args = process.argv.slice(2);

  for (const arg of args) {
    if (arg === '--skip-taxonomy') {
      options.skipTaxonomy = true;
    } else if (arg === '--skip-companies') {
      options.skipCompaniesList = true;
    } else if (arg === '--skip-details') {
      options.skipCompanyDetails = true;
    } else if (arg === '--no-headless' || arg === '--headless=false') {
      options.headless = false;
    } else if (arg === '--headless=true') {
      options.headless = true;
    } else if (arg.startsWith('--headless=')) {
      const value = arg.split('=')[1];
      if (value === 'true') {
        options.headless = true;
      } else if (value === 'false') {
        options.headless = false;
      } else {
        console.warn(`⚠️  headless bayrağı için bilinmeyen değer: ${value}`);
      }
    } else if (arg === '--help' || arg === '-h') {
      printUsage();
      process.exit(0);
    } else {
      console.warn(`⚠️  Bilinmeyen argüman: ${arg}`);
    }
  }

  return options;
}

async function cleanup(signal?: NodeJS.Signals, exitCode: number = 0): Promise<void> {
  if (isShuttingDown) {
    if (signal) {
      process.exit(exitCode);
    }
    return;
  }

  isShuttingDown = true;

  if (signal) {
    console.log(`\n⚠️  ${signal} sinyali alındı, kapatma süreci başlatılıyor...`);
  }

  try {
    await browser.close();
  } catch (browserError) {
    console.error('❌ Tarayıcı kapatılırken hata meydana geldi:', browserError);
  }

  try {
    await disconnectDatabase();
  } catch (dbError) {
    console.error('❌ Veritabanı bağlantısı kapatılırken hata meydana geldi:', dbError);
  }

  if (signal) {
    process.exit(exitCode);
  }
}

function setupSignalHandlers(): void {
  const handleSignal = (signal: NodeJS.Signals) => {
    cleanup(signal).catch(error => {
      console.error('❌ Graceful shutdown sırasında hata:', error);
      process.exit(1);
    });
  };

  ['SIGINT', 'SIGTERM'].forEach(signal => {
    process.once(signal as NodeJS.Signals, () => handleSignal(signal as NodeJS.Signals));
  });
}

async function main(): Promise<number> {
  const options = parseArgs();
  setupSignalHandlers();

  console.log('🚀 KAP BIST Data Scraper başlatılıyor...\n');
  console.log('═'.repeat(60));
  console.log('⚙️  Çalıştırma seçenekleri:');
  console.log(`   • Tarayıcı headless: ${options.headless ? 'evet' : 'hayır'}`);
  console.log(`   • Taksonomi adımları: ${options.skipTaxonomy ? 'atla' : 'çalıştır'}`);
  console.log(`   • Şirket listesi: ${options.skipCompaniesList ? 'atla' : 'çalıştır'}`);
  console.log(`   • Şirket detayları: ${options.skipCompanyDetails ? 'atla' : 'çalıştır'}`);
  console.log('═'.repeat(60));

  const startTime = Date.now();
  let exitCode = 0;

  try {
    await connectDatabase();
    await browser.launch(options.headless);

    if (!options.skipTaxonomy) {
      console.log('\n' + '═'.repeat(60));
      console.log('📋 ADIM 1: Taksonomi Verileri (Indices, Sectors, Markets)');
      console.log('═'.repeat(60));

      console.log('\n🔄 Endeksler kazınıyor...');
      const indicesScraper = new IndicesScraper(browser);
      await indicesScraper.scrapeAll();

      console.log('\n🔄 Sektörler kazınıyor...');
      const sectorsScraper = new SectorsScraper(browser);
      await sectorsScraper.scrapeAll();

      console.log('\n🔄 Pazarlar kazınıyor...');
      const marketsScraper = new MarketsScraper(browser);
      await marketsScraper.scrapeAll();
    } else {
      console.log('\n⏭️  Adım 1 (Taksonomi) --skip-taxonomy bayrağı nedeniyle atlandı.');
    }

    console.log('\n' + '═'.repeat(60));
    console.log('📋 ADIM 2: Şirket Verileri');
    console.log('═'.repeat(60));

    if (!options.skipCompaniesList) {
      console.log('\n🔄 Şirket listesi kazınıyor...');
      const companiesListScraper = new CompaniesListScraper(browser);
      await companiesListScraper.scrapeAll();
    } else {
      console.log('\n⏭️  Şirket listesi kazıması (--skip-companies) bayrağı nedeniyle atlandı.');
    }

    if (!options.skipCompanyDetails) {
      console.log('\n🔄 Şirket detayları kazınıyor (bu işlem uzun sürebilir)...');
      const companiesDetailScraper = new CompaniesDetailScraper(browser);
      await companiesDetailScraper.scrapeAll();
    } else {
      console.log('\n⏭️  Şirket detay kazıması (--skip-details) bayrağı nedeniyle atlandı.');
    }

    // Endeks-Şirket ilişkilendirmesi (companies kazındıktan sonra)
    // NOT: Bu metadata bazlı olduğu için browser gerektirmez
    console.log('\n' + '═'.repeat(60));
    console.log('📋 ADIM 3: Endeks-Şirket İlişkilendirmesi');
    console.log('═'.repeat(60));
    
    console.log('\n🔗 Endeks-şirket ilişkileri oluşturuluyor (metadata bazlı)...');
    const indicesScraperForLinking = new IndicesScraper(browser);
    await indicesScraperForLinking.linkCompaniesToIndices();

    const elapsed = ((Date.now() - startTime) / 1000 / 60).toFixed(2);
    console.log('\n' + '═'.repeat(60));
    console.log('✅ TÜM İŞLEMLER BAŞARIYLA TAMAMLANDI!');
    console.log('═'.repeat(60));
    console.log(`⏱️  Toplam Süre: ${elapsed} dakika`);
    console.log('═'.repeat(60));
  } catch (error) {
    console.error('\n❌ Kritik Hata:', error);
    exitCode = 1;
  } finally {
    await cleanup();
  }

  return exitCode;
}

if (import.meta.url === `file://${process.argv[1]}`) {
  main().then(code => {
    if (code !== 0) {
      process.exit(code);
    }
  });
}

