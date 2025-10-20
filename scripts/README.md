# Essential Scripts Overview

This directory contains production-ready scripts for the KAP BIST data collection system.

## 🚀 Production Scripts (Must Keep)

### 1. `scrape_financial_groups.py`
**Purpose:** Web scraping to determine each company's financial reporting group  
**Frequency:** Quarterly (3 months)  
**Duration:** ~10 minutes  
**Output:** Populates `company_financial_groups` table with 590 mappings  

**Example:**
```bash
.venv/bin/python scripts/scrape_financial_groups.py
```

---

### 2. `financial_scraper_v2.py`
**Purpose:** Scrape financial statements for all companies with dynamic group support  
**Frequency:** Weekly (Sunday nights)  
**Duration:** ~2-3 hours  
**Output:** Populates `financial_statements` table with ~1.8M records  

**Features:**
- ✅ Dynamic financial group detection (UFRS_A, UFRS_B, etc.)
- ✅ Database mapping integration
- ✅ Upsert logic (safe to re-run)
- ✅ Comprehensive logging

**Example:**
```bash
.venv/bin/python scripts/financial_scraper_v2.py
```

---

## 🛠️ Utility Scripts

### 3. `monitor_scraping.sh`
**Purpose:** Real-time monitoring of scraping progress  
**Usage:**
```bash
./scripts/monitor_scraping.sh
```

**Output:**
- Current progress (X/592 companies)
- Success/failure counts
- Financial group distribution
- Database record count

---

## 📝 TypeScript Utilities

### 4. `refresh-tradable.ts`
**Purpose:** Update `isTradable` status for companies  
**Usage:**
```bash
npx ts-node scripts/refresh-tradable.ts
```

### 5. `targeted-company-detail.ts`
**Purpose:** Scrape detailed info for specific companies  
**Usage:**
```bash
npx ts-node scripts/targeted-company-detail.ts
```

---

## ⚠️ Important Notes

### Script Dependencies

```
Company Metadata (src/index.ts)
       ↓
Financial Groups (scrape_financial_groups.py)
       ↓
Financial Statements (financial_scraper_v2.py)
```

### Execution Order (First Deployment)
1. **Company metadata:** `node dist/index.js`
2. **Financial groups:** `.venv/bin/python scripts/scrape_financial_groups.py`
3. **Financial statements:** `.venv/bin/python scripts/financial_scraper_v2.py`

### Cron Schedule (Production)
See `DEPLOYMENT_SCHEDULE.md` for detailed cron configuration.

**Quick Reference:**
- Company metadata: Monthly (1st, 02:00)
- Financial groups: Quarterly (1st, 03:00)
- Financial statements: Weekly (Sunday, 04:00)

---

## 🧹 Removed Scripts

The following test/validation scripts were removed as they are not needed for production:

- ❌ `test_*.py` - Temporary test scripts
- ❌ `explore_*.py` - Exploration scripts
- ❌ `data_quality_checks.py` - One-time validation
- ❌ `financial_quarterly_update.py` - Replaced by v2
- ❌ `financial_scraper.py` - V1, replaced by V2
- ❌ `full_validation.py` - One-time validation
- ❌ `isyatirim_crosscheck.py` - One-time validation
- ❌ `quick_*.py` - Quick validation scripts
- ❌ `validate_financials.py` - One-time validation

All validation logic is now built into the main scrapers with comprehensive logging.

---

## 📊 Expected Outputs

| Script | Duration | Records | Frequency |
|--------|----------|---------|-----------|
| scrape_financial_groups.py | 10 min | 590 | Quarterly |
| financial_scraper_v2.py | 2-3 hours | ~1.8M | Weekly |

---

**For deployment instructions, see: `DEPLOYMENT_SCHEDULE.md`**
