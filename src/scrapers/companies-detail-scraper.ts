import { Locator, Page } from 'playwright';
import { prisma } from '../utils/database.js';
import { BrowserManager } from '../utils/browser.js';
import { cleanText, parseTurkishNumber, parseTurkishDate, parseBoolean, randomDelay, logProgress, findHeaderIndex } from '../utils/helpers.js';
import { fetchIsyatirimUniverse, type IsyatirimUniverseEntry } from '../utils/isyatirim.js';

const MARKET_ALIASES = new Map<string, string>([
  ['YILDIZ PAZAR', 'YILDIZ PAZAR'],
  ['YILDIZ PAZARI', 'YILDIZ PAZAR'],
  ['ANA PAZAR', 'ANA PAZAR'],
  ['ANA PAZARI', 'ANA PAZAR'],
  ['ALT PAZAR', 'ALT PAZAR'],
  ['ALT PAZARI', 'ALT PAZAR'],
  ['YAKIN İZLEME PAZARI', 'YAKIN İZLEME PAZARI'],
  ['YAKIN IZLEME PAZARI', 'YAKIN İZLEME PAZARI'],
  ['PİYASA ÖNCESİ İŞLEM PLATFORMU', 'PİYASA ÖNCESİ İŞLEM PLATFORMU'],
  ['PIYASA ONCESI ISLEM PLATFORMU', 'PİYASA ÖNCESİ İŞLEM PLATFORMU'],
  ['YAPILANDIRILMIŞ ÜRÜNLER VE FON PAZARI', 'YAPILANDIRILMIŞ ÜRÜNLER VE FON PAZARI'],
  ['YAPILANDIRILMIS URUNLER VE FON PAZARI', 'YAPILANDIRILMIŞ ÜRÜNLER VE FON PAZARI'],
  ['EMTİA PAZARI', 'EMTİA PAZARI'],
  ['EMTIA PAZARI', 'EMTİA PAZARI']
]);

const MARKET_PRIORITY = [
  'YILDIZ PAZAR',
  'ANA PAZAR',
  'ALT PAZAR',
  'YAKIN İZLEME PAZARI',
  'PİYASA ÖNCESİ İŞLEM PLATFORMU',
  'YAPILANDIRILMIŞ ÜRÜNLER VE FON PAZARI',
  'EMTİA PAZARI'
];

const MARKET_PRIORITY_LOOKUP = new Map<string, number>(
  MARKET_PRIORITY.map((market, index) => [market, index])
);

const normalizeMarketList = (rawText: string | null): string[] => {
  if (!rawText) {
    return [];
  }

  const parts = rawText
    .split(/[\/,]/)
    .map(segment => {
      const cleaned = cleanText(segment)?.replace(/\(.*?\)/g, '');
      return cleaned ? cleaned.trim() : null;
    })
    .filter((segment): segment is string => Boolean(segment));

  const canonical = parts
    .map(segment => {
      const key = segment.toLocaleUpperCase('tr-TR');
      return MARKET_ALIASES.get(key) ?? null;
    })
    .filter((segment): segment is string => Boolean(segment));

  if (!canonical.length) {
    return [];
  }

  const unique = Array.from(new Set(canonical));
  unique.sort((a, b) => (MARKET_PRIORITY_LOOKUP.get(a) ?? Infinity) - (MARKET_PRIORITY_LOOKUP.get(b) ?? Infinity));

  return unique.length ? [unique[0]] : [];
};

interface ParsedCompanyDetails {
  // Contact Information
  headquartersAddress?: string | null;
  communicationAddress?: string | null;
  communicationPhone?: string | null;
  communicationFax?: string | null;
  productionFacilities?: string[];
  email?: string | null;
  website?: string | null;
  
  // Business Info
  businessScope?: string | null;
  companyDuration?: string | null;
  auditor?: string | null;
  
  // Market/Sector/Indices (will be linked via junction tables)
  sectorName?: string | null;
  subSectorName?: string | null;
  marketNames?: string[];
  indexNames?: string[];
  
  // Registration & Tax
  registryOffice?: string | null;
  registrationDate?: Date | null;
  registrationNumber?: string | null;
  taxNumber?: string | null;
  taxOffice?: string | null;
  
  // Capital
  paidInCapital?: number | null;
  authorizedCapital?: number | null;
  
  // Free Float
  freeFloatEntries?: Array<{
    ticker: string | null;
    amountTL: number | null;
    percentFloat: number | null;
  }>;
  
  // Share classes (Pay Grubu bilgileri)
  shareClasses?: Array<{
    group: string | null;
    nominalValue?: number | null;
    nominalCurrency?: string | null;
    nominalTotal?: number | null;
    totalCurrency?: string | null;
    sharePercent?: number | null;
    privilege?: string | null;
    isTradable?: boolean | null;
  }>;
  
  // Relations (will be stored in separate tables)
  irStaff?: any[];
  boardMembers?: any[];
  executives?: any[];
  shareholders?: any[];
  subsidiaries?: any[];
}

export class CompaniesDetailScraper {
  private browser: BrowserManager;
  private isyatirimLookup: Map<string, IsyatirimUniverseEntry> | null = null;
  private allowedCodes: Set<string> | null = null;
  private isyatirimFetched = false;

  constructor(browser: BrowserManager) {
    this.browser = browser;
  }

  private async ensureIsyatirimLookup(): Promise<void> {
    if (this.isyatirimLookup && this.allowedCodes && this.allowedCodes.size) {
      return;
    }

    try {
      const universe = await fetchIsyatirimUniverse(this.browser);
      this.isyatirimLookup = new Map(universe.entries.map(entry => [entry.code, entry]));
      this.allowedCodes = universe.codeSet;
      this.isyatirimFetched = true;
    } catch (error) {
      this.isyatirimLookup = null;
      this.allowedCodes = null;
      this.isyatirimFetched = false;
      const reason = error instanceof Error ? error.message : String(error);
      throw new Error(`İş Yatırım fihristi yüklenemedi: ${reason}`);
    }
  }

  private async extractTable(page: Page, selector: string): Promise<{ headers: string[]; rows: string[][] } | null> {
    const tableHandle = await page.$(selector);
    if (!tableHandle) {
      return null;
    }

    let headers = await tableHandle.$$eval('thead tr th', cells =>
      cells.map(cell => (cell.textContent ?? '').replace(/\s+/g, ' ').trim())
    );

    const rows = await tableHandle.$$eval('tbody tr', rows =>
      rows.map(row =>
        Array.from((row as any).querySelectorAll('td,th')).map(cell => ((cell as any).textContent ?? '').replace(/\s+/g, ' ').trim())
      )
    );

    if (!headers.length && rows.length) {
      headers = rows[0].map((_, idx) => `Column ${idx + 1}`);
    }

    return { headers, rows };
  }

  private getCellValue(row: string[], index: number): string | null {
    if (index < 0 || index >= row.length) {
      return null;
    }
    return cleanText(row[index]);
  }

