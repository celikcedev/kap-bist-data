#!/bin/bash
# Update financial groups mapping by scraping IsYatirim website
# This should be run periodically (e.g., monthly) to catch any changes in company reporting formats

set -e  # Exit on error

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${YELLOW}🔄 Updating financial groups mapping from IsYatirim website...${NC}"

# Activate virtual environment
if [ -f "$PROJECT_DIR/.venv/bin/activate" ]; then
    source "$PROJECT_DIR/.venv/bin/activate"
else
    echo -e "${RED}❌ Error: Virtual environment not found${NC}"
    exit 1
fi

# Load environment variables
if [ -f "$PROJECT_DIR/.env" ]; then
    export $(grep -v '^#' "$PROJECT_DIR/.env" | xargs)
else
    echo -e "${RED}❌ Error: .env file not found${NC}"
    exit 1
fi

# Count before update
BEFORE_COUNT=$(psql "$DATABASE_URL" -t -c "SELECT COUNT(*) FROM company_financial_groups;" | tr -d ' ')
echo -e "${GREEN}📊 Current database records: $BEFORE_COUNT${NC}"

# Run scraper
echo -e "${YELLOW}🕷️  Scraping financial groups...${NC}"
python "$SCRIPT_DIR/scrape_financial_groups.py"

# Count after update
AFTER_COUNT=$(psql "$DATABASE_URL" -t -c "SELECT COUNT(*) FROM company_financial_groups;" | tr -d ' ')
echo -e "${GREEN}📊 Updated database records: $AFTER_COUNT${NC}"

# Export to CSV for Git tracking
echo -e "${YELLOW}📤 Exporting to CSV for version control...${NC}"
psql "$DATABASE_URL" -c "COPY (SELECT * FROM company_financial_groups ORDER BY ticker) TO STDOUT WITH CSV HEADER" > "$PROJECT_DIR/data/company_financial_groups.csv"

CSV_ROWS=$(tail -n +2 "$PROJECT_DIR/data/company_financial_groups.csv" | wc -l | tr -d ' ')
echo -e "${GREEN}✅ Exported $CSV_ROWS companies to CSV${NC}"

# Show any changes in financial groups
echo -e "${YELLOW}📋 Recent updates (last 24 hours):${NC}"
psql "$DATABASE_URL" -c "SELECT ticker, \"financialGroup\", \"displayName\", \"updatedAt\" FROM company_financial_groups WHERE \"updatedAt\" > NOW() - INTERVAL '24 hours' ORDER BY \"updatedAt\" DESC LIMIT 10;"

echo -e "${GREEN}✨ Done! Consider committing the updated CSV to Git.${NC}"
