# 📊 Finansal Tablo Schema Tasarımı (isyatirimhisse API v5.0.0)

## 🎯 Hedef

isyatirimhisse API'den çekilen quarterly (üç aylık) finansal tabloları veritabanına kaydetmek:
- **Bilanço (Aktif)** - FINANCIAL_ITEM_CODE: 1xxx
- **Bilanço (Pasif)** - FINANCIAL_ITEM_CODE: 2xxx  
- **Gelir Tablosu** - FINANCIAL_ITEM_CODE: 3xxx
- **Nakit Akış Tablosu** - FINANCIAL_ITEM_CODE: 4xxx

---

## 🔍 isyatirimhisse API Analizi

### API Çağrısı
```python
from isyatirimhisse import fetch_financials

df = fetch_financials(
    symbols="THYAO",           # veya ["THYAO", "GARAN"]
    start_year=2020,           # 5 yıl geriye
    end_year=2025,
    exchange="TRY",            # TRY | USD
    financial_group='1',       # '1': XI_29 | '2': UFRS | '3': UFRS_K
    save_to_excel=False
)
```

### Dönen DataFrame Yapısı
```
Columns:
- FINANCIAL_ITEM_CODE: str      # "1A", "2A", "3C", "4B"
- FINANCIAL_ITEM_NAME_TR: str   # "Dönen Varlıklar"
- FINANCIAL_ITEM_NAME_EN: str   # "CURRENT ASSETS"
- 2024/3: float                 # Q1 2024 değeri
- 2024/6: float                 # Q2 2024 değeri
- 2024/9: float                 # Q3 2024 değeri
- 2024/12: float                # Q4 2024 değeri (yıllık)
- 2025/3: float                 # Q1 2025 değeri
- ...
- SYMBOL: str                   # "THYAO"
```

**API Özellikleri:**
- **Wide Format** → Long Format'a dönüştürmeliyiz
- **Quarterly Columns**: `{year}/{month}` formatında (3, 6, 9, 12)
- **Statement Type**: FINANCIAL_ITEM_CODE'un ilk karakterinden çıkarılır
  - `1xxx`: Balance Sheet - Assets (Bilanço - Aktif)
  - `2xxx`: Balance Sheet - Liabilities (Bilanço - Pasif)
  - `3xxx`: Income Statement (Gelir Tablosu)
  - `4xxx`: Cash Flow (Nakit Akış)

---

## 🏗️ Schema Yaklaşımı: LONG/NARROW FORMAT

### Neden Long Format?

✅ **Avantajlar:**
- Her finansal kalem × dönem kombinasyonu ayrı satır → Esneklik
- Yeni finansal kalemler için schema değişikliği gerekmez
- Zaman serisi analizi kolay (quarterly trend, YoY, QoQ)
- API'den gelen dinamik kalemler kolayca eklenir
- Sektörel farklılıklara uyumlu (banka vs. sanayi)

❌ **Wide Format Problemi:**
- Her finansal kalem ayrı sütun → 150+ sütun
- Yeni kalem eklenince migration gerekir
- Sparse data (çoğu şirket bazı kalemleri raporlamaz)

---

## 📋 Finansal Tablo Schema (Prisma) - GÜNCELLENMİŞ ✅