  /**
   * Tüm şirketlerin detay bilgilerini kazı
   */
  async scrapeAll(): Promise<void> {
    console.log('\n📋 Şirket detayları kazınıyor...');
    
    await this.ensureIsyatirimLookup();

    const allowedCodes = this.allowedCodes;
    if (!allowedCodes || !allowedCodes.size) {
      throw new Error('İş Yatırım Ulusal-Tüm listesi boş döndü');
    }

    console.log(`✅ İş Yatırım Ulusal-Tüm listesi yüklendi (${allowedCodes.size} kod)`);

    // Veritabanından şirket listesini al
    const companies = await prisma.company.findMany({
      select: { id: true, code: true, name: true, detailUrl: true }
    });

    const filteredCompanies = companies.filter(company => allowedCodes.has(company.code.toUpperCase()));

    if (filteredCompanies.length !== companies.length) {
      const skipped = companies.length - filteredCompanies.length;
      if (skipped > 0) {
        console.log(`ℹ️  İş Yatırım listesinde bulunmayan ${skipped} şirket atlandı`);
      }
    }

    console.log(`✅ ${filteredCompanies.length} şirket bulundu, detaylar kazınacak...`);

    for (let i = 0; i < filteredCompanies.length; i++) {
      const company = filteredCompanies[i];
      if (!company.detailUrl) {
        console.warn(`⚠️  ${company.code} - Detail URL yok, atlanıyor`);
        continue;
      }

      logProgress(i + 1, filteredCompanies.length, `${company.code} - ${company.name}`);

      let success = false;
      let retryCount = 0;
      const maxRetries = 3;

      while (!success && retryCount < maxRetries) {
        try {
          await this.scrapeCompanyDetail(company.id, company.code, company.detailUrl);
          success = true;
          await randomDelay(1000, 2000); // Rate limiting
        } catch (error: any) {
          retryCount++;
          
          // İnternet bağlantısı hatası mı?
          const isNetworkError = error?.message?.includes('ERR_INTERNET_DISCONNECTED') || 
                                  error?.message?.includes('ERR_NETWORK_CHANGED');
          
          if (isNetworkError && retryCount < maxRetries) {
            console.warn(`   ⚠️  ${company.code}: Bağlantı hatası, ${retryCount}. deneme... (3 sn bekleniyor)`);
            await randomDelay(3000, 5000); // Daha uzun bekle
          } else {
            console.error(`   ❌ ${company.code} için hata (${retryCount}/${maxRetries}):`, error?.message || error);
            break; // Başka hata türleri için retry yapma
          }
        }
      }
    }

    console.log('✅ Şirket detayları kazıma tamamlandı');
  }

  /**
   * Tek bir şirketin detaylarını kazı
   */
  async scrapeCompanyDetail(companyId: number, code: string, detailUrl: string): Promise<void> {
    const page = await this.browser.newPage();
    
    try {
      await this.ensureIsyatirimLookup();
      const normalizedCode = code.toUpperCase();

      if (this.allowedCodes && !this.allowedCodes.has(normalizedCode)) {
        console.log(`ℹ️  ${normalizedCode}: İş Yatırım fihristinde yer almıyor, kazıma atlandı`);
        return;
      }
      // "ozet" yerine "genel" kullan
      const generalUrl = detailUrl.replace('/ozet/', '/genel/');
      
      await page.goto(generalUrl, { waitUntil: 'domcontentloaded', timeout: 30000 });

      try {
        await page.waitForSelector('#general', { timeout: 20000, state: 'visible' });
      } catch (initialWaitError) {
        console.warn(`⚠️  ${code}: #general beklenirken timeout, sayfa yenileniyor`);
        await page.reload({ waitUntil: 'domcontentloaded', timeout: 30000 });
        await page.waitForSelector('#general', { timeout: 20000, state: 'visible' });
      }
      
      // Tüm bölümleri genişlet ("Tüm İçeriği Görüntüle" butonuna tıkla)
      await this.expandAllSections(page);
      
      await randomDelay(800, 1200);

      // Tüm bölümleri parse et
  const details = await this.parseAllSections(page);

      // Veritabanına kaydet
  await this.saveCompanyDetails(companyId, normalizedCode, details);

    } catch (error) {
      throw error;
    } finally {
      await page.close();
    }
  }

  /**
   * Tüm collapsible bölümleri genişlet
   */
  private async expandAllSections(page: Page): Promise<void> {
    try {
      // "Tüm İçeriği Görüntüle" butonunu bul ve tıkla
      const toggleLocator = page.locator('#general > div > div > div.flex.gap-3.justify-end.items-center.w-full.h-max.text-sm.font-medium.p-4.company__sgbf-remove > button');

      if (await toggleLocator.count()) {
        const shouldToggle = await toggleLocator.first().evaluate(button => {
          const svg = button.querySelector('svg path:last-child');
          const transform = svg?.getAttribute('transform') ?? '';
          return !transform.includes('rotate');
        }).catch(() => true);

        if (shouldToggle) {
          await toggleLocator.first().scrollIntoViewIfNeeded();
          await toggleLocator.first().click({ timeout: 5000 });
          await randomDelay(400, 600);
        }
      }

      const collapsedSections = page.locator('#general button[aria-expanded="false"]');
      let attempts = 0;
      const maxAttempts = 40;

      while ((await collapsedSections.count()) > 0 && attempts < maxAttempts) {
        const sectionButton = collapsedSections.first();
        await sectionButton.scrollIntoViewIfNeeded();
        await sectionButton.click({ timeout: 5000 });
        await randomDelay(180, 260);
        attempts++;
      }

      if ((await collapsedSections.count()) > 0) {
        console.warn('⚠️  Bazı bölümler açılırken limit aşıldı, kalanlar atlanıyor');
      }
    } catch (error) {
      console.warn('⚠️  Bölümler genişletilirken hata (devam ediliyor):', error);
    }
  }

  /**
   * Tüm bölümleri parse et
   */
  private async parseAllSections(page: Page): Promise<ParsedCompanyDetails> {
    const details: ParsedCompanyDetails = {};

    try {
      // 1. İletişim Bilgileri
      const contact = await this.parseContactInformation(page);
      Object.assign(details, contact);

      // 2. Faaliyet ve Denetim
      const business = await this.parseScopeAndAudit(page);
      Object.assign(details, business);

      // 3. Pazar, Endeks ve Araçlar
      const market = await this.parseMarketsIndices(page);
      Object.assign(details, market);

      // 4. Tescil ve Vergi
      const registry = await this.parseRegistrationTax(page);
      Object.assign(details, registry);

      // 5. Şirket Yönetimi
      const management = await this.parseCompanyManagement(page);
      Object.assign(details, management);

      // 6. Sermaye ve Ortaklık
      const capital = await this.parseCapitalShareholders(page);
      Object.assign(details, capital);

      // 7. Bağlı Ortaklıklar
      const subsidiaries = await this.parseSubsidiaries(page);
      details.subsidiaries = subsidiaries;

    } catch (error) {
      console.warn('⚠️  Parse sırasında hata:', error);
    }

    return details;
  }

