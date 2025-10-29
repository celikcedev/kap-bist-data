#!/bin/bash
# Import company financial groups mapping to database

set -e  # Exit on error

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
CSV_FILE="$PROJECT_DIR/data/company_financial_groups.csv"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${YELLOW}🔄 Importing company financial groups mapping...${NC}"

# Check if CSV file exists
if [ ! -f "$CSV_FILE" ]; then
    echo -e "${RED}❌ Error: CSV file not found: $CSV_FILE${NC}"
    exit 1
fi

# Load environment variables
if [ -f "$PROJECT_DIR/.env" ]; then
    export $(grep -v '^#' "$PROJECT_DIR/.env" | xargs)
else
    echo -e "${RED}❌ Error: .env file not found${NC}"
    exit 1
fi

# Check if DATABASE_URL is set
if [ -z "$DATABASE_URL" ]; then
    echo -e "${RED}❌ Error: DATABASE_URL not set in .env${NC}"
    exit 1
fi

echo -e "${GREEN}📊 CSV file found: $CSV_FILE${NC}"
echo -e "${GREEN}🗄️  Database: $DATABASE_URL${NC}"

# Count rows in CSV (excluding header)
CSV_ROWS=$(tail -n +2 "$CSV_FILE" | wc -l | tr -d ' ')
echo -e "${YELLOW}📝 CSV contains $CSV_ROWS companies${NC}"

# Clear existing data
echo -e "${YELLOW}🗑️  Clearing existing data...${NC}"
psql "$DATABASE_URL" -c "TRUNCATE TABLE company_financial_groups RESTART IDENTITY CASCADE;" > /dev/null

# Import CSV
echo -e "${YELLOW}📥 Importing data...${NC}"
psql "$DATABASE_URL" -c "\COPY company_financial_groups(id,ticker,\"financialGroup\",\"displayName\",\"createdAt\",\"updatedAt\") FROM '$CSV_FILE' WITH CSV HEADER;" > /dev/null

# Verify import
DB_ROWS=$(psql "$DATABASE_URL" -t -c "SELECT COUNT(*) FROM company_financial_groups;" | tr -d ' ')
echo -e "${GREEN}✅ Import complete!${NC}"
echo -e "${GREEN}📊 Database now contains: $DB_ROWS companies${NC}"

# Show sample data
echo -e "${YELLOW}📋 Sample bank mappings:${NC}"
psql "$DATABASE_URL" -c "SELECT ticker, \"financialGroup\", \"displayName\" FROM company_financial_groups WHERE ticker IN ('AKBNK','GARAN','HALKB','VAKBN','YKBNK') ORDER BY ticker;"

echo -e "${GREEN}✨ Done!${NC}"
