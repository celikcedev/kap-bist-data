#!/usr/bin/env python3
"""
Test Subset Financial Scraper - Only 10 companies for testing
"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

# Import original scraper
from financial_scraper_v2 import (
    IsYatirimFinancialAPI,
    FinancialDataProcessor,
    load_financial_group_mapping
)

import logging
from datetime import datetime
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Test subset - 10 companies
TEST_COMPANIES = [
    'GARAN', 'THYAO', 'AKGRT', 'AGESA', 'BRKVY',
    'DOCO', 'ISCTR', 'TUPRS', 'EREGL', 'SAHOL'
]

def main():
    logger.info("=" * 80)
    logger.info("Financial Scraper V2 - TEST SUBSET (10 companies)")
    logger.info("=" * 80)
    
    DATABASE_URL = os.getenv("DATABASE_URL")
    if not DATABASE_URL:
        raise ValueError("DATABASE_URL not set")
    
    # Load financial group mapping
    financial_group_mapping = load_financial_group_mapping()
    
    # Get test companies from DB
    db_url = DATABASE_URL.replace("postgresql://", "postgresql+psycopg2://").split("?")[0]
    engine = create_engine(db_url)
    
    query = """
        SELECT c.id, c.code, c.name
        FROM companies c
        WHERE c.code = ANY(:test_codes)
        ORDER BY c.code
    """
    
    with engine.connect() as conn:
        result = conn.execute(text(query), {"test_codes": TEST_COMPANIES})
        companies = [(row[0], row[1], row[2]) for row in result]
    
    if not companies:
        logger.error("No test companies found in database!")
        return
    
    logger.info(f"Found {len(companies)} test companies\n")
    
    # Initialize API and processor
    api_client = IsYatirimFinancialAPI(exchange="TRY", financial_group_mapping=financial_group_mapping)
    processor = FinancialDataProcessor(DATABASE_URL)
    
    success_count = 0
    failed_companies = []
    start_time = datetime.now()
    
    for idx, (company_id, symbol, name) in enumerate(companies, 1):
        logger.info(f"[{idx}/{len(companies)}] Processing: {symbol} - {name}")
        
        financial_group = api_client.get_financial_group_for_ticker(symbol)
        logger.info(f"  Financial Group: {financial_group}")
        
        try:
            df_wide = api_client.fetch_financials(
                symbol=symbol,
                financial_group=financial_group,
                start_year=2020,
                end_year=datetime.now().year
            )
            
            df_long = processor.transform_to_long_format(
                df_wide=df_wide,
                company_id=company_id,
                symbol=symbol,
                financial_group=financial_group
            )
            
            rows = processor.upsert_financial_data(df_long)
            logger.info(f"  ✓ Success: {rows} records saved")
            success_count += 1
            
        except Exception as e:
            logger.error(f"  ✗ Failed: {e}")
            failed_companies.append((symbol, str(e)))
    
    duration = (datetime.now() - start_time).total_seconds()
    
    logger.info("\n" + "=" * 80)
    logger.info("TEST SCRAPING COMPLETED")
    logger.info(f"Successful: {success_count}/{len(companies)}")
    logger.info(f"Failed: {len(failed_companies)}")
    logger.info(f"Duration: {duration/60:.1f} minutes")
    
    if failed_companies:
        logger.warning("\nFailed Companies:")
        for symbol, error in failed_companies:
            logger.warning(f"  - {symbol}: {error}")

if __name__ == "__main__":
    main()
