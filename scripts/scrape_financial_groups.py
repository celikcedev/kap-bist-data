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