  /**
   * 1. İletişim Bilgileri
   */
  private async parseContactInformation(page: Page): Promise<Partial<ParsedCompanyDetails>> {
    const result: Partial<ParsedCompanyDetails> = {};
    const baseSelector = '#general > div > div > div:nth-child(2)';

    try {
      // Merkez Adresi
      const headquartersEl = await page.$(`${baseSelector} > div > div > div > div > div > div:nth-child(1) > div > div > span`);
      if (headquartersEl) {
        result.headquartersAddress = cleanText(await headquartersEl.textContent());
      }

      // İletişim Adresi, Telefon, Faks (tablo)
      const commTable = await page.$(`${baseSelector} > div > div > div > div > div > div:nth-child(2) > div > div.overflow-x-auto.w-full > table > tbody > tr`);
      if (commTable) {
        const cells = await commTable.$$('td');
        if (cells.length >= 3) {
          result.communicationAddress = cleanText(await cells[0].textContent());
          result.communicationPhone = cleanText(await cells[1].textContent());
          result.communicationFax = cleanText(await cells[2].textContent());
        }
      }

      // Üretim Tesisleri
      const facilitiesEl = await page.$(`${baseSelector} > div > div > div > div > div > div:nth-child(3) > div > div > span`);
      if (facilitiesEl) {
        const facilitiesText = cleanText(await facilitiesEl.textContent());
        if (facilitiesText && facilitiesText !== 'Bilgi Mevcut Değil') {
          // Paragrafları ayır
          const paragraphs = await facilitiesEl.$$('p');
          if (paragraphs.length > 0) {
            result.productionFacilities = [];
            for (const p of paragraphs) {
              const text = cleanText(await p.textContent());
              if (text) result.productionFacilities.push(text);
            }
          } else {
            // Satırlara ayır
            const facilityLines = facilitiesText
              .split('\n')
              .map((line: string) => cleanText(line))
              .filter((line): line is string => line !== null);

            result.productionFacilities = facilityLines;
          }
        }
      }

      // E-posta
      const emailEl = await page.$(`${baseSelector} > div > div > div > div > div > div:nth-child(4) > div > div.overflow-x-auto.w-full > table > tbody > tr > td`);
      if (emailEl) {
        result.email = cleanText(await emailEl.textContent());
      }

      // Website
      const websiteEl = await page.$(`${baseSelector} > div > div > div > div > div > div:nth-child(5) > div > div > span`);
      if (websiteEl) {
        result.website = cleanText(await websiteEl.textContent());
      }

      const irTable = await this.extractTable(page, `${baseSelector} > div > div > div > div > div > div:nth-child(6) > div > div.overflow-x-auto.w-full > table`);
      if (irTable && irTable.rows.length) {
        const idxName = findHeaderIndex(irTable.headers, ['Ad-Soyad', 'Adı-Soyadı', 'Ad Soyad']);
        if (idxName !== -1) {
          const idxTitle = findHeaderIndex(irTable.headers, ['Görevi']);
          const idxAssignment = findHeaderIndex(irTable.headers, ['Görevlendirme Tarihi', 'Görevlendirme Tarih']);
          const idxPhone = findHeaderIndex(irTable.headers, ['Telefon']);
          const idxEmail = findHeaderIndex(irTable.headers, ['E-posta', 'E-Posta']);
          const idxLicenseType = findHeaderIndex(irTable.headers, ['Lisans Belgesi Türü', 'Lisans Türü']);
          const idxLicenseNumber = findHeaderIndex(irTable.headers, ['Lisans Belge No', 'Lisans No']);

          result.irStaff = [];
          let currentStaff: any | null = null;

          for (const row of irTable.rows) {
            const fullName = this.getCellValue(row, idxName);
            const licenseType = this.getCellValue(row, idxLicenseType);
            const licenseNumber = this.getCellValue(row, idxLicenseNumber);

            if (fullName) {
              const assignmentDateText = this.getCellValue(row, idxAssignment);
              const licenseEntries = [] as Array<{ type: string | null; number: string | null }>;
              if (licenseType || licenseNumber) {
                licenseEntries.push({ type: licenseType ?? null, number: licenseNumber ?? null });
              }

              currentStaff = {
                fullName,
                title: this.getCellValue(row, idxTitle),
                assignmentDate: assignmentDateText ? parseTurkishDate(assignmentDateText) : null,
                phone: this.getCellValue(row, idxPhone),
                email: this.getCellValue(row, idxEmail),
                licenses: licenseEntries.length > 0 ? licenseEntries : null
              };

              result.irStaff.push(currentStaff);
            } else if (currentStaff && (licenseType || licenseNumber)) {
              const licensesArray = (currentStaff.licenses as Array<{ type: string | null; number: string | null }> | null) ?? [];
              licensesArray.push({ type: licenseType ?? null, number: licenseNumber ?? null });
              currentStaff.licenses = licensesArray;
            }
          }
        }
      }

    } catch (error) {
      console.warn('⚠️  İletişim bilgileri parse hatası:', error);
    }

    return result;
  }

  /**
   * 2. Faaliyet ve Denetim
   */
  private async parseScopeAndAudit(page: Page): Promise<Partial<ParsedCompanyDetails>> {
    const result: Partial<ParsedCompanyDetails> = {};
    const baseSelector = '#general > div > div > div:nth-child(3)';

    try {
      // Faaliyet Konusu
      const scopeEl = await page.$(`${baseSelector} > div > div > div > div > div > div > div:nth-child(1) > div > span > p`);
      if (scopeEl) {
        result.businessScope = cleanText(await scopeEl.textContent());
      }

      // Şirketin Süresi
      const durationEl = await page.$(`${baseSelector} > div > div > div > div > div > div > div:nth-child(2) > div > span`);
      if (durationEl) {
        result.companyDuration = cleanText(await durationEl.textContent());
      }

      // Bağımsız Denetim Kuruluşu
      const auditorEl = await page.$(`${baseSelector} > div > div > div > div > div > div > div:nth-child(3) > div > span`);
      if (auditorEl) {
        result.auditor = cleanText(await auditorEl.textContent());
      }

      // Sektör
      const sectorEl = await page.$(`${baseSelector} > div > div > div > div > div > div > div:nth-child(4) > div > span`);
      if (sectorEl) {
        const sectorText = cleanText(await sectorEl.textContent());
        if (sectorText) {
          // "ANA SEKTÖR / ALT SEKTÖR" formatında olabilir
          const parts = sectorText.split('/').map((segment: string) => segment.trim());
          result.sectorName = parts[0];
          result.subSectorName = parts.length > 1 ? parts[1] : undefined;
        }
      }

    } catch (error) {
      console.warn('⚠️  Faaliyet bilgileri parse hatası:', error);
    }

    return result;
  }

