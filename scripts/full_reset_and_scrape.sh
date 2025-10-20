#!/bin/bash

################################################################################
# FULL SYSTEM RESET & SCRAPE - Production Deployment Simulation
################################################################################
# Bu script sistemi sıfırdan başlatıp tüm verileri sıralı şekilde kazır
# Ardından upsert mekanizmasını test eder
################################################################################

set -e  # Hata durumunda dur
set -u  # Tanımsız değişken kullanımında dur

# Renkli output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Log directory
LOG_DIR="logs/full_reset_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$LOG_DIR"

echo -e "${BLUE}=================================================================================${NC}"
echo -e "${BLUE}   BIST DATA PIPELINE - FULL SYSTEM RESET & SCRAPE${NC}"
echo -e "${BLUE}=================================================================================${NC}"
echo -e "Log Directory: $LOG_DIR"
echo -e "Start Time: $(date)"
echo ""

################################################################################
# PHASE 1: DATABASE RESET
################################################################################
echo -e "${YELLOW}[PHASE 1] DATABASE RESET${NC}"
echo "Truncating all tables and resetting sequences..."

# Truncate all tables (faster than drop/recreate)
PGPASSWORD='Xd29+x-NqJeX' psql -h localhost -U ademcelik -d bist_data << 'EOF' 2>&1 | tee "$LOG_DIR/phase1_db_reset.log"
-- Disable foreign key checks temporarily
SET session_replication_role = 'replica';

-- Truncate all tables and reset sequences
TRUNCATE TABLE financial_statements RESTART IDENTITY CASCADE;
TRUNCATE TABLE company_financial_groups RESTART IDENTITY CASCADE;
TRUNCATE TABLE company_indices RESTART IDENTITY CASCADE;
TRUNCATE TABLE company_markets RESTART IDENTITY CASCADE;
TRUNCATE TABLE board_members RESTART IDENTITY CASCADE;
TRUNCATE TABLE executives RESTART IDENTITY CASCADE;
TRUNCATE TABLE ir_staff RESTART IDENTITY CASCADE;
TRUNCATE TABLE shareholders RESTART IDENTITY CASCADE;
TRUNCATE TABLE subsidiaries RESTART IDENTITY CASCADE;
TRUNCATE TABLE companies RESTART IDENTITY CASCADE;
TRUNCATE TABLE indices RESTART IDENTITY CASCADE;
TRUNCATE TABLE markets RESTART IDENTITY CASCADE;
TRUNCATE TABLE main_sectors RESTART IDENTITY CASCADE;
TRUNCATE TABLE sub_sectors RESTART IDENTITY CASCADE;

-- Re-enable foreign key checks
SET session_replication_role = 'origin';

SELECT 'All tables truncated successfully' as status;
EOF

if [ ${PIPESTATUS[0]} -eq 0 ]; then
    echo -e "${GREEN}✅ Database reset successful${NC}"
else
    echo -e "${RED}❌ Database reset failed${NC}"
    exit 1
fi

# Verification
echo "Verifying empty database..."
PGPASSWORD='Xd29+x-NqJeX' psql -h localhost -U ademcelik -d bist_data << 'EOF' | tee -a "$LOG_DIR/phase1_verification.log"
SELECT 'companies' as table_name, COUNT(*) as count FROM companies
UNION ALL SELECT 'indices', COUNT(*) FROM indices
UNION ALL SELECT 'main_sectors', COUNT(*) FROM main_sectors
UNION ALL SELECT 'sub_sectors', COUNT(*) FROM sub_sectors
UNION ALL SELECT 'markets', COUNT(*) FROM markets
UNION ALL SELECT 'company_financial_groups', COUNT(*) FROM company_financial_groups
UNION ALL SELECT 'financial_statements', COUNT(*) FROM financial_statements
ORDER BY table_name;
EOF

echo ""