\`\`\`prisma
// Finansal Tablo Kalemleri (Long Format)
// Her satır: 1 şirket × 1 kalem × 1 dönem
model FinancialStatement {
  id                      Int      @id @default(autoincrement())
  
  // Şirket Bilgisi
  companyId               Int
  
  // Dönem Bilgisi
  year                    Int      // 2024
  quarter                 Int      // 1, 2, 3, 4 (Q1-Q4)
  
  // Finansal Kalem Bilgisi
  itemCode                String   @db.VarChar(32)   // "1A", "2OA", "3C", "4CA"
  itemNameTR              String   @db.VarChar(256)  // "Dönen Varlıklar"
  itemNameEN              String?  @db.VarChar(256)  // "CURRENT ASSETS"
  
  // Değer
  value                   Decimal? @db.Decimal(20, 2) // TL cinsinden değer (nullable: bazı kalemler yok)
  
  // Statement Type (Auto-derived from itemCode)
  statementType           StatementType  // BALANCE_SHEET_ASSETS | INCOME_STATEMENT | etc.
  
  // Metadata
  financialGroup          String   @db.VarChar(16)   // "XI_29" | "UFRS" | "UFRS_K"
  currency                String   @default("TRY") @db.VarChar(8)
  
  // İlişkiler
  company                 Company  @relation(fields: [companyId], references: [id], onDelete: Cascade)
  
  // Timestamps
  createdAt               DateTime @default(now())
  updatedAt               DateTime @updatedAt
  
  // Unique constraint: Bir şirketin aynı dönem, kalem için tek değer olmalı
  @@unique([companyId, year, quarter, itemCode])
  @@index([companyId, year, quarter])
  @@index([companyId, itemCode])
  @@index([statementType, year, quarter])
  @@map("financial_statements")
}

// Finansal Tablo Türü (Enum)
enum StatementType {
  BALANCE_SHEET_ASSETS      // Bilanço - Aktif (1xxx)
  BALANCE_SHEET_LIABILITIES // Bilanço - Pasif (2xxx)
  INCOME_STATEMENT          // Gelir Tablosu (3xxx)
  CASH_FLOW                // Nakit Akış (4xxx)
}
\`\`\`

---

## 🔗 Company Model Güncellemesi

\`\`\`prisma
model Company {
  // ... mevcut alanlar ...
  
  // Finansal Tablolar (1:N ilişki)
  financialStatements  FinancialStatement[]
  
  // FreeFloat Bilgisi (1:1 inline - ayrı tablo gerekmez)
  freeFloatTicker      String?  @db.VarChar(16)      // "ASELS"
  freeFloatAmountTL    Decimal? @db.Decimal(20, 2)   // 1.175.811.253,84
  freeFloatPercent     Decimal? @db.Decimal(5, 2)    // 25,79%
}
\`\`\`

**Rationale: FreeFloat Ayrı Tablo mu?**
- ❌ **Ayrı Tablo**: Trading analizinde extra JOIN → performans kaybı
- ✅ **Inline (Company)**: 1:1 ilişki, sık erişilir, performans artışı
- **Karar**: Company modeline inline olarak ekle ✅

---

## 📊 Örnek Veri Yapısı

### API Response (Wide Format - Input)
| FINANCIAL_ITEM_CODE | FINANCIAL_ITEM_NAME_TR | FINANCIAL_ITEM_NAME_EN | 2024/3 | 2024/6 | 2024/9 | SYMBOL |
|---------------------|------------------------|------------------------|--------|--------|--------|--------|
| 1A | Dönen Varlıklar | CURRENT ASSETS | 275598000000 | 312030000000 | 338882000000 | THYAO |
| 3C | Satış Gelirleri | Net Sales | 147238000000 | 330113000000 | 551928000000 | THYAO |

### Veritabanı (Long Format - Stored)
| id | companyId | year | quarter | itemCode | itemNameTR | value | statementType |
|----|-----------|------|---------|----------|------------|-------|---------------|
| 1  | 63        | 2024 | 1       | 1A       | Dönen Varlıklar | 275598000000 | BALANCE_SHEET_ASSETS |
| 2  | 63        | 2024 | 2       | 1A       | Dönen Varlıklar | 312030000000 | BALANCE_SHEET_ASSETS |
| 3  | 63        | 2024 | 3       | 1A       | Dönen Varlıklar | 338882000000 | BALANCE_SHEET_ASSETS |
| 4  | 63        | 2024 | 1       | 3C       | Satış Gelirleri | 147238000000 | INCOME_STATEMENT |
| 5  | 63        | 2024 | 2       | 3C       | Satış Gelirleri | 330113000000 | INCOME_STATEMENT |

---

## 🎯 Sorgu Örnekleri

### 1. ASELS'in Son 4 Quarterly Net Satışları
```sql
SELECT year, quarter, value
FROM financial_statements
WHERE company_id = 63
  AND item_code = '3C'  -- Net Sales
