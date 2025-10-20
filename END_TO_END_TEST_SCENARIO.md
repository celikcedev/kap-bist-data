# 🧪 End-to-End Test Scenario - Production Deployment Simulation

## 📋 Amaç
VPS deployment öncesi **geliştirme ortamında** tam deployment sürecini simüle etmek:
1. ✅ Clean database start (tüm tabloları drop)
2. ✅ İlk deployment scraping (metadata → groups → statements)
3. ✅ Upsert mekanizması testi (veri silme → yeniden scraping → veri restore)
4. ✅ Production readiness validation

---

## 🔧 Hazırlık Kontrolleri

### ✅ Sistem Gereksinimleri

```bash
# 1. Python virtual environment aktif mi?
source .venv/bin/activate
python --version  # Python 3.11+ olmalı

# 2. Node.js dependencies kurulu mu?
ls node_modules/@prisma node_modules/playwright

# 3. TypeScript build edilmiş mi?
ls dist/index.js dist/orchestrator.js

# 4. .env dosyası var mı?
cat .env  # DATABASE_URL olmalı

# 5. PostgreSQL çalışıyor mu?
psql -h localhost -U bist -d bist_data -c "SELECT 1;"
```

**Expected Output:**
```
✅ Python: 3.11.x
✅ Node modules: @prisma, playwright mevcut
✅ TypeScript: dist/ klasörü dolu
✅ .env: DATABASE_URL configured
✅ PostgreSQL: Connection successful
```

---

## 🚀 PHASE 1: Clean Start - İlk Deployment Simülasyonu

### Step 1.1: Database Sıfırlama (⚠️ Dikkat: Tüm data silinecek!)

```bash
# Option A: Prisma ile (Önerilen - güvenli)
npx prisma migrate reset --force --skip-seed

# Option B: SQL ile manuel (alternatif)
psql -h localhost -U bist -d bist_data << 'EOF'
DROP SCHEMA public CASCADE;
CREATE SCHEMA public;
GRANT ALL ON SCHEMA public TO bist;
GRANT ALL ON SCHEMA public TO public;
EOF

# Schema'yı yeniden oluştur
npx prisma db push --force-reset
npx prisma generate
```

**Expected Output:**
```
✅ Database reset successfully
✅ Schema recreated
✅ 0 tables with data
```

**Validation:**
```sql
-- Tüm tabloları listele (boş olmalı)
SELECT 
    schemaname,
    tablename,
    (SELECT COUNT(*) FROM information_schema.tables t 
     WHERE t.table_schema = 'public') as total_tables
FROM pg_tables 
WHERE schemaname = 'public';

-- Expected: 11 tables, all empty
```

---

### Step 1.2: Company Metadata Scraping

```bash
# Log directory oluştur
mkdir -p logs

# Company metadata scrape et
node dist/index.js > logs/test_metadata_$(date +%Y%m%d_%H%M%S).log 2>&1

# Real-time takip için (başka terminal):
tail -f logs/test_metadata_*.log
```

**Expected Duration:** ~2-3 dakika

**Validation:**
```sql
-- Veri sayılarını kontrol et
SELECT 'main_sectors' as table_name, COUNT(*) as count FROM main_sectors
UNION ALL
SELECT 'sub_sectors', COUNT(*) FROM sub_sectors
UNION ALL
SELECT 'markets', COUNT(*) FROM markets
UNION ALL
SELECT 'indices', COUNT(*) FROM indices
UNION ALL
SELECT 'companies', COUNT(*) FROM companies;

-- Expected results:
-- main_sectors: ~12-15
-- sub_sectors: ~100-120
-- markets: ~5-7
-- indices: ~20-25
-- companies: ~590-600
```

---

### Step 1.3: Financial Groups Mapping

```bash
# Financial groups scrape et (tüm şirketler için)
python scripts/scrape_financial_groups.py \
  > logs/test_financial_groups_$(date +%Y%m%d_%H%M%S).log 2>&1

# Real-time takip:
tail -f logs/test_financial_groups_*.log
```

**Expected Duration:** ~10 dakika (590 şirket için)