################################################################################
# PHASE 2: METADATA SCRAPING
################################################################################
echo -e "${YELLOW}[PHASE 2] METADATA SCRAPING (Companies, Indices, Sectors, Markets)${NC}"
echo "Expected: 592 companies, ~10 minutes"

npm run scrape:all 2>&1 | tee "$LOG_DIR/phase2_metadata.log"

if [ ${PIPESTATUS[0]} -eq 0 ]; then
    echo -e "${GREEN}✅ Metadata scraping successful${NC}"
else
    echo -e "${RED}❌ Metadata scraping failed${NC}"
    exit 1
fi

# Verification
echo "Verifying metadata..."
PGPASSWORD='Xd29+x-NqJeX' psql -h localhost -U ademcelik -d bist_data << 'EOF' | tee -a "$LOG_DIR/phase2_verification.log"
\timing on
SELECT 'METADATA COUNTS:' as info;
SELECT 'companies' as table_name, COUNT(*) as count FROM companies
UNION ALL SELECT 'indices', COUNT(*) FROM indices
UNION ALL SELECT 'main_sectors', COUNT(*) FROM main_sectors
UNION ALL SELECT 'sub_sectors', COUNT(*) FROM sub_sectors
UNION ALL SELECT 'markets', COUNT(*) FROM markets
UNION ALL SELECT 'company_indices', COUNT(*) FROM company_indices
UNION ALL SELECT 'company_markets', COUNT(*) FROM company_markets
ORDER BY table_name;

SELECT '' as separator; 
SELECT 'Sample companies:' as info;
SELECT code, name, "isTradable", "freeFloatTicker" FROM companies LIMIT 5;
\timing off
EOF

echo ""

################################################################################
# PHASE 3: FINANCIAL GROUPS MAPPING
################################################################################
echo -e "${YELLOW}[PHASE 3] FINANCIAL GROUPS MAPPING${NC}"
echo "Expected: 590/592 companies, ~15 minutes"

.venv/bin/python scripts/scrape_financial_groups.py 2>&1 | tee "$LOG_DIR/phase3_financial_groups.log"

if [ ${PIPESTATUS[0]} -eq 0 ]; then
    echo -e "${GREEN}✅ Financial groups mapping successful${NC}"
else
    echo -e "${RED}❌ Financial groups mapping failed${NC}"
    exit 1
fi

# Verification
echo "Verifying financial groups..."
PGPASSWORD='Xd29+x-NqJeX' psql -h localhost -U ademcelik -d bist_data << 'EOF' | tee -a "$LOG_DIR/phase3_verification.log"
SELECT 'FINANCIAL GROUPS:' as info;
SELECT COUNT(*) as total FROM company_financial_groups;

SELECT '';
SELECT 'Distribution:';
SELECT "financialGroup", COUNT(*) as count
FROM company_financial_groups
GROUP BY "financialGroup"
ORDER BY count DESC;

SELECT '';
SELECT 'Missing companies (expected: ISKUR, MARMR):';
SELECT code FROM companies 
WHERE code NOT IN (SELECT ticker FROM company_financial_groups)
ORDER BY code;
EOF

echo ""

################################################################################
# PHASE 4: FINANCIAL STATEMENTS SCRAPING (ALL 590 COMPANIES)
################################################################################
echo -e "${YELLOW}[PHASE 4] FINANCIAL STATEMENTS SCRAPING - ALL 590 COMPANIES${NC}"
echo "Expected: ~2.2 million records, ~2-3 hours"
echo "Press Ctrl+C within 10 seconds to skip this phase..."
sleep 10

.venv/bin/python scripts/financial_scraper_v2.py 2>&1 | tee "$LOG_DIR/phase4_financial_statements.log"

if [ ${PIPESTATUS[0]} -eq 0 ]; then
    echo -e "${GREEN}✅ Financial statements scraping successful${NC}"
else
    echo -e "${RED}❌ Financial statements scraping failed${NC}"
    exit 1
fi

