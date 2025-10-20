import path from 'node:path';
import { tmpdir } from 'node:os';
import { promises as fs } from 'node:fs';
import { randomBytes } from 'node:crypto';
import ExcelJS, { type Cell, type Row } from 'exceljs';
import type { BrowserManager } from './browser.js';
import { cleanText } from './helpers.js';

const ISYATIRIM_URL = 'https://www.isyatirim.com.tr/tr-tr/analiz/hisse/Sayfalar/Temel-Degerler-Ve-Oranlar.aspx#page-1';
const EXCEL_SELECTOR = '#tab1 > div.tab-content > div:nth-child(1) > div.box > div > a';
const CACHE_DIR = path.join(process.cwd(), '.cache');
const SNAPSHOT_FILE = path.join(CACHE_DIR, 'isyatirim-universe.json');

export interface IsyatirimUniverseEntry {
  code: string;
  name: string | null;
  sector: string | null;
  freeFloatPercent: number | null;
  paidInCapitalMn: number | null;
}

export interface IsyatirimUniverseSnapshot {
  entries: IsyatirimUniverseEntry[];
  codeSet: Set<string>;
  fetchedAt: Date;
}

async function persistIsyatirimSnapshot(snapshot: IsyatirimUniverseSnapshot): Promise<void> {
  const payload = {
    fetchedAt: snapshot.fetchedAt.toISOString(),
    entries: snapshot.entries
  };

  await fs.mkdir(CACHE_DIR, { recursive: true });
  await fs.writeFile(SNAPSHOT_FILE, JSON.stringify(payload, null, 2), 'utf-8');
}

function getCellText(row: Row, column: number | undefined): string | null {
  if (!column) {
    return null;
  }

  const cell = row.getCell(column);
  const rawText = typeof cell.text === 'string' && cell.text.length > 0
    ? cell.text
    : typeof cell.value === 'string'
      ? cell.value
      : null;

  return cleanText(rawText);
}

function getCellNumber(row: Row, column: number | undefined): number | null {
  if (!column) {
    return null;
  }

  const cell = row.getCell(column);
  if (typeof cell.value === 'number') {
    return Number.isFinite(cell.value) ? cell.value : null;
  }

  const rawText = cell.text ?? (typeof cell.value === 'string' ? cell.value : null);
  const cleaned = cleanText(rawText);
  if (!cleaned) {
    return null;
  }

  const normalized = cleaned.replace(/\./g, '').replace(',', '.');
  const numeric = Number.parseFloat(normalized);
  return Number.isFinite(numeric) ? numeric : null;
}

export async function fetchIsyatirimUniverse(browser: BrowserManager): Promise<IsyatirimUniverseSnapshot> {
  const page = await browser.newPage();
  const tempFile = path.join(tmpdir(), `temelozet-${Date.now()}-${randomBytes(6).toString('hex')}.xlsx`);

  try {
    await page.goto(ISYATIRIM_URL, { waitUntil: 'domcontentloaded', timeout: 30000 });
    await page.waitForSelector(EXCEL_SELECTOR, { timeout: 20000 });

    const [download] = await Promise.all([
      page.waitForEvent('download', { timeout: 20000 }),
      page.click(EXCEL_SELECTOR, { timeout: 20000 })
    ]);

    await download.saveAs(tempFile);

    const workbook = new ExcelJS.Workbook();
    await workbook.xlsx.readFile(tempFile);

    const worksheet = workbook.worksheets[0];
    if (!worksheet) {
      throw new Error('İş Yatırım Excel dosyasında sayfa bulunamadı');
    }

    const headerIndex = new Map<string, number>();
  worksheet.getRow(1).eachCell({ includeEmpty: true }, (cell: Cell, colNumber: number) => {
      const headerText = cleanText(cell.text ?? (typeof cell.value === 'string' ? cell.value : null));
      if (headerText) {
        headerIndex.set(headerText, colNumber);
      }
    });

    const codeColumn = headerIndex.get('Kod');
    const nameColumn = headerIndex.get('Hisse Adı');
    const sectorColumn = headerIndex.get('Sektör');
    const freeFloatColumn = headerIndex.get('Halka AçıklıkOranı (%)');
    const capitalColumn = headerIndex.get('Sermaye(mn TL)');

    if (!codeColumn) {
      throw new Error('İş Yatırım Excel tablosunda "Kod" sütunu bulunamadı');
    }

    const entries: IsyatirimUniverseEntry[] = [];
    const codeSet = new Set<string>();

  worksheet.eachRow({ includeEmpty: false }, (row: Row, rowNumber: number) => {
      if (rowNumber === 1) {
        return;
      }

      const code = getCellText(row, codeColumn)?.toUpperCase();
      if (!code) {
        return;
      }

      const entry: IsyatirimUniverseEntry = {
        code,
        name: getCellText(row, nameColumn),
        sector: getCellText(row, sectorColumn),
        freeFloatPercent: getCellNumber(row, freeFloatColumn),
        paidInCapitalMn: getCellNumber(row, capitalColumn)
      };

      entries.push(entry);
      codeSet.add(code);
    });

    if (!entries.length) {
      throw new Error('İş Yatırım Excel tablosu boş döndü');
    }

    const snapshot: IsyatirimUniverseSnapshot = {
      entries,
      codeSet,
      fetchedAt: new Date()
    };

    try {
      await persistIsyatirimSnapshot(snapshot);
    } catch (error) {
      console.warn('⚠️  İş Yatırım fihristi önbelleğe yazılamadı:', error);
    }

    return snapshot;
  } finally {
    await page.close().catch(() => undefined);
    await fs.unlink(tempFile).catch(() => undefined);
  }
}
