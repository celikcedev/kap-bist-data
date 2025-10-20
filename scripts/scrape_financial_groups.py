"""
Financial Group Scraper - Scrape correct financial group for each company from IsYatirim website.

This scraper extracts the financial group selection from the company card page,
which tells us exactly which format (XI_29, UFRS, UFRS_K, etc.) each company uses.

Updated: Uses BeautifulSoup for speed, fetches all tradable tickers from DB,
and upserts to company_financial_groups table.
"""

import os
import sys
import time
import logging
from typing import Optional, Dict, List
from datetime import datetime
import psycopg2
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class FinancialGroupScraper:
    """
    Scraper to extract financial group information from IsYatirim website.
    """
    
    BASE_URL = "https://www.isyatirim.com.tr/tr-tr/analiz/hisse/Sayfalar/sirket-karti.aspx"
    
    def __init__(self, database_url: str):
        """Initialize with database connection."""
        # psycopg2 doesn't support 'schema' query parameter - remove it
        self.database_url = database_url.split('?')[0]
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
        })
    
    def get_tradable_tickers(self) -> List[str]:
        """
        Fetch all tickers from database.
        BUG FIX: Changed to fetch ALL companies (not just tradable ones).
        
        Returns:
            List of ticker codes
        """
        conn = psycopg2.connect(self.database_url)
        cursor = conn.cursor()
        
        # BUG FIX: Get ALL companies (removed isTradable filter)
        cursor.execute("""
            SELECT DISTINCT COALESCE(companies."freeFloatTicker", companies.code) as ticker
            FROM companies
            ORDER BY ticker
        """)
        
        tickers = [row[0] for row in cursor.fetchall()]
        cursor.close()
        conn.close()
        
        logger.info(f"Fetched {len(tickers)} tickers from database (all companies)")
        return tickers
    
    def scrape_financial_group(self, ticker: str) -> Optional[Dict[str, str]]:
        """
        Scrape financial group for a single company.
        
        Args:
            ticker: Company ticker symbol
            
        Returns:
            Dict with 'value' and 'display' keys, or None if failed
        """
        url = f"{self.BASE_URL}?hisse={ticker}"
        
        try:
            response = self.session.get(url, timeout=15)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Find select element
            select = soup.find('select', id='ddlMaliTabloGroup')
            if not select:
                # Try alternative selector
                select = soup.find('select', attrs={'name': lambda x: x and 'ddlMaliTabloGroup' in x})
            
            if not select:
                logger.warning(f"{ticker}: ddlMaliTabloGroup select not found")
                return None
            
            # Find selected option
            selected_option = select.find('option', selected=True)
            if not selected_option:
                # If no selected, take first option
                selected_option = select.find('option')
            
            if not selected_option:
                logger.warning(f"{ticker}: No options found in select")
                return None
            
            value = selected_option.get('value')
            display = selected_option.get_text(strip=True)
            
            if not value:
                logger.warning(f"{ticker}: Option has no value attribute")
                return None
            
            logger.info(f"✅ {ticker}: {display} -> {value}")
            return {'value': value, 'display': display}
        
        except Exception as e:
            logger.error(f"❌ {ticker}: {str(e)}")
            return None
    
    def upsert_financial_group(self, ticker: str, financial_group: str, display_name: str):
        """
        Upsert financial group to database.
        
        Args:
            ticker: Company ticker
            financial_group: API value (e.g., 'UFRS_K')
            display_name: Display text (e.g., 'Konsolide UFRS')
        """
        conn = psycopg2.connect(self.database_url)
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO company_financial_groups (ticker, "financialGroup", "displayName", "createdAt", "updatedAt")
            VALUES (%s, %s, %s, NOW(), NOW())
            ON CONFLICT (ticker)
            DO UPDATE SET
                "financialGroup" = EXCLUDED."financialGroup",
                "displayName" = EXCLUDED."displayName",
                "updatedAt" = NOW()
        """, (ticker, financial_group, display_name))
        
        conn.commit()
        cursor.close()
        conn.close()
    
    def scrape_all_companies(self, tickers: List[str]) -> Dict[str, Optional[Dict]]:
        """
        Scrape financial groups for all companies and upsert to DB.
        
        Args:
            tickers: List of company ticker symbols
            
        Returns:
            Dictionary mapping ticker to financial group info
        """
        results = {}
        total = len(tickers)
        success_count = 0
        failed_count = 0
        
        logger.info("=" * 80)
        logger.info("Starting financial group scraping...")
        logger.info(f"Total companies: {total}")
        logger.info("=" * 80)
        
        for i, ticker in enumerate(tickers, 1):
            logger.info(f"[{i}/{total}] Processing {ticker}...")
            
            financial_group_info = self.scrape_financial_group(ticker)
            results[ticker] = financial_group_info
            
            if financial_group_info:
                # Upsert to database
                try:
                    self.upsert_financial_group(
                        ticker,
                        financial_group_info['value'],
                        financial_group_info['display']
                    )
                    success_count += 1
                except Exception as e:
                    logger.error(f"Failed to upsert {ticker}: {e}")
                    failed_count += 1
            else:
                failed_count += 1
            
            # Polite scraping: small delay
            time.sleep(0.5)
        
        logger.info("=" * 80)
        logger.info(f"Scraping completed!")
        logger.info(f"Success: {success_count}/{total}")
        logger.info(f"Failed: {failed_count}/{total}")
        logger.info("=" * 80)
        
        return results

def main():
    """Main function to scrape financial groups for all tradable companies."""
    
    # Get DATABASE_URL from environment
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        logger.error("DATABASE_URL environment variable not set")
        sys.exit(1)
    
    scraper = FinancialGroupScraper(database_url)
    
    # Get all tradable tickers from DB
    tickers = scraper.get_tradable_tickers()
    
    if not tickers:
        logger.error("No tradable tickers found in database")
        sys.exit(1)
    
    # Scrape all companies
    results = scraper.scrape_all_companies(tickers)
    
    # Print summary by financial group
    print("\n" + "=" * 80)
    print("📊 FINANCIAL GROUP DISTRIBUTION")
    print("=" * 80)
    print()
    
    grouped = {}
    for ticker, info in results.items():
        if info and info['value']:
            group = info['value']
            if group not in grouped:
                grouped[group] = []
            grouped[group].append(ticker)
    
    for group in sorted(grouped.keys()):
        tickers_list = grouped[group]
        print(f"{group}: {len(tickers_list)} companies")
        # Print first 10 examples
        examples = ', '.join(tickers_list[:10])
        if len(tickers_list) > 10:
            examples += f", ... (+{len(tickers_list) - 10} more)"
        print(f"  Examples: {examples}")
        print()
    
    print("=" * 80)
    print("✅ Scraping completed and data saved to company_financial_groups table")
    print("=" * 80)

if __name__ == "__main__":
    main()

import asyncio
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeout
import logging
from typing import Optional, Dict
import json
from datetime import datetime

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class AsyncFinancialGroupScraper:
    """
    Async scraper to extract financial group information from IsYatirim website.
    Uses Playwright for browser automation.
    """
    
    BASE_URL = "https://www.isyatirim.com.tr/tr-tr/analiz/hisse/Sayfalar/sirket-karti.aspx"
    
    # Selectors (verified working!)
    SELECTOR_MALI_TABLOLAR_TAB = "#page-4"  # Mali Tablolar tab
    SELECTOR_FINANCIAL_GROUP_SELECT = "#ddlMaliTabloGroup"  # Actual select element (hidden by select2)
    
    # Financial group display text to API value mapping
    DISPLAY_TO_VALUE_MAP = {
        "Konsolide Olmayan UFRS": "UFRS",
        "Konsolide UFRS": "UFRS_K",
        "TMS": "XI_29",
        "TMS/TFRS": "XI_29",
        "XI_29": "XI_29",
        "Faktoring": "XI_29K",
        "Leasing": "XI_29K",
    }
    
    async def scrape_financial_group(self, ticker: str, page) -> Optional[str]:
        """
        Scrape financial group for a single company.
        
        Args:
            ticker: Company ticker symbol
            page: Playwright page object
            
        Returns:
            Financial group string (e.g., 'UFRS', 'XI_29', 'UFRS_K') or None if failed
        """
        url = f"{self.BASE_URL}?hisse={ticker}"
        
        try:
            logger.info(f"Scraping financial group for {ticker}")
            
            # Navigate to company page
            await page.goto(url, wait_until="domcontentloaded", timeout=30000)
            await asyncio.sleep(2)  # Wait for page to fully load
            
            # Click Mali Tablolar tab
            try:
                mali_tablolar_tab = await page.wait_for_selector(
                    self.SELECTOR_MALI_TABLOLAR_TAB,
                    timeout=15000,
                    state="visible"
                )
                await mali_tablolar_tab.click()
                await asyncio.sleep(2)  # Wait for tab content to load
                
            except PlaywrightTimeout:
                logger.warning(f"{ticker}: Mali Tablolar tab not found")
                return None
            except Exception as e:
                logger.warning(f"{ticker}: Error clicking Mali Tablolar - {str(e)}")
                return None
            
            # Get selected financial group VALUE from dropdown
            # We need the VALUE attribute (UFRS_K), not the display text (Konsolide UFRS)
            try:
                # Get the actual select element (not the select2 display)
                select_element = await page.wait_for_selector(
                    self.SELECTOR_FINANCIAL_GROUP_SELECT,
                    timeout=15000,
                    state="attached"  # Don't need visible, it's hidden by select2
                )
                
                # Get the selected option's value attribute
                financial_group = await select_element.evaluate("""
                    (select) => {
                        const selectedOption = select.options[select.selectedIndex];
                        return selectedOption ? selectedOption.value : null;
                    }
                """)
                
                if financial_group:
                    logger.info(f"✅ {ticker}: {financial_group}")
                    return financial_group
                else:
                    logger.warning(f"{ticker}: No option selected in dropdown")
                    return None
                
            except PlaywrightTimeout:
                logger.warning(f"{ticker}: Financial group dropdown not found")
                return None
            except Exception as e:
                logger.warning(f"{ticker}: Error getting financial group - {str(e)}")
                return None
        
        except Exception as e:
            logger.error(f"❌ {ticker}: Error - {str(e)}")
            return None
    
    def upsert_financial_group(self, ticker: str, financial_group: str, display_name: str):
        """
        Upsert financial group to database.
        
        Args:
            ticker: Company ticker symbol
            financial_group: Financial group value (e.g., 'XI_29', 'UFRS_K')
            display_name: Display name (e.g., 'Seri XI No:29 Konsolide Olmayan')
        """
        conn = psycopg2.connect(
            host=os.getenv('DB_HOST'),
            database=os.getenv('DB_NAME'),
            user=os.getenv('DB_USER'),
            password=os.getenv('DB_PASS'),
            port=os.getenv('DB_PORT', '5432')
        )
        
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO company_financial_groups (ticker, "financialGroup", "displayName", "createdAt", "updatedAt")
            VALUES (%s, %s, %s, NOW(), NOW())
            ON CONFLICT (ticker)
            DO UPDATE SET
                "financialGroup" = EXCLUDED."financialGroup",
                "displayName" = EXCLUDED."displayName",
                "updatedAt" = NOW()
        """, (ticker, financial_group, display_name))
        
        conn.commit()
        cursor.close()
        conn.close()
    
    async def scrape_all_companies(self, tickers: list[str]) -> Dict[str, Optional[str]]:
        """
        Scrape financial groups for all companies AND save to database.
        
        Args:
            tickers: List of company ticker symbols
            
        Returns:
            Dictionary mapping ticker to financial group
        """
        results = {}
        
        async with async_playwright() as p:
            logger.info("Launching browser...")
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                viewport={"width": 1920, "height": 1080},
                user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
            )
            page = await context.new_page()
            
            total = len(tickers)
            success_count = 0
            
            for i, ticker in enumerate(tickers, 1):
                logger.info(f"[{i}/{total}] Processing {ticker}...")
                
                financial_group = await self.scrape_financial_group(ticker, page)
                results[ticker] = financial_group
                
                if financial_group:
                    success_count += 1
                    # BUG FIX: Save to database immediately with correct parameters
                    try:
                        self.upsert_financial_group(
                            ticker,
                            financial_group['value'],
                            financial_group['display']
                        )
                    except Exception as e:
                        logger.error(f"Failed to upsert {ticker}: {e}")
                
                # Small delay between requests (polite scraping)
                await asyncio.sleep(1)
            
            await browser.close()
            
            logger.info("=" * 80)
            logger.info(f"Scraping completed: {success_count}/{total} successful")
            logger.info("=" * 80)
        
        return results