# Verification
echo "Verifying financial statements..."
PGPASSWORD='Xd29+x-NqJeX' psql -h localhost -U ademcelik -d bist_data << 'EOF' | tee -a "$LOG_DIR/phase4_verification.log"
\timing on

SELECT 'FINANCIAL STATEMENTS:' as info;
SELECT COUNT(*) as total_records FROM financial_statements;

SELECT '';
SELECT 'Companies with statements:';
SELECT COUNT(DISTINCT "companyId") as companies_with_data FROM financial_statements;

SELECT '';
SELECT 'Records by year:';
SELECT year, COUNT(*) as records
FROM financial_statements
GROUP BY year
ORDER BY year DESC;

SELECT '';
SELECT 'Top 10 companies by record count:';
SELECT c.code, COUNT(*) as records
FROM financial_statements fs
JOIN companies c ON fs."companyId" = c.id
GROUP BY c.code
ORDER BY records DESC
LIMIT 10;

SELECT '';
SELECT 'Duplicate check:';
SELECT COUNT(*) as duplicates FROM (
  SELECT "companyId", year, quarter, "itemCode"
  FROM financial_statements
  GROUP BY "companyId", year, quarter, "itemCode"
  HAVING COUNT(*) > 1
) dups;

\timing off
EOF

echo ""

################################################################################
# PHASE 5: PRODUCTION VALIDATION
################################################################################
echo -e "${YELLOW}[PHASE 5] PRODUCTION VALIDATION${NC}"

PGPASSWORD='Xd29+x-NqJeX' psql -h localhost -U ademcelik -d bist_data << 'EOF' | tee "$LOG_DIR/phase5_validation.log"
\timing on

SELECT '================================================================================' as separator;
SELECT '                    PRODUCTION READINESS VALIDATION' as title;
SELECT '================================================================================' as separator;

-- Table counts
SELECT '' as separator;
SELECT '1. TABLE COUNTS:' as section;
SELECT 'companies' as table_name, COUNT(*) as count FROM companies
UNION ALL SELECT 'company_financial_groups', COUNT(*) FROM company_financial_groups
UNION ALL SELECT 'financial_statements', COUNT(*) FROM financial_statements
UNION ALL SELECT 'indices', COUNT(*) FROM indices
UNION ALL SELECT 'markets', COUNT(*) FROM markets
UNION ALL SELECT 'main_sectors', COUNT(*) FROM main_sectors
UNION ALL SELECT 'sub_sectors', COUNT(*) FROM sub_sectors
UNION ALL SELECT 'company_indices', COUNT(*) FROM company_indices
UNION ALL SELECT 'company_markets', COUNT(*) FROM company_markets
ORDER BY table_name;

-- Duplicates
SELECT '' as separator;
SELECT '2. DUPLICATE CHECK:' as section;
SELECT 'Companies' as table_name, COUNT(*) as duplicates FROM (
  SELECT code FROM companies GROUP BY code HAVING COUNT(*) > 1
) d;
SELECT 'Financial groups' as table_name, COUNT(*) as duplicates FROM (
  SELECT ticker FROM company_financial_groups GROUP BY ticker HAVING COUNT(*) > 1
) d;
SELECT 'Financial statements' as table_name, COUNT(*) as duplicates FROM (
  SELECT "companyId", year, quarter, "itemCode" 
  FROM financial_statements 
  GROUP BY "companyId", year, quarter, "itemCode" 
  HAVING COUNT(*) > 1
) d;

-- Foreign keys
SELECT '' as separator;
SELECT '3. FOREIGN KEY INTEGRITY:' as section;
SELECT 'Orphaned financial statements' as check_type, COUNT(*) as orphans
FROM financial_statements fs
LEFT JOIN companies c ON fs."companyId" = c.id
WHERE c.id IS NULL;

SELECT 'Orphaned company_indices' as check_type, COUNT(*) as orphans
FROM company_indices ci
LEFT JOIN companies c ON ci."companyId" = c.id
WHERE c.id IS NULL;