ORDER BY year DESC, quarter DESC
LIMIT 4;
```

### 2. 2024 Q1'de En Yüksek Net Kar Yapan 10 Şirket
```sql
SELECT c.code, c.name, fs.value as net_income
FROM companies c
JOIN financial_statements fs ON fs.company_id = c.id
WHERE fs.year = 2024 
  AND fs.quarter = 1
  AND fs.item_code = '3Z'  -- Net Dönem Karı
ORDER BY fs.value DESC
LIMIT 10;
```

### 3. Quarterly Büyüme Oranı (QoQ)
```sql
WITH current_quarter AS (
  SELECT company_id, value
  FROM financial_statements
  WHERE year = 2024 AND quarter = 2 AND item_code = '3C'
),
previous_quarter AS (
  SELECT company_id, value
  FROM financial_statements
  WHERE year = 2024 AND quarter = 1 AND item_code = '3C'
)
SELECT 
  c.code,
  ((cq.value - pq.value) / NULLIF(pq.value, 0) * 100) as qoq_growth_percent
FROM current_quarter cq
JOIN previous_quarter pq ON cq.company_id = pq.company_id
JOIN companies c ON c.id = cq.company_id
ORDER BY qoq_growth_percent DESC;
```

### 4. Tüm Şirketlerin 2024 Yıllık (12. Ay) Bilanço Özeti
```sql
SELECT 
  c.code,
  c.name,
  MAX(CASE WHEN fs.item_code = '1BL' THEN fs.value END) as total_assets,
  MAX(CASE WHEN fs.item_code = '2Z' THEN fs.value END) as total_liabilities
FROM companies c
JOIN financial_statements fs ON fs.company_id = c.id
WHERE fs.year = 2024 AND fs.quarter = 4
  AND fs.item_code IN ('1BL', '2Z')
GROUP BY c.id, c.code, c.name;
```

---

## 🚀 İmplementasyon Stratejisi

### Faz 1: Schema Migration ✅
```bash
# Prisma schema'ya ekle
# prisma/schema.prisma

model Company {
  // FreeFloat inline
  freeFloatTicker   String?  @db.VarChar(16)
  freeFloatAmountTL Decimal? @db.Decimal(20, 2)
  freeFloatPercent  Decimal? @db.Decimal(5, 2)
  
  financialStatements FinancialStatement[]
}

enum StatementType {
  BALANCE_SHEET_ASSETS
  BALANCE_SHEET_LIABILITIES
  INCOME_STATEMENT
  CASH_FLOW
}

model FinancialStatement {
  id            Int      @id @default(autoincrement())
  companyId     Int
  year          Int
  quarter       Int
  itemCode      String   @db.VarChar(32)
  itemNameTR    String   @db.VarChar(256)
  itemNameEN    String?  @db.VarChar(256)
  value         Decimal? @db.Decimal(20, 2)
  statementType StatementType
  financialGroup String  @db.VarChar(16)
  currency      String   @default("TRY") @db.VarChar(8)
  
  company       Company  @relation(fields: [companyId], references: [id], onDelete: Cascade)
  
  createdAt     DateTime @default(now())
  updatedAt     DateTime @updatedAt
  
  @@unique([companyId, year, quarter, itemCode])
  @@index([companyId, year, quarter])
  @@index([companyId, itemCode])
  @@map("financial_statements")
}

# Migration
npm run db:push
```

### Faz 2: Python Scraper (isyatirimhisse)
```python
# scripts/financial_scraper.py
import pandas as pd
from isyatirimhisse import fetch_financials
from sqlalchemy import create_engine
from datetime import datetime

# Database bağlantısı
engine = create_engine('postgresql://bist:12345@localhost:5432/bist_data')