  /**
   * 3. Pazar, Endeks ve Araçlar
   */
  private async parseMarketsIndices(page: Page): Promise<Partial<ParsedCompanyDetails>> {
    const result: Partial<ParsedCompanyDetails> = {};
    const baseSelector = '#general > div > div > div:nth-child(4)';

    try {
      // Pazar
      const marketEl = await page.$(`${baseSelector} > div > div > div > div > div > div:nth-child(1) > div:nth-child(1) > div > span`);
      if (marketEl) {
        const marketText = cleanText(await marketEl.textContent());
        const normalized = normalizeMarketList(marketText ?? null);
        if (normalized.length > 0) {
          result.marketNames = normalized;
        }
      }

      // Endeksler
      const indicesEl = await page.$(`${baseSelector} > div > div > div > div > div > div:nth-child(1) > div:nth-child(2) > div > span`);
      if (indicesEl) {
        const indicesText = cleanText(await indicesEl.textContent());
        if (indicesText) {
          // Endeksler "/" ile ayrılmış, tekrar edenleri filtrele
          const cleanedIndices = indicesText
            .split('/')
            .map((indexName: string) => indexName.trim())
            .filter((indexName: string): indexName is string => indexName.length > 0);

          const uniqueIndices = Array.from(new Set<string>(cleanedIndices));

          if (uniqueIndices.length > 0) {
            result.indexNames = uniqueIndices;
          }
        }
      }

    } catch (error) {
      console.warn('⚠️  Pazar/Endeks bilgileri parse hatası:', error);
    }

    return result;
  }

  /**
   * 4. Tescil ve Vergi
   */
  private async parseRegistrationTax(page: Page): Promise<Partial<ParsedCompanyDetails>> {
    const result: Partial<ParsedCompanyDetails> = {};
    const baseSelector = '#general > div > div > div:nth-child(5)';

    try {
      // Ticaret Sicil Memurluğu
      const officeEl = await page.$(`${baseSelector} > div > div > div > div > div > div > div:nth-child(1) > div > span`);
      if (officeEl) result.registryOffice = cleanText(await officeEl.textContent());

      // Tescil Tarihi
      const dateEl = await page.$(`${baseSelector} > div > div > div > div > div > div > div:nth-child(2) > div > span`);
      if (dateEl) result.registrationDate = parseTurkishDate(await dateEl.textContent());

      // Ticaret Sicil Numarası
      const regNumEl = await page.$(`${baseSelector} > div > div > div > div > div > div > div:nth-child(3) > div > span`);
      if (regNumEl) result.registrationNumber = cleanText(await regNumEl.textContent());

      // Vergi No
      const taxNumEl = await page.$(`${baseSelector} > div > div > div > div > div > div > div:nth-child(4) > div > span`);
      if (taxNumEl) result.taxNumber = cleanText(await taxNumEl.textContent());

      // Vergi Dairesi
      const taxOfficeEl = await page.$(`${baseSelector} > div > div > div > div > div > div > div:nth-child(5) > div > span`);
      if (taxOfficeEl) result.taxOffice = cleanText(await taxOfficeEl.textContent());

    } catch (error) {
      console.warn('⚠️  Tescil/Vergi bilgileri parse hatası:', error);
    }

    return result;
  }