async def main_async():
    """Async main function for testing financial group scraping with Playwright."""
    
    # Test with failed companies first
    failed_companies = [
        'AGESA', 'AKGRT', 'ANHYT', 'ANSGR', 'BRKVY',
        'DOCO', 'DSTKF', 'GLCVY', 'ISKUR', 'MARMR',
        'RAYSG', 'SMRVA', 'TURSG'
    ]
    
    # Also test with some successful companies to verify
    test_companies = ['GARAN', 'THYAO', 'AKBNK'] + failed_companies
    
    scraper = AsyncFinancialGroupScraper()
    results = await scraper.scrape_all_companies(test_companies)
    
    # Print results
    print("\n" + "=" * 80)
    print("📊 FINANCIAL GROUP MAPPING")
    print("=" * 80)
    print()
    
    # Group by financial group
    grouped = {}
    for ticker, group in results.items():
        if group:
            if group not in grouped:
                grouped[group] = []
            grouped[group].append(ticker)
    
    for group, tickers in grouped.items():
        print(f"{group}:")
        print(f"  Companies ({len(tickers)}): {', '.join(tickers)}")
        print()
    
    # Save to JSON
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = f"financial_groups_{timestamp}.json"
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    
    print("=" * 80)
    print(f"✅ Results saved to: {output_file}")
    print("=" * 80)
    
    # Show failed companies with their correct groups
    print("\n" + "=" * 80)
    print("🎯 FAILED COMPANIES - CORRECT FINANCIAL GROUPS")
    print("=" * 80)
    print()
    
    for ticker in failed_companies:
        group = results.get(ticker, 'Not Found')
        print(f"{ticker}: {group}")
    
    print()
    print("=" * 80)
    print("💡 NEXT STEP: Update financial_scraper_v2.py with these mappings!")
    print("=" * 80)

if __name__ == "__main__":
    # Check if async mode is requested via environment variable
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "--async":
        asyncio.run(main_async())
    else:
        # Use sync version by default (main() function defined earlier)
        main()