def determine_financial_group(company_code, main_sector_name):
    """
    Şirketin finansal grubunu belirle (XI_29 vs UFRS)
    """
    # Bankacılık ve Finans sektörü için UFRS
    financial_sectors = [
        'Bankacılık', 
        'Finansal Kiralama', 
        'Faktoring',
        'Sigorta',
        'Holdin Şirketleri'  # bazıları finans holdingi
    ]
    
    if any(sector in main_sector_name for sector in financial_sectors):
        return '2'  # UFRS
    else:
        return '1'  # XI_29

def determine_statement_type(item_code: str) -> str:
    """FINANCIAL_ITEM_CODE'dan statement type'ı belirle"""
    if not item_code:
        return None
    
    first_char = item_code[0]
    mapping = {
        '1': 'BALANCE_SHEET_ASSETS',
        '2': 'BALANCE_SHEET_LIABILITIES',
        '3': 'INCOME_STATEMENT',
        '4': 'CASH_FLOW'
    }
    return mapping.get(first_char)

def transform_wide_to_long(df_wide: pd.DataFrame) -> pd.DataFrame:
    """
    Wide format (API) → Long format (Database)
    """
    # Quarterly column'ları tespit et (örn: "2024/3", "2024/6")
    quarterly_cols = [col for col in df_wide.columns 
                      if '/' in col and col != 'SYMBOL']
    
    # Melt: Wide → Long
    df_long = df_wide.melt(
        id_vars=['FINANCIAL_ITEM_CODE', 'FINANCIAL_ITEM_NAME_TR', 
                 'FINANCIAL_ITEM_NAME_EN', 'SYMBOL'],
        value_vars=quarterly_cols,
        var_name='period',
        value_name='value'
    )
    
    # Period'u parse et: "2024/3" → year=2024, quarter=1
    df_long[['year', 'month']] = df_long['period'].str.split('/', expand=True).astype(int)
    df_long['quarter'] = df_long['month'] // 3  # 3→Q1, 6→Q2, 9→Q3, 12→Q4
    
    # Statement type ekle
    df_long['statement_type'] = df_long['FINANCIAL_ITEM_CODE'].apply(determine_statement_type)
    
    # Rename columns to match DB schema
    df_long = df_long.rename(columns={
        'FINANCIAL_ITEM_CODE': 'item_code',
        'FINANCIAL_ITEM_NAME_TR': 'item_name_tr',
        'FINANCIAL_ITEM_NAME_EN': 'item_name_en',
        'SYMBOL': 'symbol'
    })
    
    # Drop unnecessary columns
    df_long = df_long.drop(columns=['period', 'month'])
    
    return df_long