**Validation:**
```sql
-- Financial groups dağılımını kontrol et
SELECT 
    "financialGroup",
    COUNT(*) as company_count,
    ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER(), 2) as percentage
FROM company_financial_groups
GROUP BY "financialGroup"
ORDER BY company_count DESC;

-- Expected results:
-- XI_29: ~556 companies (94%)
-- UFRS_K: ~19 companies
-- XI_29K: ~10 companies
-- UFRS_B: ~3 companies
-- UFRS: ~1 company
-- UFRS_A: ~1 company
-- Total: ~590 companies

-- Örnek şirketleri kontrol et
SELECT ticker, "financialGroup" 
FROM company_financial_groups 
WHERE ticker IN ('GARAN', 'THYAO', 'AKGRT', 'AGESA', 'BRKVY')
ORDER BY ticker;

-- Expected:
-- AGESA: XI_29
-- AKGRT: XI_29K
-- BRKVY: UFRS_B
-- GARAN: UFRS_K
-- THYAO: XI_29
```

---

### Step 1.4: Financial Statements Scraping (SUBSET - Test için)

**Not:** Test için sadece 10 şirket scrape edeceğiz (production'da tümü yapılacak).

Test şirket seçimi:
- **GARAN** (UFRS_K - Büyük banka)
- **THYAO** (XI_29 - Türk Hava Yolları)
- **AKGRT** (XI_29K - Factoring, daha önce failed)
- **AGESA** (XI_29 - Daha önce failed)
- **BRKVY** (UFRS_B - DO&CO grubu)
- **DOCO** (UFRS_A - DO&CO ana şirket)
- **ISCTR** (UFRS - Banka)
- **TUPRS** (XI_29 - Tüpraş)
- **EREGL** (XI_29 - Erdemir)
- **SAHOL** (XI_29 - Sabancı Holding)

```bash
# Test için özel scraper scripti oluştur
cat > scripts/financial_scraper_test_subset.py << 'EOF'
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
EOF

chmod +x scripts/financial_scraper_test_subset.py

# Test subset'i çalıştır
python scripts/financial_scraper_test_subset.py \
  > logs/test_financial_statements_$(date +%Y%m%d_%H%M%S).log 2>&1

# Real-time takip:
tail -f logs/test_financial_statements_*.log
```

**Expected Duration:** ~15-20 dakika (10 şirket)

**Validation:**
```sql
-- Financial statements toplam record sayısı
SELECT COUNT(*) as total_records FROM financial_statements;
-- Expected: ~30,000-40,000 records (10 companies × 20 quarters × ~200 items)

-- Şirket başına record sayısı
SELECT 
    c.code,
    COUNT(fs.id) as record_count,
    MIN(fs.year) as first_year,
    MAX(fs.year) as last_year,
    COUNT(DISTINCT fs.year || '-' || fs.quarter) as total_periods
FROM financial_statements fs
JOIN companies c ON fs."companyId" = c.id
WHERE c.code IN ('GARAN', 'THYAO', 'AKGRT', 'AGESA', 'BRKVY', 
                 'DOCO', 'ISCTR', 'TUPRS', 'EREGL', 'SAHOL')
GROUP BY c.code
ORDER BY c.code;

-- Expected: Her şirket için 2020-2025 arası ~20 dönem, ~3000-4000 record

-- GARAN detaylı kontrol (kritik test case)
SELECT 
    year,
    quarter,
    COUNT(*) as item_count
FROM financial_statements
WHERE "companyId" = (SELECT id FROM companies WHERE code = 'GARAN')
GROUP BY year, quarter
ORDER BY year, quarter;

-- Expected: Her dönem için ~160-200 item
```

---

## 🔄 PHASE 2: Upsert Test - Simulated Production Update

### Step 2.1: Belirli Verileri Sil (Upsert testi için)

```sql
-- Senaryo: GARAN ve THYAO için 2024 Q3-Q4 verilerini silelim
-- Bu, çeyrek dönem raporu güncellemesi simülasyonu

-- Önce mevcut veriyi kaydet (backup)
CREATE TEMP TABLE deleted_records_backup AS
SELECT * FROM financial_statements
WHERE "companyId" IN (
    SELECT id FROM companies WHERE code IN ('GARAN', 'THYAO')
)
AND year = 2024
AND quarter IN (3, 4);

-- Kaç kayıt silineceğini göster
SELECT 
    c.code,
    fs.year,
    fs.quarter,
    COUNT(*) as records_to_delete
FROM financial_statements fs
JOIN companies c ON fs."companyId" = c.id
WHERE c.code IN ('GARAN', 'THYAO')
AND year = 2024
AND quarter IN (3, 4)
GROUP BY c.code, fs.year, fs.quarter
ORDER BY c.code, fs.year, fs.quarter;

-- Expected: GARAN ve THYAO için ~600-800 record silinecek

-- VERİLERİ SİL
DELETE FROM financial_statements
WHERE "companyId" IN (
    SELECT id FROM companies WHERE code IN ('GARAN', 'THYAO')
)
AND year = 2024
AND quarter IN (3, 4);

-- Silme sonrası kontrol
SELECT 
    c.code,
    COUNT(*) as remaining_records,
    MAX(year || '-Q' || quarter) as latest_period
FROM financial_statements fs
JOIN companies c ON fs."companyId" = c.id
WHERE c.code IN ('GARAN', 'THYAO')
GROUP BY c.code;

-- Expected: GARAN ve THYAO için 2024-Q3/Q4 YOK, latest_period: 2024-Q2 olmalı
```

```sql
-- Ayrıca: 3 şirketi financial_groups tablosundan silelim
-- Bu, yeni şirket ekleme veya grup değişikliği simülasyonu

-- Silinecek şirketler
DELETE FROM company_financial_groups
WHERE ticker IN ('AKGRT', 'BRKVY', 'DOCO');

-- Kontrol
SELECT COUNT(*) FROM company_financial_groups;
-- Expected: ~587 (590 - 3)

SELECT ticker FROM company_financial_groups 
WHERE ticker IN ('AKGRT', 'BRKVY', 'DOCO');
-- Expected: 0 rows
```

---

### Step 2.2: Upsert - Financial Groups Yeniden Scrape

```bash
# Financial groups'u yeniden çalıştır (sadece silinen 3 şirket eklenecek)
python scripts/scrape_financial_groups.py \
  > logs/test_upsert_groups_$(date +%Y%m%d_%H%M%S).log 2>&1

# Takip et
tail -f logs/test_upsert_groups_*.log
```

**Expected Duration:** ~10 dakika

**Validation:**
```sql
-- Silinen şirketler geri geldi mi?
SELECT ticker, "financialGroup", "updatedAt"
FROM company_financial_groups
WHERE ticker IN ('AKGRT', 'BRKVY', 'DOCO')
ORDER BY ticker;

-- Expected:
-- AKGRT: XI_29K
-- BRKVY: UFRS_B
-- DOCO: UFRS_A
-- updatedAt: ŞİMDİ (yeni timestamp)

-- Toplam sayı kontrol
SELECT COUNT(*) FROM company_financial_groups;
-- Expected: ~590 (eski hale döndü)

-- Duplicate kontrolü (çok önemli!)
SELECT ticker, COUNT(*) as count
FROM company_financial_groups
GROUP BY ticker
HAVING COUNT(*) > 1;
-- Expected: 0 rows (duplicate YOK)
```

---

### Step 2.3: Upsert - Financial Statements Yeniden Scrape

```bash
# Test subset'i yeniden çalıştır (silinen GARAN, THYAO verileri geri gelecek)
python scripts/financial_scraper_test_subset.py \
  > logs/test_upsert_statements_$(date +%Y%m%d_%H%M%S).log 2>&1

# Takip et
tail -f logs/test_upsert_statements_*.log
```

**Expected Duration:** ~15-20 dakika

**Validation:**
```sql
-- GARAN ve THYAO için 2024 Q3-Q4 geri geldi mi?
SELECT 
    c.code,
    fs.year,
    fs.quarter,
    COUNT(*) as record_count,
    MIN(fs."updatedAt") as first_update,
    MAX(fs."updatedAt") as last_update
FROM financial_statements fs
JOIN companies c ON fs."companyId" = c.id
WHERE c.code IN ('GARAN', 'THYAO')
AND year = 2024
AND quarter IN (3, 4)
GROUP BY c.code, fs.year, fs.quarter
ORDER BY c.code, fs.year, fs.quarter;

-- Expected: GARAN ve THYAO için 2024-Q3, 2024-Q4 mevcut
-- updatedAt: ŞİMDİ (yeni timestamp, upsert çalıştı)

-- Toplam record sayısı değişti mi?
SELECT COUNT(*) as total_records FROM financial_statements;
-- Expected: İlk scraping ile AYNI sayı (upsert duplicate yaratmadı)

-- Duplicate kontrolü (çok önemli!)
SELECT 
    "companyId",
    year,
    quarter,
    "itemCode",
    COUNT(*) as count
FROM financial_statements
GROUP BY "companyId", year, quarter, "itemCode"
HAVING COUNT(*) > 1
LIMIT 10;
-- Expected: 0 rows (duplicate YOK)

-- Tüm test şirketleri için son durum
SELECT 
    c.code,
    COUNT(fs.id) as total_records,
    COUNT(DISTINCT fs.year || '-' || fs.quarter) as periods,
    MIN(fs.year) as first_year,
    MAX(fs.year || '-Q' || fs.quarter) as latest_period
FROM financial_statements fs
JOIN companies c ON fs."companyId" = c.id
WHERE c.code IN ('GARAN', 'THYAO', 'AKGRT', 'AGESA', 'BRKVY', 
                 'DOCO', 'ISCTR', 'TUPRS', 'EREGL', 'SAHOL')
GROUP BY c.code
ORDER BY c.code;

-- Expected: Her şirket için ~20 dönem, ~3000-4000 record
-- latest_period: 2025-Q3 veya 2025-Q2 (bugüne göre)
```

---

## ✅ PHASE 3: Production Readiness Validation

### Final Checklist

```bash
# 1. Tüm dependencies kurulu mu?
pip list | grep -E "(beautifulsoup4|requests|psycopg2|pandas|sqlalchemy|python-dotenv)"
npm list --depth=0 | grep -E "(prisma|playwright|dotenv)"

# 2. Script dosyaları executable mi?
ls -l scripts/*.py scripts/*.sh

# 3. Log directory mevcut mu?
ls -ld logs/

# 4. .env dosyası production-ready mi?
cat .env

# 5. TypeScript build güncel mi?
ls -lt dist/ | head -10

# 6. Database bağlantısı stabil mi?
for i in {1..5}; do
  psql -h localhost -U bist -d bist_data -c "SELECT COUNT(*) FROM companies;" && \
  echo "Test $i: OK"
done
```

### Database Health Check

```sql
-- Tüm tabloların data'sı var mı?
SELECT 
    schemaname,
    tablename,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size,
    (SELECT COUNT(*) 
     FROM information_schema.columns 
     WHERE table_schema = schemaname 
     AND table_name = tablename) AS column_count
FROM pg_tables 
WHERE schemaname = 'public'
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;

-- Expected: financial_statements en büyük tablo (~10-50 MB test data için)

-- Index'ler mevcut mu?
SELECT 
    schemaname,
    tablename,
    indexname,
    indexdef
FROM pg_indexes
WHERE schemaname = 'public'
ORDER BY tablename, indexname;

-- Expected: Primary keys, foreign keys, unique indexes mevcut

-- Foreign key constraints kontrol
SELECT
    tc.table_name, 
    kcu.column_name, 
    ccu.table_name AS foreign_table_name,
    ccu.column_name AS foreign_column_name 
FROM information_schema.table_constraints AS tc 
JOIN information_schema.key_column_usage AS kcu
  ON tc.constraint_name = kcu.constraint_name
JOIN information_schema.constraint_column_usage AS ccu
  ON ccu.constraint_name = tc.constraint_name
WHERE tc.constraint_type = 'FOREIGN KEY'
AND tc.table_schema = 'public'
ORDER BY tc.table_name;

-- Expected: All foreign keys intact
```

### Performance Test

```sql
-- Query performance test
EXPLAIN ANALYZE
SELECT 
    c.code,
    c.name,
    ms.name as sector,
    COUNT(fs.id) as statement_count
FROM companies c
LEFT JOIN main_sectors ms ON c."mainSectorId" = ms.id
LEFT JOIN financial_statements fs ON fs."companyId" = c.id
WHERE c.code IN ('GARAN', 'THYAO', 'AKGRT')
GROUP BY c.code, c.name, ms.name
ORDER BY c.code;

-- Expected: Execution time < 100ms
```

---

## 📊 Expected Test Results Summary

### Phase 1: Clean Start
| Step | Expected Result | Duration |
|------|----------------|----------|
| Database reset | ✅ All tables empty | ~10 sec |
| Company metadata | ✅ ~590 companies | ~2-3 min |
| Financial groups | ✅ ~590 mappings | ~10 min |
| Financial statements (10 co.) | ✅ ~35,000 records | ~15-20 min |

### Phase 2: Upsert Test
| Step | Expected Result | Validation |
|------|----------------|-----------|
| Delete GARAN/THYAO Q3-Q4 2024 | ✅ ~600-800 records deleted | SQL query |
| Delete 3 companies from groups | ✅ 587 groups remaining | SQL query |
| Re-scrape financial groups | ✅ 590 groups restored | No duplicates |
| Re-scrape financial statements | ✅ Q3-Q4 data restored | No duplicates |

### Phase 3: Production Ready
| Check | Status | Evidence |
|-------|--------|----------|
| Dependencies complete | ✅ | pip list, npm list |
| Scripts executable | ✅ | ls -l scripts/ |
| Database stable | ✅ | 5x connection test |
| No duplicates | ✅ | SQL duplicate queries |
| Performance OK | ✅ | Query < 100ms |

---

## 🚨 Troubleshooting

### Sorun: Database connection failed

```bash
# PostgreSQL çalışıyor mu?
pg_isready -h localhost -p 5432

# Port dinliyor mu?
lsof -i :5432

# Credentials doğru mu?
psql -h localhost -U bist -d bist_data -c "SELECT current_user, current_database();"
```

### Sorun: Python import error

```bash
# Virtual environment aktif mi?
which python  # .venv/bin/python olmalı

# Dependencies tekrar kur
pip install -r requirements.txt

# Script path sorunu
export PYTHONPATH=/Users/ademcelik/Desktop/kap_bist_data:$PYTHONPATH
```

### Sorun: TypeScript build hataları

```bash
# Clean build
rm -rf dist/
npm run build

# Dependencies tekrar kur
rm -rf node_modules/
npm install
```

### Sorun: Scraping çok yavaş

```bash
# Rate limiting azalt (dikkatli!)
# financial_scraper_v2.py içinde:
# RATE_LIMIT_DELAY = (0.2, 0.5)  # Varsayılan: (0.5, 1.5)
```

---

## ✅ Test Completion Criteria

Test **BAŞARILI** sayılır eğer:

1. ✅ **Phase 1:** Tüm metadata, groups, statements başarıyla scrape edildi
2. ✅ **Phase 2:** Silinen veriler upsert ile geri geldi, duplicate YOK
3. ✅ **Phase 3:** Tüm dependencies kurulu, database healthy
4. ✅ **No Errors:** Loglar'da kritik hata yok
5. ✅ **Performance:** Query response time < 100ms

---

## 🎯 Post-Test Actions

Test başarılı olduktan sonra:

```bash
# 1. Test subset scraper'ı sil (artık gerekli değil)
rm scripts/financial_scraper_test_subset.py

# 2. Test loglarını arşivle
mkdir -p logs/archive/test_$(date +%Y%m%d)
mv logs/test_*.log logs/archive/test_$(date +%Y%m%d)/

# 3. Production'a hazır commit
git add .
git commit -m "✅ End-to-end test completed - Production ready"

# 4. VPS deployment başlat
# DEPLOYMENT_SCHEDULE.md dosyasını takip et
```

---

## 📝 Notlar

- **Test süresi:** ~45-60 dakika (phase 1 + 2 + 3)
- **Disk kullanımı:** ~50-100 MB (10 company test data)
- **Production deployment:** Test başarılı olduktan sonra DEPLOYMENT_SCHEDULE.md'ye göre ilerle
- **Full scraping:** Production'da tüm 590 şirket için ~2-3 saat
