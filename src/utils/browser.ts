import { chromium, Browser, Page, BrowserContext } from 'playwright';

export class BrowserManager {
  private browser: Browser | null = null;
  private context: BrowserContext | null = null;

  async launch(headless: boolean = true): Promise<void> {
    console.log('🌐 Tarayıcı başlatılıyor...');
    this.browser = await chromium.launch({
      headless,
      args: [
        '--no-sandbox',
        '--disable-setuid-sandbox',
        '--disable-dev-shm-usage',
        '--disable-blink-features=AutomationControlled'
      ]
    });

    this.context = await this.browser.newContext({
      userAgent: 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
      locale: 'tr-TR',
      timezoneId: 'Europe/Istanbul',
      viewport: { width: 1920, height: 1080 }
    });

    console.log('✅ Tarayıcı hazır');
  }

  async newPage(): Promise<Page> {
    if (!this.context) {
      throw new Error('Browser context not initialized. Call launch() first.');
    }
    return await this.context.newPage();
  }

  async close(): Promise<void> {
    if (this.context) {
      await this.context.close();
    }
    if (this.browser) {
      await this.browser.close();
      console.log('🔒 Tarayıcı kapatıldı');
    }
  }

  getContext(): BrowserContext {
    if (!this.context) {
      throw new Error('Browser context not initialized. Call launch() first.');
    }
    return this.context;
  }
}

