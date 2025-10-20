#!/usr/bin/env python3
"""
Professional Financial Statement Scraper V2
============================================

Direct API integration with Is Yatirim financial data endpoint.
Supports all financial groups: XI_29, XI_29K, UFRS, UFRS_K.

No external dependencies except requests and standard libraries.
Built for production use with proper error handling, logging, and retry logic.

Author: KAP BIST Data Project
Version: 2.0.0
Date: October 2025
"""

from __future__ import annotations

import os
import time
import uuid
import random
import logging
from datetime import datetime
from typing import Optional, List, Tuple
from dataclasses import dataclass

import requests
import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Load environment
load_dotenv()


@dataclass
class FinancialGroup:
    """Financial group configuration"""
    code: str
    name: str
    description: str
    applicable_to: List[str]


def load_financial_group_mapping() -> dict[str, str]:
    """
    Load ticker -> financial_group mapping from database.
    
    Returns:
        Dictionary mapping ticker codes to financial group codes.
        Example: {'GARAN': 'UFRS_K', 'THYAO': 'XI_29', ...}
    """
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        logger.warning("DATABASE_URL not set, financial group mapping unavailable")
        return {}
    
    # Remove schema parameter for psycopg2 compatibility
    database_url = database_url.split('?')[0]
    
    try:
        import psycopg2
        conn = psycopg2.connect(database_url)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT ticker, "financialGroup"
            FROM company_financial_groups
            ORDER BY ticker
        """)
        
        mapping = {row[0]: row[1] for row in cursor.fetchall()}
        
        cursor.close()
        conn.close()
        
        logger.info(f"✅ Loaded financial group mapping for {len(mapping)} companies")
        return mapping
        
    except Exception as e:
        logger.warning(f"Failed to load financial group mapping: {e}")
        return {}


class IsYatirimFinancialAPI:
    """
    Professional API client for Is Yatirim financial statements.
    
    Supports all financial reporting groups with unified interface:
    - XI_29: Standard companies
    - XI_29K: Factoring, Leasing, Asset Management companies
    - UFRS: Banks & Insurance (IFRS compliant)
    - UFRS_K: Alternative IFRS reporting
    """
    
    BASE_URL = "https://www.isyatirim.com.tr/_layouts/15/IsYatirim.Website/Common/Data.aspx/MaliTablo"
    
    FINANCIAL_GROUPS = {
        "XI_29": FinancialGroup(
            code="XI_29",
            name="XI-29 Standard",
            description="Standard Turkish accounting for regular companies",
            applicable_to=["Manufacturing", "Retail", "Technology", "etc."]
        ),
        "XI_29K": FinancialGroup(
            code="XI_29K",
            name="XI-29/K Special Financial",
            description="Special accounting for financial institutions",
            applicable_to=["Factoring", "Leasing", "Asset Management"]
        ),
        "UFRS": FinancialGroup(
            code="UFRS",
            name="IFRS/UFRS",
            description="International Financial Reporting Standards",
            applicable_to=["Banks", "Insurance", "Large caps"]
        ),
        "UFRS_K": FinancialGroup(
            code="UFRS_K",
            name="IFRS/UFRS-K",
            description="Alternative IFRS reporting",
            applicable_to=["Special cases"]
        ),
        "UFRS_A": FinancialGroup(
            code="UFRS_A",
            name="UFRS: DO&CO Finansalları",
            description="DO&CO specific IFRS reporting",
            applicable_to=["DO&CO companies"]
        ),
        "UFRS_B": FinancialGroup(
            code="UFRS_B",
            name="UFRS: DO&CO K_Finansalları",
            description="DO&CO consolidated IFRS reporting",
            applicable_to=["DO&CO consolidated companies"]
        ),
    }
    
    QUARTERS = [3, 6, 9, 12]  # Q1, Q2, Q3, Q4
    MAX_RETRIES = 3
    RETRY_DELAY = 2  # seconds
    REQUEST_TIMEOUT = 15  # seconds
    RATE_LIMIT_DELAY = (0.5, 1.5)  # Random delay between requests (min, max) in seconds
    
    def __init__(self, exchange: str = "TRY", financial_group_mapping: Optional[dict[str, str]] = None):
        """
        Initialize API client.
        
        Args:
            exchange: Currency code (TRY or USD)
            financial_group_mapping: Optional ticker -> financial_group mapping from DB
        """
        self.exchange = exchange.upper()
        if self.exchange not in ("TRY", "USD"):
            raise ValueError("Exchange must be 'TRY' or 'USD'")
        
        # Store financial group mapping
        self.financial_group_mapping = financial_group_mapping or {}
        
        # Dynamically extend FINANCIAL_GROUPS with any new groups from mapping
        if financial_group_mapping:
            unique_groups = set(financial_group_mapping.values())
            for group_code in unique_groups:
                if group_code not in self.FINANCIAL_GROUPS:
                    # Add dynamically discovered group
                    self.FINANCIAL_GROUPS[group_code] = FinancialGroup(
                        code=group_code,
                        name=f"Dynamic: {group_code}",
                        description=f"Dynamically added from DB mapping",
                        applicable_to=["Various companies"]
                    )
                    logger.debug(f"Dynamically added financial group: {group_code}")
        
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
            "Accept": "*/*",
            "Accept-Language": "tr,en;q=0.9",
            "X-Requested-With": "XMLHttpRequest",
        })
    
    def get_financial_group_for_ticker(self, ticker: str) -> str:
        """
        Get the correct financial group for a ticker.
        
        Uses the database mapping if available, otherwise falls back to default logic.
        
        Args:
            ticker: Stock ticker code
            
        Returns:
            Financial group code (XI_29, XI_29K, UFRS, UFRS_K)
        """
        # First, check if we have a mapping from the database
        if ticker in self.financial_group_mapping:
            group = self.financial_group_mapping[ticker]
            logger.debug(f"Using DB mapping for {ticker}: {group}")
            return group
        
        # Fallback to default logic if no mapping exists
        logger.debug(f"No DB mapping for {ticker}, using fallback logic")
        return "XI_29"  # Default fallback
    
    def fetch_financials(
        self,
        symbol: str,
        financial_group: str,
        start_year: int,
        end_year: int
    ) -> pd.DataFrame:
        """
        Fetch financial statements for a company.
        
        Args:
            symbol: Stock ticker symbol (e.g., 'GARFA', 'GARAN')
            financial_group: Financial group code (XI_29, XI_29K, UFRS, UFRS_K, or any from DB)
            start_year: Start year (inclusive)
            end_year: End year (inclusive)
        
        Returns:
            DataFrame with financial statement data
            
        Raises:
            ValueError: If parameters are invalid
            requests.RequestException: If API call fails
        """
        # Validate financial group - accept known groups or add dynamically
        if financial_group not in self.FINANCIAL_GROUPS:
            # If it's from DB mapping but not in our list, add it dynamically
            logger.warning(
                f"Unknown financial_group '{financial_group}' for {symbol}. "
                f"Adding dynamically and attempting to use it."
            )
            self.FINANCIAL_GROUPS[financial_group] = FinancialGroup(
                code=financial_group,
                name=f"Dynamic: {financial_group}",
                description=f"Dynamically discovered during runtime",
                applicable_to=[symbol]
            )
        
        logger.info(
            f"Fetching {financial_group} data for {symbol} "
            f"({start_year}-{end_year}, {self.exchange})"
        )
        
        # Generate all quarters
        all_quarters = self._generate_quarters(start_year, end_year)
        
        # Fetch data in chunks (API accepts max 4 quarters per request)
        all_dataframes = []
        
        for chunk_start in range(0, len(all_quarters), 4):
            chunk_quarters = all_quarters[chunk_start:chunk_start + 4]
            
            try:
                df_chunk = self._fetch_chunk(symbol, financial_group, chunk_quarters)
                if df_chunk is not None and not df_chunk.empty:
                    all_dataframes.append(df_chunk)
                
                # Rate limiting
                time.sleep(0.5)
                
            except Exception as e:
                logger.warning(
                    f"Failed to fetch chunk for {symbol} "
                    f"({chunk_quarters[0] if chunk_quarters else 'unknown'}): {e}"
                )
        
        # Merge all chunks
        if not all_dataframes:
            raise ValueError(f"No financial data found for {symbol} ({financial_group})")
        
        df_final = self._merge_chunks(all_dataframes)
        
        logger.info(f"Successfully fetched {len(df_final)} items for {symbol}")
        return df_final
    
    def _generate_quarters(self, start_year: int, end_year: int) -> List[Tuple[int, int]]:
        """Generate list of (year, quarter_month) tuples"""
        quarters = []
        for year in range(start_year, end_year + 1):
            for month in self.QUARTERS:
                quarters.append((year, month))
        return quarters
    
    def _fetch_chunk(
        self,
        symbol: str,
        financial_group: str,
        quarters: List[Tuple[int, int]]
    ) -> Optional[pd.DataFrame]:
        """
        Fetch single chunk (up to 4 quarters) from API.
        
        Args:
            symbol: Stock symbol
            financial_group: Financial group code
            quarters: List of (year, quarter_month) tuples
        
        Returns:
            DataFrame with financial data or None if failed
        """
        # Build request parameters
        params = {
            "companyCode": symbol,
            "exchange": self.exchange,
            "financialGroup": financial_group,
        }
        
        # Add quarter parameters (year1-4, period1-4)
        for idx, (year, month) in enumerate(quarters, start=1):
            params[f"year{idx}"] = str(year)
            params[f"period{idx}"] = str(month)
        
        # Add cache buster
        params["_"] = str(int(time.time() * 1000))
        
        # Make request with retry logic
        for attempt in range(self.MAX_RETRIES):
            try:
                # Rate limiting: random delay between requests
                if attempt == 0:  # Only on first attempt, not on retries
                    delay = random.uniform(*self.RATE_LIMIT_DELAY)
                    time.sleep(delay)
                
                response = self.session.get(
                    self.BASE_URL,
                    params=params,
                    timeout=self.REQUEST_TIMEOUT
                )
                response.raise_for_status()
                
                # Parse JSON response
                data = response.json()
                
                if not data.get("ok"):
                    error_msg = data.get("errorDescription", "Unknown error")
                    logger.warning(f"API returned error: {error_msg}")
                    return None
                
                if not data.get("value"):
                    logger.debug(f"No data in response for {symbol}")
                    return None
                
                # Convert to DataFrame
                df = pd.DataFrame(data["value"])
                
                if df.empty:
                    return None
                
                # Rename columns to standardized format
                column_mapping = {
                    "itemCode": "itemCode",
                    "itemDescTr": "itemDescTr",
                    "itemDescEng": "itemDescEng",
                }
                
                # Add quarter columns (value1-4 → YYYY/MM format)
                for idx, (year, month) in enumerate(quarters, start=1):
                    column_mapping[f"value{idx}"] = f"{year}/{month}"
                
                # Rename only existing columns
                df = df.rename(columns={
                    k: v for k, v in column_mapping.items() if k in df.columns
                })
                
                return df
                
            except requests.exceptions.RequestException as e:
                if attempt < self.MAX_RETRIES - 1:
                    logger.warning(
                        f"Attempt {attempt + 1} failed for {symbol}, "
                        f"retrying in {self.RETRY_DELAY}s: {e}"
                    )
                    time.sleep(self.RETRY_DELAY)
                else:
                    logger.error(f"All retry attempts failed for {symbol}: {e}")
                    raise
        
        return None
    
    def _merge_chunks(self, dataframes: List[pd.DataFrame]) -> pd.DataFrame:
        """
        Merge multiple chunk DataFrames into one.
        
        Args:
            dataframes: List of DataFrames to merge
        
        Returns:
            Merged DataFrame
        """
        if len(dataframes) == 1:
            return dataframes[0]
        
        # Merge on item columns
        df_merged = dataframes[0]
        
        for df_chunk in dataframes[1:]:
            df_merged = pd.merge(
                df_merged,
                df_chunk,
                on=["itemCode", "itemDescTr", "itemDescEng"],
                how="outer"
            )
        
        # Remove completely null columns
        null_cols = df_merged.columns[df_merged.isnull().all()]
        df_merged = df_merged.drop(columns=null_cols)
        
        return df_merged


class FinancialDataProcessor:
    """Process and store financial statement data in database"""
    
    def __init__(self, database_url: str):
        """
        Initialize processor with database connection.
        
        Args:
            database_url: PostgreSQL connection string
        """
        db_url = database_url.replace("postgresql://", "postgresql+psycopg2://").split("?")[0]
        self.engine = create_engine(db_url)
        logger.info("Database connection established")
    
    def transform_to_long_format(
        self,
        df_wide: pd.DataFrame,
        company_id: int,
        symbol: str,
        financial_group: str
    ) -> pd.DataFrame:
        """
        Transform wide format data to long format for database storage.
        
        Args:
            df_wide: Wide format DataFrame from API
            company_id: Database company ID
            symbol: Stock symbol
            financial_group: Financial group code
        
        Returns:
            Long format DataFrame ready for database insertion
        """
        # Get quarter columns (format: YYYY/MM)
        quarter_cols = [
            col for col in df_wide.columns 
            if isinstance(col, str) and "/" in col
        ]
        
        if not quarter_cols:
            logger.warning(f"No quarterly data found for {symbol}")
            return pd.DataFrame()
        
        # Melt to long format
        df_long = df_wide.melt(
            id_vars=["itemCode", "itemDescTr", "itemDescEng"],
            value_vars=quarter_cols,
            var_name="period",
            value_name="value"
        )
        
        # Parse period (YYYY/MM → year, quarter)
        period_split = df_long["period"].str.split("/", expand=True)
        df_long["year"] = period_split[0].astype(int)
        month = period_split[1].astype(int)
        df_long["quarter"] = (month // 3).astype(int)
        
        # Determine statement type from item code
        df_long["statementType"] = df_long["itemCode"].apply(self._determine_statement_type)
        
        # Add metadata
        df_long["companyId"] = company_id
        df_long["financialGroup"] = financial_group
        df_long["currency"] = "TRY"
        
        # Remove null values
        df_long = df_long[df_long["value"].notna()]
        
        # Select and order columns
        df_long = df_long[[
            "companyId",
            "year",
            "quarter",
            "itemCode",
            "itemDescTr",
            "itemDescEng",
            "value",
            "statementType",
            "financialGroup",
            "currency",
        ]]
        
        # Rename columns to match database schema
        df_long = df_long.rename(columns={
            "itemDescTr": "itemNameTR",
            "itemDescEng": "itemNameEN",
        })
        
        return df_long
    
    @staticmethod
    def _determine_statement_type(item_code: str) -> str:
        """Map item code to statement type"""
        if not item_code:
            return "INCOME_STATEMENT"
        
        first_char = item_code[0]
        mapping = {
            "1": "BALANCE_SHEET_ASSETS",
            "2": "BALANCE_SHEET_LIABILITIES",
            "3": "INCOME_STATEMENT",
            "4": "CASH_FLOW",
            "A": "BALANCE_SHEET_ASSETS",  # Some codes start with A
        }
        
        return mapping.get(first_char, "INCOME_STATEMENT")
    
    def upsert_financial_data(self, df_long: pd.DataFrame) -> int:
        """
        Insert or update financial data in database.
        
        Args:
            df_long: Long format DataFrame
        
        Returns:
            Number of rows affected
        """
        if df_long.empty:
            return 0
        
        # Create temporary table with UUID for guaranteed uniqueness
        # This prevents pg_type_typname_nsp_index constraint violations
        temp_table = f"financial_statements_temp_{uuid.uuid4().hex}"
        df_long.to_sql(
            temp_table,
            self.engine,
            if_exists="replace",
            index=False,
            method="multi"
        )
        
        # Upsert query
        upsert_query = f"""
        INSERT INTO financial_statements 
            ("companyId", year, quarter, "itemCode", "itemNameTR", "itemNameEN", 
             value, "statementType", "financialGroup", currency, "createdAt", "updatedAt")
        SELECT 
            "companyId", year, quarter, "itemCode", "itemNameTR", "itemNameEN",
            value::numeric, "statementType"::"StatementType", "financialGroup", currency,
            NOW(), NOW()
        FROM {temp_table}
        ON CONFLICT ("companyId", year, quarter, "itemCode")
        DO UPDATE SET
            value = EXCLUDED.value,
            "itemNameTR" = EXCLUDED."itemNameTR",
            "itemNameEN" = EXCLUDED."itemNameEN",
            "statementType" = EXCLUDED."statementType",
            "financialGroup" = EXCLUDED."financialGroup",
            "updatedAt" = NOW();
        """
        
        drop_query = f"DROP TABLE IF EXISTS {temp_table};"
        
        with self.engine.begin() as conn:
            result = conn.exec_driver_sql(upsert_query)
            conn.exec_driver_sql(drop_query)
            rows_affected = result.rowcount if hasattr(result, 'rowcount') else len(df_long)
        
        logger.info(f"Upserted {rows_affected} financial records")
        return rows_affected


class CompanyFinancialGroupMapper:
    """Determine appropriate financial group for each company"""
    
    # XI_29K: Special financial institutions
    XI_29K_COMPANIES = {
        # Factoring
        "CRDFA", "GARFA", "LIDFA", "ULUFA",
        # Leasing
        "ISFIN", "QNBFK", "SEKFK", "VAKFN",
        # Asset Management
        "BRKVY", "GLCVY", "SMRVA",
        # Other special financial
        "DOCO", "MARMR", "ISKUR", "KTLEV",
    }
    
    # UFRS: Banks and Insurance
    BANK_CODES = {
        "AKBNK", "ALBRK", "GARAN", "HALKB", "ICBCT",
        "ISATR", "ISBTR", "ISCTR", "KLNMA", "QNBTR",
        "SKBNK", "TSKB", "VAKBN", "YKBNK",
    }
    
    UFRS_SECTORS = {"BANKACILIK", "SIGORTA", "SİGORTA"}
    
    @classmethod
    def determine_financial_group(
        cls,
        company_code: str,
        main_sector: Optional[str] = None
    ) -> str:
        """
        Determine appropriate financial group for a company.
        
        Args:
            company_code: Stock ticker symbol
            main_sector: Main sector name (optional)
        
        Returns:
            Financial group code (XI_29, XI_29K, UFRS, or UFRS_K)
        """
        company_code_upper = company_code.upper()
        
        # Check XI_29K (special financial institutions)
        if company_code_upper in cls.XI_29K_COMPANIES:
            return "XI_29K"
        
        # Check UFRS (banks and insurance)
        if company_code_upper in cls.BANK_CODES:
            return "UFRS"
        
        if main_sector:
            main_sector_upper = main_sector.upper().strip()
            if any(sector in main_sector_upper for sector in cls.UFRS_SECTORS):
                return "UFRS"
        
        # Default: XI_29 (standard companies)
        return "XI_29"


def main():
    """Main execution function - Scrape all companies"""
    logger.info("=" * 80)
    logger.info("Financial Scraper V2 - FULL PRODUCTION RUN")
    logger.info("=" * 80)
    
    DATABASE_URL = os.getenv("DATABASE_URL")
    if not DATABASE_URL:
        raise ValueError("DATABASE_URL environment variable not set")
    
    # Load financial group mapping from database
    logger.info("\n📋 Loading financial group mapping...")
    financial_group_mapping = load_financial_group_mapping()
    
    # Database connection for fetching companies
    db_url = DATABASE_URL.replace("postgresql://", "postgresql+psycopg2://").split("?")[0]
    engine = create_engine(db_url)
    
    # Fetch all companies from database
    logger.info("\n📊 Fetching companies from database...")
    query = """
        SELECT c.id, c.code, c.name, ms.name as main_sector
        FROM companies c
        LEFT JOIN main_sectors ms ON c."mainSectorId" = ms.id
        WHERE c.code IS NOT NULL
        ORDER BY c.code
    """
    
    with engine.connect() as conn:
        from sqlalchemy import text
        result = conn.execute(text(query))
        companies = [(row[0], row[1], row[2], row[3]) for row in result]
    
    total_companies = len(companies)
    logger.info(f"✓ Found {total_companies} companies to process\n")
    
    # Initialize API client and processor with mapping
    api_client = IsYatirimFinancialAPI(exchange="TRY", financial_group_mapping=financial_group_mapping)
    processor = FinancialDataProcessor(DATABASE_URL)
    
    # Statistics
    success_count = 0
    failed_companies = []
    start_time = datetime.now()
    
    # Process each company
    for idx, company_tuple in enumerate(companies, 1):
        company_id, symbol, name = company_tuple[0], company_tuple[1], company_tuple[2]
        logger.info(f"\n[{idx}/{total_companies}] Processing: {symbol} - {name}")
        
        # Determine financial group using DB mapping or fallback
        financial_group = api_client.get_financial_group_for_ticker(symbol)
        
        # Show if using DB mapping or fallback
        if symbol in financial_group_mapping:
            logger.info(f"  Financial Group: {financial_group} (from DB mapping)")
        else:
            logger.info(f"  Financial Group: {financial_group} (fallback)")
        
        try:
            # Fetch from API
            df_wide = api_client.fetch_financials(
                symbol=symbol,
                financial_group=financial_group,
                start_year=2020,
                end_year=datetime.now().year
            )
            
            # Transform to long format
            df_long = processor.transform_to_long_format(
                df_wide=df_wide,
                company_id=company_id,
                symbol=symbol,
                financial_group=financial_group
            )
            
            # Save to database
            rows = processor.upsert_financial_data(df_long)
            logger.info(f"  ✓ Success: {rows} records saved")
            success_count += 1
            
        except Exception as e:
            logger.error(f"  ✗ Failed: {e}")
            failed_companies.append((symbol, str(e)))
    
    # Final statistics
    end_time = datetime.now()
    duration = (end_time - start_time).total_seconds()
    
    logger.info("\n" + "=" * 80)
    logger.info("SCRAPING COMPLETED")
    logger.info("=" * 80)
    logger.info(f"Total Companies: {total_companies}")
    logger.info(f"Successful: {success_count} ({success_count/total_companies*100:.1f}%)")
    logger.info(f"Failed: {len(failed_companies)}")
    logger.info(f"Duration: {duration/60:.1f} minutes")
    
    if failed_companies:
        logger.warning("\nFailed Companies:")
        for symbol, error in failed_companies:
            logger.warning(f"  - {symbol}: {error}")
    
    logger.info("\n" + "=" * 80)
    
    logger.info("\n" + "=" * 80)
    logger.info("Scraping completed")
    logger.info("=" * 80)


if __name__ == "__main__":
    main()
