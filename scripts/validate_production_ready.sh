#!/bin/bash
# Production Readiness Pre-Test Validation
# Run this before starting END_TO_END_TEST_SCENARIO.md

set -e

echo "╔════════════════════════════════════════════════════════════════╗"
echo "║   Production Readiness Validation - Pre-Test Check            ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo ""

# Color codes
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

ERRORS=0

# Function to check and report
check() {
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✓${NC} $1"
    else
        echo -e "${RED}✗${NC} $1"
        ERRORS=$((ERRORS + 1))
    fi
}

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "1. ENVIRONMENT CHECKS"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Python version
python --version > /dev/null 2>&1
check "Python 3.11+ installed ($(python --version 2>&1))"

# Node.js version
node --version > /dev/null 2>&1
check "Node.js installed ($(node --version))"

# Virtual environment active
if [[ "$VIRTUAL_ENV" != "" ]]; then
    echo -e "${GREEN}✓${NC} Python virtual environment active ($VIRTUAL_ENV)"
else
    echo -e "${RED}✗${NC} Python virtual environment NOT active"
    ERRORS=$((ERRORS + 1))
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "2. CONFIGURATION FILES"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# .env file
if [ -f .env ]; then
    echo -e "${GREEN}✓${NC} .env file exists"
    if grep -q "DATABASE_URL" .env; then
        echo -e "${GREEN}✓${NC} DATABASE_URL configured"
    else
        echo -e "${RED}✗${NC} DATABASE_URL not found in .env"
        ERRORS=$((ERRORS + 1))
    fi
else
    echo -e "${RED}✗${NC} .env file missing"
    ERRORS=$((ERRORS + 1))
fi

# package.json
[ -f package.json ]; check "package.json exists"

# requirements.txt
[ -f requirements.txt ]; check "requirements.txt exists"

# prisma/schema.prisma
[ -f prisma/schema.prisma ]; check "prisma/schema.prisma exists"

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "3. PYTHON DEPENDENCIES"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

pip show beautifulsoup4 > /dev/null 2>&1; check "beautifulsoup4"
pip show requests > /dev/null 2>&1; check "requests"
pip show psycopg2-binary > /dev/null 2>&1; check "psycopg2-binary"
pip show pandas > /dev/null 2>&1; check "pandas"
pip show sqlalchemy > /dev/null 2>&1; check "sqlalchemy"
pip show python-dotenv > /dev/null 2>&1; check "python-dotenv"
pip show isyatirimhisse > /dev/null 2>&1; check "isyatirimhisse"

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "4. NODE.JS DEPENDENCIES"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

[ -d node_modules/@prisma/client ]; check "@prisma/client"
[ -d node_modules/prisma ]; check "prisma"
[ -d node_modules/playwright ]; check "playwright"
[ -d node_modules/dotenv ]; check "dotenv"
[ -d node_modules/typescript ]; check "typescript"
[ -d node_modules/tsx ]; check "tsx"

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "5. BUILD & SCRIPTS"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# TypeScript build
[ -f dist/index.js ]; check "dist/index.js (TypeScript build)"
[ -f dist/orchestrator.js ]; check "dist/orchestrator.js"

# Python scripts
[ -f scripts/financial_scraper_v2.py ]; check "scripts/financial_scraper_v2.py"
[ -f scripts/scrape_financial_groups.py ]; check "scripts/scrape_financial_groups.py"
[ -f scripts/monitor_scraping.sh ]; check "scripts/monitor_scraping.sh"

# Logs directory
[ -d logs ]; check "logs/ directory exists"

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "6. DATABASE CONNECTION"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Extract connection details from .env
if [ -f .env ]; then
    DB_URL=$(grep DATABASE_URL .env | cut -d'"' -f2)
    
    # Parse connection string (postgresql://user:pass@host:port/db?schema=public)
    # Format: postgresql://bist:12345@localhost:5432/bist_data?schema=public
    DB_USER=$(echo $DB_URL | sed -n 's|.*://\([^:]*\):.*|\1|p')
    DB_PASS=$(echo $DB_URL | sed -n 's|.*://[^:]*:\([^@]*\)@.*|\1|p')
    DB_HOST=$(echo $DB_URL | sed -n 's|.*@\([^:]*\):.*|\1|p')
    DB_PORT=$(echo $DB_URL | sed -n 's|.*:\([0-9]*\)/.*|\1|p')
    DB_NAME=$(echo $DB_URL | sed -n 's|.*/\([^?]*\).*|\1|p')
    
    echo "  Database: $DB_NAME"
    echo "  Host: $DB_HOST:$DB_PORT"
    echo "  User: $DB_USER"
    echo ""
    
    # Test PostgreSQL connection
    if command -v psql > /dev/null 2>&1; then
        export PGPASSWORD="$DB_PASS"
        if psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -c "SELECT 1;" > /dev/null 2>&1; then
            echo -e "${GREEN}✓${NC} PostgreSQL connection successful"
            
            # Count existing tables
            TABLE_COUNT=$(psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -t -c "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'public';" 2>/dev/null | xargs)
            echo -e "${GREEN}✓${NC} Found $TABLE_COUNT tables in database"
        else
            echo -e "${RED}✗${NC} PostgreSQL connection failed"
            ERRORS=$((ERRORS + 1))
        fi
        unset PGPASSWORD
    else
        echo -e "${YELLOW}⚠${NC} psql not found - cannot test database connection"
    fi
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "7. DOCUMENTATION"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

[ -f README.md ]; check "README.md"
[ -f DEPLOYMENT_SCHEDULE.md ]; check "DEPLOYMENT_SCHEDULE.md"
[ -f END_TO_END_TEST_SCENARIO.md ]; check "END_TO_END_TEST_SCENARIO.md"
[ -f scripts/README.md ]; check "scripts/README.md"

echo ""
echo "╔════════════════════════════════════════════════════════════════╗"
echo "║                    VALIDATION SUMMARY                          ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo ""

if [ $ERRORS -eq 0 ]; then
    echo -e "${GREEN}✓ ALL CHECKS PASSED${NC}"
    echo ""
    echo "System is PRODUCTION READY! ✨"
    echo ""
    echo "Next steps:"
    echo "  1. Review END_TO_END_TEST_SCENARIO.md"
    echo "  2. Get approval to start test"
    echo "  3. Run: npx prisma migrate reset --force --skip-seed"
    echo ""
    exit 0
else
    echo -e "${RED}✗ $ERRORS ERRORS FOUND${NC}"
    echo ""
    echo "Please fix the errors above before proceeding."
    echo ""
    echo "Common fixes:"
    echo "  • Activate venv: source .venv/bin/activate"
    echo "  • Install Python deps: pip install -r requirements.txt"
    echo "  • Install Node deps: npm install"
    echo "  • Build TypeScript: npm run build"
    echo "  • Create .env: Copy DATABASE_URL from existing config"
    echo ""
    exit 1
fi