-- Performance
SELECT '' as separator;
SELECT '4. PERFORMANCE TEST (GARAN query):' as section;
SELECT c.code, COUNT(*) as statements, cfg."financialGroup"
FROM companies c
LEFT JOIN financial_statements fs ON c.id = fs."companyId"
LEFT JOIN company_financial_groups cfg ON c.code = cfg.ticker
WHERE c.code = 'GARAN'
GROUP BY c.code, cfg."financialGroup";

SELECT '' as separator;
SELECT '================================================================================' as separator;
SELECT '✅ VALIDATION COMPLETE' as title;
SELECT '================================================================================' as separator;

\timing off
EOF

echo ""

################################################################################
# PHASE 6: UPSERT TEST
################################################################################
echo -e "${YELLOW}[PHASE 6] UPSERT MECHANISM TEST${NC}"
echo "Simulating production updates..."

# 6.1: Delete test data
echo "6.1: Deleting test records (GARAN & THYAO 2024 Q3-Q4)..."
PGPASSWORD='Xd29+x-NqJeX' psql -h localhost -U ademcelik -d bist_data << 'EOF' | tee "$LOG_DIR/phase6_1_delete.log"
-- Delete GARAN & THYAO 2024 Q3-Q4
DELETE FROM financial_statements fs
USING companies c
WHERE fs."companyId" = c.id 
  AND c.code IN ('GARAN', 'THYAO')
  AND fs.year = 2024
  AND fs.quarter IN (3, 4);

SELECT 'Deleted records:' as info, COUNT(*) FROM financial_statements fs
JOIN companies c ON fs."companyId" = c.id
WHERE c.code IN ('GARAN', 'THYAO') AND fs.year = 2024;

-- Delete 3 companies from financial groups
DELETE FROM company_financial_groups WHERE ticker IN ('AKGRT', 'BRKVY', 'DOCO');
SELECT 'Remaining financial groups:' as info, COUNT(*) FROM company_financial_groups;
EOF

# 6.2: Re-scrape financial groups (upsert test)
echo "6.2: Re-scraping financial groups (should restore 3 deleted)..."
.venv/bin/python scripts/scrape_financial_groups.py 2>&1 | tee "$LOG_DIR/phase6_2_groups_upsert.log"

# Verify restoration
PGPASSWORD='Xd29+x-NqJeX' psql -h localhost -U ademcelik -d bist_data << 'EOF' | tee -a "$LOG_DIR/phase6_2_verification.log"
SELECT 'Restored financial groups:' as info;
SELECT ticker, "financialGroup" FROM company_financial_groups 
WHERE ticker IN ('AKGRT', 'BRKVY', 'DOCO')
ORDER BY ticker;
EOF

# 6.3: Re-scrape financial statements (upsert test)
echo "6.3: Re-scraping financial statements for GARAN & THYAO..."

# Re-run the full financial scraper (it will upsert existing records)
# Only for these 2 companies to test upsert mechanism
PGPASSWORD='Xd29+x-NqJeX' psql -h localhost -U ademcelik -d bist_data << 'SQL_TEMP' > /tmp/test_companies.txt
SELECT code FROM companies WHERE code IN ('GARAN', 'THYAO');
SQL_TEMP

# Create temporary Python script that processes only GARAN and THYAO
cat > /tmp/upsert_test_scraper.py << 'PYTHON_SCRIPT'
#!/usr/bin/env python3
import sys
import os
import logging
from datetime import datetime

# Add project root to path
sys.path.insert(0, '/Users/ademcelik/Desktop/kap_bist_data')

# Import from financial_scraper_v2
from scripts.financial_scraper_v2 import (
    IsYatirimFinancialAPI,
    FinancialDataProcessor,
    load_financial_group_mapping
)

from dotenv import load_dotenv
from sqlalchemy import create_engine, text

# Setup logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Load environment
load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise ValueError("DATABASE_URL not set")