  /**
   * 5. Şirket Yönetimi (Board Members + Executives)
   */
  private async parseCompanyManagement(page: Page): Promise<Partial<ParsedCompanyDetails>> {
    const result: Partial<ParsedCompanyDetails> = {};
    const baseSelector = '#general > div > div > div:nth-child(6)';

    try {
      const boardTable = await this.extractTable(page, `${baseSelector} > div > div > div > div > div > div:nth-child(1) > div > div.overflow-x-auto.w-full > table`);
      if (boardTable && boardTable.rows.length) {
        const idxName = findHeaderIndex(boardTable.headers, ['Adı-Soyadı', 'Ad Soyadı', 'Ad - Soyad']);
        if (idxName !== -1) {
          const idxActing = findHeaderIndex(boardTable.headers, ['Tüzel Kişi Üye Adına Hareket Eden Kişi', 'Tüzel Kişi']);
          const idxGender = findHeaderIndex(boardTable.headers, ['Cinsiyeti', 'Cinsiyet']);
          const idxTitle = findHeaderIndex(boardTable.headers, ['Görevi']);
          const idxProfession = findHeaderIndex(boardTable.headers, ['Mesleği']);
          const idxFirstElection = findHeaderIndex(boardTable.headers, ['Yönetim Kuruluna İlk Seçilme Tarihi', 'İlk Seçilme Tarihi']);
          const idxIsExecutive = findHeaderIndex(boardTable.headers, ['İcrada Görevli Olup Olmadığı', 'İcrada Görevli']);
          const idxRolesFiveYears = findHeaderIndex(boardTable.headers, ['Son 5 Yılda Ortaklıkta Üstlendiği Görevler', 'Son 5 Yılda Üstlendiği Görevler']);
          const idxExternalRoles = findHeaderIndex(boardTable.headers, ['Son Durum itibariyle Ortaklık Dışında Aldığı Görevler', 'Ortaklık Dışında Aldığı Görevler']);
          const idxHasFinancialExp = findHeaderIndex(boardTable.headers, ['Denetim, Muhasebe ve/veya Finans Alanında En Az 5 Yıllık Deneyime Sahip Olup Olmadığı', 'Finans Alanında En Az 5 Yıllık Deneyim']);
          const idxSharePercent = findHeaderIndex(boardTable.headers, ['Sermayedeki Payı (%)', 'Sermayedeki Payı(%)']);
          const idxShareGroup = findHeaderIndex(boardTable.headers, ['Temsil Ettiği Pay Grubu', 'Pay Grubu']);
          const idxIsIndependent = findHeaderIndex(boardTable.headers, ['Bağımsız Yönetim Kurulu Üyesi Olup Olmadığı', 'Bağımsız Üye']);
          const idxIndependenceDisclosure = findHeaderIndex(boardTable.headers, ['Bağımsızlık Beyanının Yer Aldığı KAP Duyurusunun Bağlantısı', 'Bağımsızlık Beyanı']);
          const idxNomCommittee = findHeaderIndex(boardTable.headers, ['Bağımsız Üyenin Aday Gösterme Komitesi Tarafından Değerlendirilip Değerlendirilmediği', 'Aday Gösterme Komitesi Değerlendirmesi']);
          const idxLostIndependence = findHeaderIndex(boardTable.headers, ['Bağımsızlığını Kaybeden Üye Olup Olmadığı', 'Bağımsızlığını Kaybetti mi']);
          const idxCommittees = findHeaderIndex(boardTable.headers, ['Yer Aldığı Komiteler ve Görevi', 'Komiteler']);

          result.boardMembers = [];

          for (const row of boardTable.rows) {
            const fullName = this.getCellValue(row, idxName);
            if (!fullName) {
              continue;
            }

            const actingForLegalEntity = this.getCellValue(row, idxActing);
            const gender = this.getCellValue(row, idxGender);
            const title = this.getCellValue(row, idxTitle);
            const profession = this.getCellValue(row, idxProfession);
            const firstElection = this.getCellValue(row, idxFirstElection);
            const isExecutiveText = this.getCellValue(row, idxIsExecutive);
            const rolesFiveYears = this.getCellValue(row, idxRolesFiveYears);
            const externalRoles = this.getCellValue(row, idxExternalRoles);
            const hasFinancialExpText = this.getCellValue(row, idxHasFinancialExp);
            const sharePercentText = this.getCellValue(row, idxSharePercent);
            const shareGroup = this.getCellValue(row, idxShareGroup);
            const isIndependentText = this.getCellValue(row, idxIsIndependent);
            const independenceDisclosure = this.getCellValue(row, idxIndependenceDisclosure);
            const nomCommitteeText = this.getCellValue(row, idxNomCommittee);
            const lostIndependenceText = this.getCellValue(row, idxLostIndependence);
            const committees = this.getCellValue(row, idxCommittees);

            let isExecutive = isExecutiveText ? parseBoolean(isExecutiveText) : null;
            if (isExecutive === null && isExecutiveText) {
              const upper = isExecutiveText.toUpperCase();
              if (upper.includes('DEĞİL')) {
                isExecutive = false;
              } else if (upper.includes('GÖREVLİ')) {
                isExecutive = true;
              }
            }

            let hasFinancialExp = hasFinancialExpText ? parseBoolean(hasFinancialExpText) : null;
            if (hasFinancialExp === null && hasFinancialExpText) {
              const upper = hasFinancialExpText.toUpperCase();
              if (upper.includes('EVET')) {
                hasFinancialExp = true;
              } else if (upper.includes('HAYIR')) {
                hasFinancialExp = false;
              }
            }

            let isIndependent = isIndependentText ? parseBoolean(isIndependentText) : null;
            if (isIndependent === null && isIndependentText) {
              const upper = isIndependentText.toUpperCase();
              if (upper.includes('DEĞİL')) {
                isIndependent = false;
              } else if (upper.includes('BAĞIMSIZ')) {
                isIndependent = true;
              }
            }

            let evaluatedByNomCommittee = nomCommitteeText ? parseBoolean(nomCommitteeText) : null;
            if (evaluatedByNomCommittee === null && nomCommitteeText) {
              const upper = nomCommitteeText.toUpperCase();
              if (upper.includes('DEĞERLENDİRİLDİ')) {
                evaluatedByNomCommittee = true;
              } else if (upper.includes('DEĞERLENDİRİLMEDİ')) {
                evaluatedByNomCommittee = false;
              }
            }

            const lostIndependence = lostIndependenceText ? parseBoolean(lostIndependenceText) : null;

            result.boardMembers.push({
              fullName,
              actingForLegalEntity,
              gender,
              title,
              profession,
              firstElectionDate: firstElection ? parseTurkishDate(firstElection) : null,
              isExecutive,
              rolesLast5Years: rolesFiveYears,
              externalRoles,
              has5yFinExp: hasFinancialExp,
              sharePercent: sharePercentText ? parseTurkishNumber(sharePercentText) : null,
              representedShareGroup: shareGroup,
              isIndependent,
              independenceDisclosure,
              evaluatedByNomCommittee,
              lostIndependence,
              committees
            });
          }
        }
      }

      const execTable = await this.extractTable(page, `${baseSelector} > div > div > div > div > div > div:nth-child(2) > div > div.overflow-x-auto.w-full > table`);
      if (execTable && execTable.rows.length) {
        const idxName = findHeaderIndex(execTable.headers, ['Adı-Soyadı', 'Ad Soyadı', 'Ad - Soyad']);
        if (idxName !== -1) {
          const idxTitle = findHeaderIndex(execTable.headers, ['Görevi']);
          const idxProfession = findHeaderIndex(execTable.headers, ['Mesleği']);
          const idxRolesFiveYears = findHeaderIndex(execTable.headers, ['Son 5 Yılda Ortaklıkta Üstlendiği Görevler', 'Son 5 Yılda Üstlendiği Görevler']);
          const idxExternalRoles = findHeaderIndex(execTable.headers, ['Son Durum İtibariyle Ortaklık Dışında Aldığı Görevler', 'Ortaklık Dışında Aldığı Görevler']);

          result.executives = [];

          for (const row of execTable.rows) {
            const fullName = this.getCellValue(row, idxName);
            if (!fullName) {
              continue;
            }

            result.executives.push({
              fullName,
              title: this.getCellValue(row, idxTitle),
              profession: this.getCellValue(row, idxProfession),
              rolesLast5Years: this.getCellValue(row, idxRolesFiveYears),
              externalRoles: this.getCellValue(row, idxExternalRoles)
            });
          }
        }
      }

    } catch (error) {
      console.warn('⚠️  Yönetim bilgileri parse hatası:', error);
    }

    return result;
  }

  /**
   * 6. Sermaye ve Ortaklık
   */
  private async parseCapitalShareholders(page: Page): Promise<Partial<ParsedCompanyDetails>> {
    const result: Partial<ParsedCompanyDetails> = {};
    const baseSelector = '#general > div > div > div:nth-child(7)';

    try {
      let headlinePaidInCapital: number | null = null;

      // Ödenmiş Sermaye
      const paidCapitalEl = await page.$(`${baseSelector} > div > div > div > div > div > div:nth-child(1) > div:nth-child(1) > div > span`);
      if (paidCapitalEl) {
        headlinePaidInCapital = parseTurkishNumber(await paidCapitalEl.textContent());
      }

      // Kayıtlı Sermaye Tavanı
      const authCapitalEl = await page.$(`${baseSelector} > div > div > div > div > div > div:nth-child(1) > div:nth-child(2) > div > span`);
      if (authCapitalEl) {
        result.authorizedCapital = parseTurkishNumber(await authCapitalEl.textContent());
      }

      const shareholderTable = await this.extractTable(page, `${baseSelector} > div > div > div > div > div > div:nth-child(2) > div > div.overflow-x-auto.w-full > table`);
      if (shareholderTable && shareholderTable.rows.length) {
        const idxName = findHeaderIndex(shareholderTable.headers, ['Ortağın Adı-Soyadı/Ticaret Ünvanı', 'Ortağın Adı', 'Ortak']);
        if (idxName !== -1) {
          const idxAmount = findHeaderIndex(shareholderTable.headers, ['Sermayedeki Payı(TL)', 'Sermayedeki Payı (TL)', 'Payı (TL)']);
          const idxPercent = findHeaderIndex(shareholderTable.headers, ['Sermayedeki Payı (%)', 'Sermayedeki Payı(%)', 'Payı (%)']);
          const idxVoting = findHeaderIndex(shareholderTable.headers, ['Oy Hakkı Oranı(%)', 'Oy Hakkı Oranı (%)']);

          result.shareholders = [];

          for (const row of shareholderTable.rows) {
            const name = this.getCellValue(row, idxName);
            if (!name || name.toUpperCase().includes('TOPLAM')) {
              continue;
            }

            const amount = this.getCellValue(row, idxAmount);
            const percent = this.getCellValue(row, idxPercent);
            const voting = this.getCellValue(row, idxVoting);

            result.shareholders.push({
              name,
              shareAmountTL: amount ? parseTurkishNumber(amount) : null,
              sharePercent: percent ? parseTurkishNumber(percent) : null,
              votingPercent: voting ? parseTurkishNumber(voting) : null
            });
          }
        }
      }

      // Fiili Dolaşımdaki Paylar (Modal Popup)
      try {
        result.freeFloatEntries = await this.parseFreeFloat(page, baseSelector);
      } catch (freeFloatError) {
        console.warn('⚠️  FreeFloat bilgisi alınamadı:', freeFloatError);
        result.freeFloatEntries = [];
      }

      // Sermayeyi Temsil Eden Paylara İlişkin Bilgi (pay grupları)
      let shareClasses = [] as NonNullable<ParsedCompanyDetails['shareClasses']>;
      try {
        shareClasses = await this.parseShareRepresentation(page, baseSelector);
      } catch (shareClassError) {
        console.warn('⚠️  Pay grubu bilgisi alınamadı:', shareClassError);
      }

      result.shareClasses = shareClasses;

      if (shareClasses.length) {
        const nominalTotals = shareClasses
          .map(item => item?.nominalTotal)
          .filter((value): value is number => typeof value === 'number' && !Number.isNaN(value));

        if (nominalTotals.length) {
          const nominalSum = nominalTotals.reduce((acc, value) => acc + value, 0);
          if (nominalSum > 0) {
            // Pay grubu toplamları şirketin gerçek ödenmiş sermayesini temsil eder.
            result.paidInCapital = Number(nominalSum.toFixed(2));
          }
        }
      }

      if (result.paidInCapital === undefined) {
        result.paidInCapital = headlinePaidInCapital;
      }

      if (result.paidInCapital === undefined) {
        result.paidInCapital = null;
      }

    } catch (error) {
      console.warn('⚠️  Sermaye/Ortaklık bilgileri parse hatası:', error);
    }

    return result;
  }

