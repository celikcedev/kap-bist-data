#!/usr/bin/env python3
"""
Quick test script for XI_29K financial group fix
Tests: GARFA (Faktoring) and ISFIN (Leasing)
"""

import os
import sys
from datetime import datetime
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

# Add scripts directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'scripts'))

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise ValueError("DATABASE_URL environment variable is not set")

db_url = DATABASE_URL.replace("postgresql://", "postgresql+psycopg2://").split("?")[0]
engine = create_engine(db_url)

# Import after setting up path
from financial_scraper import scrape_company_financials, determine_financial_group

def test_xi_29k_companies():
    """Test scraping for XI_29K companies"""
    
    test_companies = [
        ("GARFA", "Faktoring"),
        ("ISFIN", "Finansal Kiralama"),
    ]
    
    print("=" * 80)
    print("XI_29K FİNANSAL GROUP TEST")
    print("=" * 80)
    print(f"Test başlangıç: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    for code, sector in test_companies:
        print(f"\n{'='*80}")
        print(f"🔍 Test: {code} ({sector})")
        print(f"{'='*80}")
        
        # Get company info from database
        query = text("""
            SELECT c.id, c.code, c.name, ms.name as main_sector
            FROM companies c
            LEFT JOIN main_sectors ms ON c."mainSectorId" = ms.id
            WHERE c.code = :code
        """)
        
        with engine.connect() as conn:
            result = conn.execute(query, {"code": code}).fetchone()
            
            if not result:
                print(f"❌ {code} veritabanında bulunamadı!")
                continue
            
            company_id, company_code, company_name, main_sector = result
            print(f"✓ Şirket bilgileri:")
            print(f"  - ID: {company_id}")
            print(f"  - Kod: {company_code}")
            print(f"  - İsim: {company_name}")
            print(f"  - Sektör: {main_sector}")
            
            # Determine financial group
            financial_group = determine_financial_group(company_code, main_sector or "", engine)
            group_names = {"1": "XI_29", "2": "UFRS", "3": "UFRS_K", "4": "XI_29K"}
            print(f"  - Financial Group: {group_names.get(financial_group, 'UNKNOWN')} (code: {financial_group})")
            
            if financial_group != "4":
                print(f"⚠️  UYARI: {code} için XI_29K (4) bekleniyor, ama {financial_group} tespit edildi!")
            
            # Check if data already exists
            check_query = text("""
                SELECT COUNT(*) as count
                FROM financial_statements
                WHERE "companyId" = :company_id
            """)
            existing_count = conn.execute(check_query, {"company_id": company_id}).scalar()
            print(f"  - Mevcut kayıt sayısı: {existing_count}")
            
            print(f"\n🚀 Scraping başlatılıyor...")
            print(f"   Parametreler: code={company_code}, group={financial_group}, start_year=2020")
            
            # Scrape
            success = scrape_company_financials(
                company_id=company_id,
                company_code=company_code,
                financial_group=financial_group,
                start_year=2020
            )
            
            if success:
                # Check new count
                new_count = conn.execute(check_query, {"company_id": company_id}).scalar()
                added = new_count - existing_count
                
                print(f"\n✅ BAŞARILI!")
                print(f"   Toplam kayıt: {new_count} (Yeni: +{added})")
                
                # Show sample data
                sample_query = text("""
                    SELECT year, quarter, "statementType", COUNT(*) as items
                    FROM financial_statements
                    WHERE "companyId" = :company_id
                    GROUP BY year, quarter, "statementType"
                    ORDER BY year DESC, quarter DESC
                    LIMIT 5
                """)
                
                print(f"\n   Son 5 dönem özeti:")
                for row in conn.execute(sample_query, {"company_id": company_id}):
                    print(f"   - {row.year}Q{row.quarter} {row[2]}: {row.items} items")
            else:
                print(f"\n❌ BAŞARISIZ!")
                print(f"   {code} için finansal veri çekilemedi")
    
    print(f"\n{'='*80}")
    print(f"Test tamamlandı: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*80}\n")

if __name__ == "__main__":
    try:
        test_xi_29k_companies()
    except KeyboardInterrupt:
        print("\n\n⚠️  Test kullanıcı tarafından durduruldu")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ HATA: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