def scrape_company_financials(company_id, company_code, financial_group, start_year=2020):
    """
    Bir şirketin finansal tablolarını API'den çek ve veritabanına kaydet
    """
    try:
        # API'den veri çek (5 yıl geriye)
        df_wide = fetch_financials(
            symbols=company_code,
            start_year=start_year,
            end_year=datetime.now().year,
            exchange="TRY",
            financial_group=financial_group,
            save_to_excel=False
        )
        
        if df_wide.empty:
            print(f"⚠️  {company_code}: API'den veri gelmedi")
            return False
        
        # Wide → Long format dönüşümü
        df_long = transform_wide_to_long(df_wide)
        
        # Company ID ekle
        df_long['company_id'] = company_id
        df_long['financial_group'] = 'XI_29' if financial_group == '1' else 'UFRS'
        df_long['currency'] = 'TRY'
        
        # NULL değerleri kaldır (bazı kalemler bazı dönemlerde yok)
        df_long = df_long[df_long['value'].notna()]
        
        # Veritabanına upsert (ON CONFLICT DO UPDATE)
        # PostgreSQL'in conflict handling özelliğini kullan
        df_long.to_sql(
            'financial_statements_temp',
            engine,
            if_exists='replace',
            index=False
        )
        
        # Upsert SQL
        engine.execute(\"\"\"
            INSERT INTO financial_statements 
                (company_id, year, quarter, item_code, item_name_tr, item_name_en, 
                 value, statement_type, financial_group, currency, created_at, updated_at)
            SELECT 
                company_id, year, quarter, item_code, item_name_tr, item_name_en,
                value, statement_type, financial_group, currency,
                NOW(), NOW()
            FROM financial_statements_temp
            ON CONFLICT (company_id, year, quarter, item_code)
            DO UPDATE SET
                value = EXCLUDED.value,
                item_name_tr = EXCLUDED.item_name_tr,
                item_name_en = EXCLUDED.item_name_en,
                statement_type = EXCLUDED.statement_type,
                updated_at = NOW();
        \"\"\")
        
        print(f"✅ {company_code}: {len(df_long)} kayıt kaydedildi")
        return True
        
    except Exception as e:
        print(f"❌ {company_code}: {str(e)}")
        return False

def scrape_all_companies():
    """Tüm şirketlerin finansal tablolarını kazı"""
    # PostgreSQL'den şirketleri çek
    query = \"\"\"
        SELECT c.id, c.code, c.name, ms.name as main_sector
        FROM companies c
        LEFT JOIN main_sectors ms ON c.main_sector_id = ms.id
        ORDER BY c.code;
    \"\"\"
    
    df_companies = pd.read_sql(query, engine)
    
    total = len(df_companies)
    success = 0
    failed = []
    
    for idx, row in df_companies.iterrows():
        print(f"\\n[{idx+1}/{total}] {row['code']} - {row['name']}")
        
        # Financial group belirle
        financial_group = determine_financial_group(row['code'], row['main_sector'] or '')
        
        # Scrape
        if scrape_company_financials(row['id'], row['code'], financial_group):
            success += 1
        else:
            failed.append(row['code'])
    
    print(f"\\n{'='*60}")
    print(f"✅ Başarılı: {success}/{total}")
    print(f"❌ Başarısız: {len(failed)}/{total}")
    if failed:
        print(f"Başarısız şirketler: {', '.join(failed)}")

if __name__ == "__main__":
    scrape_all_companies()
```

### Faz 3: Veri Doğrulama
```python
# scripts/validate_financials.py

def validate_quarterly_data():
    """
    Quarterly veri bütünlüğünü kontrol et
    """
    query = \"\"\"
        SELECT 
            company_id,
            year,
            quarter,
            COUNT(DISTINCT item_code) as item_count
        FROM financial_statements
        GROUP BY company_id, year, quarter
        HAVING COUNT(DISTINCT item_code) < 50
        ORDER BY item_count;
    \"\"\"
    # Eksik kalem olan dönemleri tespit et

def detect_anomalies():
    \"\"\"
    Anormal değerleri tespit et (örn: negatif toplam aktif)
    \"\"\"
    query = \"\"\"
        SELECT c.code, fs.*
        FROM financial_statements fs
        JOIN companies c ON c.id = fs.company_id
        WHERE fs.item_code = '1BL'  -- Toplam Aktif
          AND fs.value < 0;
    \"\"\"

def check_historical_trends():
    \"\"\"
    Historical trend kontrolü (ani %1000 artış → hatalı veri?)
    \"\"\"
    pass
```

---

## 📝 Önemli Notlar

### 1. Financial Group Seçimi (Otomatik)
```python
# Banka/Finans → '2' (UFRS)
# Diğer tüm şirketler → '1' (XI_29)

if company.main_sector.name in ['Bankacılık', 'Finansal Kiralama', 'Faktoring']:
    financial_group = '2'
else:
    financial_group = '1'
```

### 2. Geriye Dönük Periyot: 5 YIL (20 Quarter) ✅

**Gerekçe:**
- **Minimum 3 yıl (12 Q)**: Temel trend analizi
- **İdeal 5 yıl (20 Q)**: Seasonal patterns, cycle detection
- **Trading için**: 5 yıl yeterli (daha eski veriler stale)
- **Database boyutu**: 710 şirket × 150 kalem × 20 Q = ~2.1M satır → kabul edilebilir

**Parametreler:**
```python
start_year = 2020  # 5 yıl geriye (2020-2025)
end_year = 2025    # Güncel yıl
```

### 3. Item Code Standardizasyonu

API'den gelen `FINANCIAL_ITEM_CODE` değerleri doğrudan kullanılır:
- Normalleştirme gerekmez (zaten standart)
- String comparison için case-sensitive

### 4. Currency

Şimdilik **TRY varsayılan**, gelecekte:
```python
exchange="USD"  # USD bazlı raporlama için
```

### 5. Upsert Stratejisi

**PostgreSQL ON CONFLICT**:
```sql
ON CONFLICT (company_id, year, quarter, item_code)
DO UPDATE SET
  value = EXCLUDED.value,
  updated_at = NOW();
```

Revize raporlar otomatik güncellenir.

### 6. Performance Optimization

**Indexes:**
- `(company_id, year, quarter)`: Dönemsel sorgular
- `(company_id, item_code)`: Specific item time-series
- `(statement_type, year, quarter)`: Sektörel karşılaştırma

---

## 🎯 FreeFloat: Company İçinde (Ayrı Tablo DEĞİL) ✅

**Rationale:**
- **1:1 İlişki**: Her şirketin tek bir FreeFloat değeri var
- **Sık Erişim**: Trading analizinde her sorguda kullanılır
- **Performance**: JOIN yapmaya gerek yok → hız artışı
- **Simplicity**: Schema daha temiz

**Company Model:**
```prisma
model Company {
  // ... mevcut alanlar ...
  
  // FreeFloat (inline)
  freeFloatTicker   String?  @db.VarChar(16)      // "ASELS"
  freeFloatAmountTL Decimal? @db.Decimal(20, 2)   // 1175811253.84
  freeFloatPercent  Decimal? @db.Decimal(5, 2)    // 25.79
  
  financialStatements FinancialStatement[]
}
```

---

## ✅ Schema Özet: ÖNCESİ vs SONRASI

### ❌ ÖNCEKI TASARIM (Hatalı)
```prisma
model FinancialStatement {
  id           Int
  companyId    Int
  statementType FinancialStatementType  // Enum: INCOME_STATEMENT
  year         Int
  quarter      Int
  periodEnd    DateTime  // ❌ Gereksiz
  reportedAt   DateTime? // ❌ API'de yok
  
  items        FinancialStatementItem[]  // ❌ Ayrı tablo → karmaşıklık
}

model FinancialStatementItem {
  id                   Int
  financialStatementId Int  // ❌ Foreign key → JOIN overhead
  itemCode             String
  itemNameTR           String
  value                Decimal
}
```

### ✅ YENİ TASARIM (Doğru)
```prisma
enum StatementType {
  BALANCE_SHEET_ASSETS
  BALANCE_SHEET_LIABILITIES
  INCOME_STATEMENT
  CASH_FLOW
}

model FinancialStatement {
  id            Int      @id @default(autoincrement())
  companyId     Int
  year          Int      // ✅ API'den direkt
  quarter       Int      // ✅ API'den direkt (1-4)
  itemCode      String   // ✅ Tek tabloda
  itemNameTR    String
  itemNameEN    String?
  value         Decimal?
  statementType StatementType  // ✅ itemCode'dan türetilir
  financialGroup String  // ✅ XI_29 | UFRS
  currency      String   @default("TRY")
  
  company       Company  @relation(fields: [companyId], references: [id])
  
  @@unique([companyId, year, quarter, itemCode])
}
```

**Avantajlar:**
- Tek tablo → hızlı sorgular
- API yapısına uyumlu
- Upsert kolay
- Index friendly

---

**Status**: ✅ Schema isyatirimhisse API v5.0.0'a göre güncellendi  
**Geriye Dönük Periyot**: 5 yıl (20 quarter)  
**Financial Group**: Otomatik belirleme (sektöre göre)  
**FreeFloat**: Company modeline inline eklendi