  /**
   * Fiili Dolaşımdaki Paylar (Modal Popup'tan)
   * 
   * İki durum var:
   * 1. Ana sayfada veri varsa → Direkt alınır (modal açılmadan)
   * 2. Ana sayfada "Bilgi Mevcut Değil" yazıyorsa → Modal popup açılır, en güncel (ilk satır) alınır
   */
  private async parseFreeFloat(page: Page, baseSelector: string): Promise<Array<{ticker: string | null, amountTL: number | null, percentFloat: number | null}>> {
    try {
      const rows: Array<{ticker: string | null, amountTL: number | null, percentFloat: number | null}> = [];
      const inlineTable = await this.extractTable(page, `${baseSelector} > div > div > div > div > div > div:nth-child(5) > div > div.overflow-x-auto.w-full > table`);
      if (inlineTable && inlineTable.rows.length) {
        const idxTicker = findHeaderIndex(inlineTable.headers, ['Borsa Kodu', 'Kod']);
        const idxAmount = findHeaderIndex(inlineTable.headers, ['Fiili Dolaşımdaki Pay Tutarı(TL)', 'Fiili Dolaşımdaki Pay Tutarı (TL)', 'Pay Tutarı']);
        const idxPercent = findHeaderIndex(inlineTable.headers, ['Fiili Dolaşımdaki Pay Oranı(%)', 'Fiili Dolaşımdaki Pay Oranı (%)', 'Pay Oranı']);

        for (const row of inlineTable.rows) {
          const ticker = this.getCellValue(row, idxTicker);
          const amountText = this.getCellValue(row, idxAmount);
          const percentText = this.getCellValue(row, idxPercent);

          if (!ticker && !amountText && !percentText) {
            continue;
          }

          rows.push({
            ticker: ticker ?? null,
              amountTL: amountText ? parseTurkishNumber(amountText) : null,
              percentFloat: percentText ? parseTurkishNumber(percentText) : null
          });
        }

        if (rows.length) {
          return rows;
        }
      }

      // "Fiili Dolaşımdaki Paylar" başlığındaki ikinci ikonu bul (bildirim/geçmiş ikonu)
      const historyButtonSelector = `${baseSelector} > div > div > div > div > div > div:nth-child(5) > div > div.flex.items-center.justify-between.py-4.company__sgbf-h6-title > div.flex.gap-3.justify-end.company__sgbf-remove > button:nth-child(2)`;

      const maxModalClickAttempts = 3;
      let modalTriggered = false;

      for (let attempt = 0; attempt < maxModalClickAttempts && !modalTriggered; attempt++) {
        const historyButton = page.locator(historyButtonSelector).first();

        if (!(await historyButton.count())) {
          return rows;
        }

        try {
          await historyButton.waitFor({ state: 'visible', timeout: 5000 });
          await historyButton.scrollIntoViewIfNeeded();
          await historyButton.click({ force: true, timeout: 5000 });
          modalTriggered = true;
        } catch (clickError) {
          const message = clickError instanceof Error ? clickError.message : String(clickError);
          console.warn(`   ⚠️  FreeFloat modal butonuna tıklanamadı (deneme ${attempt + 1}/${maxModalClickAttempts}): ${message}`);
          if (attempt === maxModalClickAttempts - 1) {
            throw clickError;
          }
          await randomDelay(400, 700);
        }
      }

      if (!modalTriggered) {
        return rows;
      }

      const modalLocator = page.locator('div[role="dialog"], div[aria-modal="true"]').first();

      try {
        await modalLocator.waitFor({ state: 'visible', timeout: 10000 });
        await randomDelay(600, 900);
      } catch (waitError) {
        console.warn('   ⚠️  FreeFloat modal açılamadı (timeout)');
        return rows;
      }

      const modalFirstRow = modalLocator.locator('table tbody tr').first();

      if (!(await modalFirstRow.count())) {
        console.warn('   ⚠️  FreeFloat modal tablosu bulunamadı');
        await this.closeModal(modalLocator);
        return rows;
      }

      const modalRows = modalLocator.locator('table tbody tr');
      const rowCount = await modalRows.count();

      if (!rowCount) {
        console.warn('   ⚠️  FreeFloat modal satırları bulunamadı');
        await this.closeModal(modalLocator);
        return rows;
      }

  const maxRowsToParse = Math.min(rowCount, 1);

      const modalEntries = await modalLocator.evaluate((modalElement, limit) => {
        const collected: Array<{ ticker: string | null; amount: string | null; percent: string | null }> = [];
        const modal = modalElement as any;
        const rows = Array.from((modal?.querySelectorAll?.('table tbody tr') ?? [])) as any[];

        for (let index = 0; index < rows.length && collected.length < limit; index++) {
          const row = rows[index] as any;
          const cells = Array.from(row?.querySelectorAll?.('td') ?? []) as any[];
          if (cells.length < 3) {
            continue;
          }

          collected.push({
            ticker: cells[0]?.textContent ?? null,
            amount: cells[1]?.textContent ?? null,
            percent: cells[2]?.textContent ?? null
          });
        }

        return collected;
      }, maxRowsToParse);

      for (const entry of modalEntries) {
        const ticker = cleanText(entry.ticker);
        const amountTL = entry.amount ? parseTurkishNumber(entry.amount) : null;
        const percentFloat = entry.percent ? parseTurkishNumber(entry.percent) : null;

        if (ticker || amountTL || percentFloat) {
          rows.push({
            ticker: ticker ?? null,
            amountTL,
            percentFloat
          });
        }
      }

  await this.closeModal(modalLocator);

      return rows;

    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      console.warn(`   ⚠️  FreeFloat parse hatası: ${message}`);
      // Hata durumunda modal'ı kapatmaya çalış
      try {
        const modalLocator = page.locator('div[role="dialog"], div[aria-modal="true"]').first();
        await this.closeModal(modalLocator);
      } catch {}
      
      // Hata dönmeyelim, sadece null dönelim (bazı şirketlerde olmayabilir)
  return [];
    }
  }

