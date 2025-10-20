/**
 * KAP BIST Data Scraper - Entry Point
 * 
 * Kullanım:
 * - npm run dev        : Tüm verileri kazı (orchestrator)
 * - npm run scrape:all : Tüm verileri kazı (orchestrator)
 */

export { BrowserManager } from './utils/browser.js';
export { prisma, connectDatabase, disconnectDatabase } from './utils/database.js';
export * from './utils/helpers.js';

export { IndicesScraper } from './scrapers/indices-scraper.js';
export { SectorsScraper } from './scrapers/sectors-scraper.js';
export { MarketsScraper } from './scrapers/markets-scraper.js';
export { CompaniesListScraper } from './scrapers/companies-list-scraper.js';
export { CompaniesDetailScraper } from './scrapers/companies-detail-scraper.js';

// Orchestrator'ı import et ve çalıştır
import './orchestrator.js';