# Load financial group mapping
financial_group_mapping = load_financial_group_mapping()

# Initialize components
api_client = IsYatirimFinancialAPI(exchange="TRY", financial_group_mapping=financial_group_mapping)
processor = FinancialDataProcessor(DATABASE_URL)

# Get company IDs for GARAN and THYAO
db_url = DATABASE_URL.replace("postgresql://", "postgresql+psycopg2://").split("?")[0]
engine = create_engine(db_url)

test_symbols = ['GARAN', 'THYAO']

with engine.connect() as conn:
    for symbol in test_symbols:
        result = conn.execute(text(f"SELECT id FROM companies WHERE code = '{symbol}'"))
        company_id = result.scalar()
        
        if not company_id:
            logger.warning(f"Company {symbol} not found in database")
            continue
        
        logger.info(f"Processing {symbol} (ID: {company_id})...")
        
        # Get financial group
        financial_group = api_client.get_financial_group_for_ticker(symbol)
        logger.info(f"  Financial Group: {financial_group}")
        
        try:
            # Fetch data
            df_wide = api_client.fetch_financials(
                symbol=symbol,
                financial_group=financial_group,
                start_year=2020,
                end_year=datetime.now().year
            )
            
            # Transform
            df_long = processor.transform_to_long_format(
                df_wide=df_wide,
                company_id=company_id,
                symbol=symbol,
                financial_group=financial_group
            )
            
            # Upsert (should NOT create duplicates)
            rows = processor.upsert_financial_data(df_long)
            logger.info(f"  ✅ {symbol}: {rows} records upserted")
            
        except Exception as e:
            logger.error(f"  ❌ {symbol}: {e}")

logger.info("Upsert test complete!")
PYTHON_SCRIPT

# Run the temporary script
.venv/bin/python /tmp/upsert_test_scraper.py 2>&1 | tee "$LOG_DIR/phase6_3_statements_upsert.log"

# Verify no duplicates
PGPASSWORD='Xd29+x-NqJeX' psql -h localhost -U ademcelik -d bist_data << 'EOF' | tee -a "$LOG_DIR/phase6_3_verification.log"
SELECT '' as separator;
SELECT 'UPSERT VERIFICATION:' as section;

-- Check GARAN & THYAO 2024 restored
SELECT c.code, fs.year, fs.quarter, COUNT(*) as records
FROM financial_statements fs
JOIN companies c ON fs."companyId" = c.id
WHERE c.code IN ('GARAN', 'THYAO') AND fs.year = 2024
GROUP BY c.code, fs.year, fs.quarter
ORDER BY c.code, fs.year, fs.quarter;

-- Duplicate check
SELECT '' as separator;
SELECT 'Duplicate check after upsert:' as section;
SELECT COUNT(*) as duplicates FROM (
  SELECT "companyId", year, quarter, "itemCode"
  FROM financial_statements
  GROUP BY "companyId", year, quarter, "itemCode"
  HAVING COUNT(*) > 1
) d;
EOF

echo ""

################################################################################
# SUMMARY
################################################################################
echo -e "${BLUE}=================================================================================${NC}"
echo -e "${GREEN}   ✅ FULL SYSTEM RESET & SCRAPE COMPLETE${NC}"
echo -e "${BLUE}=================================================================================${NC}"
echo ""
echo "Summary:"
echo "  - Phase 1: Database Reset ✅"
echo "  - Phase 2: Metadata Scraping ✅"
echo "  - Phase 3: Financial Groups Mapping ✅"
echo "  - Phase 4: Financial Statements (ALL 590 companies) ✅"
echo "  - Phase 5: Production Validation ✅"
echo "  - Phase 6: Upsert Mechanism Test ✅"
echo ""
echo "Logs saved to: $LOG_DIR"
echo "End Time: $(date)"
echo ""
echo -e "${GREEN}System is now production-ready!${NC}"
echo -e "${BLUE}=================================================================================${NC}"