  private async closeModal(modalLocator: Locator): Promise<void> {
    try {
      if (!(await modalLocator.count())) {
        return;
      }

      const closeButton = modalLocator.locator('button[aria-label], button[title], button:not([disabled])').first();
      if (await closeButton.count()) {
        await closeButton.click({ timeout: 3000 });
        await randomDelay(180, 260);
        return;
      }

      const fallbackButton = modalLocator.locator('button').first();
      if (await fallbackButton.count()) {
        await fallbackButton.click({ timeout: 3000 });
        await randomDelay(180, 260);
      }
    } catch (modalCloseError) {
      console.warn('   ⚠️  Modal kapatılırken hata:', modalCloseError);
    }
  }

  /**
   * Sermayeyi Temsil Eden Paylara İlişkin Bilgi
   * "Borsada İşlem Görüp Görmediği" sütununda "İşlem Görüyor" varsa true döner
   * 
   * ÖNEMLİ: Tabloda birden fazla satır olabilir (Ayrıcalıklı paylar, imtiyazlı paylar vb.)
   * TÜM SATIRLARI tarayıp herhangi birinde "İşlem Görüyor" varsa true döneriz.
   * 
   * baseSelector: #general > div > div > div:nth-child(7)
   * Tablo: baseSelector > div > div > div > div > div > div:nth-child(7) > div > div.overflow-x-auto.w-full > table
   * "Borsada İşlem Görüp Görmediği" sütunu: 9. sütun (index 8)
   */
  private async parseShareRepresentation(page: Page, baseSelector: string): Promise<Array<{ group: string | null; isTradable: boolean | null; nominalValue?: number | null; nominalCurrency?: string | null; nominalTotal?: number | null; totalCurrency?: string | null; sharePercent?: number | null; privilege?: string | null }>> {
    try {
      const table = await this.extractTable(page, `${baseSelector} > div > div > div > div > div > div:nth-child(7) > div > div.overflow-x-auto.w-full > table`);
      if (!table || !table.rows.length) {
        return [];
      }

      const idxGroup = findHeaderIndex(table.headers, ['Pay Grubu', 'Grup']);
      const idxStatus = findHeaderIndex(table.headers, ['Borsada İşlem Görüp Görmediği', 'İşlem Durumu']);
      const idxNominalValue = findHeaderIndex(table.headers, ['Beher Payın Nominal Değeri (TL)', 'Nominal Değer']);
      const idxNominalCurrency = findHeaderIndex(table.headers, ['Para Birimi', 'Nominal Değeri Para Birimi']);
      const idxNominalTotal = findHeaderIndex(table.headers, ['Payların Nominal Değeri', 'Nominal Tutar']);
      const idxTotalCurrency = findHeaderIndex(table.headers, ['Para Birimi', 'Tutar Para Birimi']);
      const idxPercent = findHeaderIndex(table.headers, ['Sermayeye Oranı', 'Sermaye Oranı']);
      const idxPrivilege = findHeaderIndex(table.headers, ['İmtiyaz Türü', 'İmtiyaz']);

      const rows: Array<{ group: string | null; isTradable: boolean | null; nominalValue?: number | null; nominalCurrency?: string | null; nominalTotal?: number | null; totalCurrency?: string | null; sharePercent?: number | null; privilege?: string | null }> = [];

      for (const row of table.rows) {
        const group = idxGroup !== -1 ? this.getCellValue(row, idxGroup) : null;
        if (group && group.toUpperCase().includes('TOPLAM')) {
          continue;
        }
        const status = idxStatus !== -1 ? this.getCellValue(row, idxStatus) : null;
        const statusUpper = status?.toUpperCase() ?? '';

        let isTradable: boolean | null = null;
        if (statusUpper.includes('İŞLEM GÖRÜYOR') || statusUpper.includes('GÖRÜYOR')) {
          isTradable = true;
        } else if (statusUpper.includes('GÖRMÜYOR') || statusUpper.includes('İŞLEM YOK')) {
          isTradable = false;
        }

        const nominalValueText = idxNominalValue !== -1 ? this.getCellValue(row, idxNominalValue) : null;
        const nominalTotalText = idxNominalTotal !== -1 ? this.getCellValue(row, idxNominalTotal) : null;
        const sharePercentText = idxPercent !== -1 ? this.getCellValue(row, idxPercent) : null;

        rows.push({
          group,
          isTradable,
          nominalValue: nominalValueText ? parseTurkishNumber(nominalValueText) : null,
          nominalCurrency: idxNominalCurrency !== -1 ? this.getCellValue(row, idxNominalCurrency) : null,
          nominalTotal: nominalTotalText ? parseTurkishNumber(nominalTotalText) : null,
          totalCurrency: idxTotalCurrency !== -1 ? this.getCellValue(row, idxTotalCurrency) : null,
          sharePercent: sharePercentText ? parseTurkishNumber(sharePercentText) : null,
          privilege: idxPrivilege !== -1 ? this.getCellValue(row, idxPrivilege) : null
        });
      }

      return rows;

    } catch (error) {
      return [];
    }
  }

  /**
   * 7. Bağlı Ortaklıklar
   */
  private async parseSubsidiaries(page: Page): Promise<any[]> {
    const subsidiaries: any[] = [];
    const baseSelector = '#general > div > div > div:nth-child(8)';

    try {
      const rows = await page.$$(`${baseSelector} > div > div > div > div > div > div > div > div.overflow-x-auto.w-full > table > tbody > tr`);
      
      for (const row of rows) {
        const cells = await row.$$('td');
        if (cells.length >= 7) {
          const tradeName = cleanText(await cells[0].textContent());
          if (tradeName) {
            subsidiaries.push({
              tradeName,
              activity: cleanText(await cells[1].textContent()),
              paidInCapital: parseTurkishNumber(await cells[2].textContent()),
              companyShareAmount: parseTurkishNumber(await cells[3].textContent()),
              currency: cleanText(await cells[4].textContent()),
              sharePercent: parseTurkishNumber(await cells[5].textContent()),
              relationType: cleanText(await cells[6].textContent())
            });
          }
        }
      }

    } catch (error) {
      console.warn('⚠️  Bağlı ortaklık bilgileri parse hatası:', error);
    }

    return subsidiaries;
  }

  /**
   * Parse edilen detayları veritabanına kaydet
   */
  private async saveCompanyDetails(companyId: number, code: string, details: ParsedCompanyDetails): Promise<void> {
    try {
      const normalizedCode = code.toUpperCase();
      const fallbackEntry = this.isyatirimLookup?.get(normalizedCode) ?? null;

      const paidInCapitalFromDetails = details.paidInCapital ?? null;
      const paidInCapitalFromFallback = fallbackEntry?.paidInCapitalMn != null
        ? Number((fallbackEntry.paidInCapitalMn * 1_000_000).toFixed(2))
        : null;
      const paidInCapital = paidInCapitalFromDetails ?? paidInCapitalFromFallback ?? null;

      // Ana şirket bilgilerini güncelle
      await prisma.company.update({
        where: { id: companyId },
        data: {
          headquartersAddress: details.headquartersAddress,
          communicationAddress: details.communicationAddress,
          communicationPhone: details.communicationPhone,
          communicationFax: details.communicationFax,
          productionFacilities: details.productionFacilities || [],
          email: details.email,
          website: details.website,
          businessScope: details.businessScope,
          companyDuration: details.companyDuration,
          auditor: details.auditor,
          registryOffice: details.registryOffice,
          registrationDate: details.registrationDate,
          registrationNumber: details.registrationNumber,
          taxNumber: details.taxNumber,
          taxOffice: details.taxOffice,
          paidInCapital,
          authorizedCapital: details.authorizedCapital,
          lastScrapedAt: new Date()
        }
      });

      // Sektör ilişkilendirmesi
      if (details.sectorName) {
        const mainSector = await prisma.mainSector.findUnique({ where: { name: details.sectorName } });
        if (mainSector) {
          let subSectorId = undefined;
          if (details.subSectorName) {
            const subSector = await prisma.subSector.findFirst({
              where: { name: details.subSectorName, mainSectorId: mainSector.id }
            });
            subSectorId = subSector?.id;
          }
          
          await prisma.company.update({
            where: { id: companyId },
            data: { mainSectorId: mainSector.id, subSectorId }
          });
        }
      }

      // Pazar ilişkilendirmesi (many-to-many)
      if (details.marketNames && details.marketNames.length > 0) {
        // Önce mevcut ilişkileri sil
        await prisma.companyMarket.deleteMany({ where: { companyId } });
        
        // Yeni ilişkileri ekle
        for (const marketName of details.marketNames) {
          const market = await prisma.market.findUnique({ where: { name: marketName } });
          if (market) {
            await prisma.companyMarket.create({
              data: { companyId, marketId: market.id }
            });
          }
        }
      }

      // Endeks ilişkilendirmesi (many-to-many)
      // NOT: Bu kısım artık indices-scraper tarafından yapılıyor (kod bazlı eşleştirme)
      // Burada sadece parseMarketsIndices() sonucu details.indexNames'e kaydediliyor,
      // ancak veritabanına yazılmıyor. İlişkilendirme indices-scraper.linkCompaniesToIndices() ile yapılıyor.
      
      // if (details.indexNames && details.indexNames.length > 0) {
      //   await prisma.companyIndex.deleteMany({ where: { companyId } });
      //   for (const indexName of details.indexNames) {
      //     const index = await prisma.index.findUnique({ where: { name: indexName } });
      //     if (index) {
      //       await prisma.companyIndex.create({
      //         data: { companyId, indexId: index.id }
      //       });
      //     }
      //   }
      // }

      // IR Staff
      if (details.irStaff && details.irStaff.length > 0) {
        await prisma.iRStaff.deleteMany({ where: { companyId } });
        for (const staff of details.irStaff) {
          await prisma.iRStaff.create({
            data: { companyId, ...staff }
          });
        }
      }

      // Board Members
      if (details.boardMembers && details.boardMembers.length > 0) {
        await prisma.boardMember.deleteMany({ where: { companyId } });
        for (const member of details.boardMembers) {
          await prisma.boardMember.create({
            data: { companyId, ...member }
          });
        }
      }

      // Executives
      if (details.executives && details.executives.length > 0) {
        await prisma.executive.deleteMany({ where: { companyId } });
        for (const exec of details.executives) {
          await prisma.executive.create({
            data: { companyId, ...exec }
          });
        }
      }

      // Shareholders
      if (details.shareholders && details.shareholders.length > 0) {
        await prisma.shareholder.deleteMany({ where: { companyId } });
        for (const shareholder of details.shareholders) {
          await prisma.shareholder.create({
            data: { companyId, ...shareholder }
          });
        }
      }

      // Subsidiaries
      if (details.subsidiaries && details.subsidiaries.length > 0) {
        await prisma.subsidiary.deleteMany({ where: { companyId } });
        for (const subsidiary of details.subsidiaries) {
          await prisma.subsidiary.create({
            data: { companyId, ...subsidiary }
          });
        }
      }

      const freeFloatEntries = details.freeFloatEntries ?? [];
      const shareClasses = details.shareClasses ?? [];

      const freeFloatEntry = freeFloatEntries.find(entry => entry.ticker?.toUpperCase() === normalizedCode);

      const shareClassMatch = shareClasses.find(shareClass => {
        if (!shareClass.group) {
          return false;
        }

        const upperGroup = shareClass.group
          .toUpperCase()
          .replace(/GRUBU|GRUB|GRP|GR\.|HİSSE|PAY/gi, '')
          .replace(/[^A-Z0-9ÇĞİÖŞÜ]/g, '')
          .trim();

        if (!upperGroup) {
          return false;
        }

        if (normalizedCode.endsWith(upperGroup)) {
          return true;
        }

        return normalizedCode.includes(upperGroup);
      });

      const freeFloatPercentValue = freeFloatEntry?.percentFloat ?? (fallbackEntry?.freeFloatPercent ?? null);
      const hasFreeFloatIndicator = Boolean(freeFloatEntry?.ticker) || (freeFloatPercentValue != null && freeFloatPercentValue > 0);

      let isTradable: boolean | null = null;
      if (shareClassMatch && shareClassMatch.isTradable !== null && shareClassMatch.isTradable !== undefined) {
        isTradable = shareClassMatch.isTradable;
      }

      // Free float verisi doğrudan ticaret edildiğine dair güçlü sinyal, bu nedenle önceliklendiriyoruz.
      if (hasFreeFloatIndicator) {
        isTradable = true;
      }

      await prisma.company.update({
        where: { id: companyId },
        data: {
          freeFloatTicker: freeFloatEntry?.ticker ?? null,
          freeFloatAmountTL: freeFloatEntry?.amountTL ?? null,
          freeFloatPercent: freeFloatPercentValue,
          isTradable
        }
      });

      console.log(`   ✅ ${code} detayları kaydedildi`);

    } catch (error) {
      console.error(`   ❌ ${code} detayları kaydedilirken hata:`, error);
      throw error;
    }
  }
}

// Standalone çalıştırma
if (import.meta.url === `file://${process.argv[1]}`) {
  const browser = new BrowserManager();
  
  (async () => {
    try {
      await browser.launch(true); // headless mode ON (production)
      const scraper = new CompaniesDetailScraper(browser);
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

