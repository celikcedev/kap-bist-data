#!/usr/bin/env python3
"""Monitor financial scraper V2 progress"""

import os
import time
from datetime import datetime
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
db_url = DATABASE_URL.replace("postgresql://", "postgresql+psycopg2://").split("?")[0]
engine = create_engine(db_url)

# Get log file
log_file = "/Users/ademcelik/Desktop/kap_bist_data/logs/financial_scraper_v2_full_20251016_233820.log"

def get_progress():
    """Parse log file for progress"""
    try:
        with open(log_file, 'r') as f:
            lines = f.readlines()
        
        # Find last processed company
        for line in reversed(lines):
            if "Processing:" in line and "[" in line:
                # Extract [X/592]
                start = line.find("[") + 1
                end = line.find("]")
                progress = line[start:end]
                current, total = progress.split("/")
                return int(current), int(total)
        
        return 0, 592
    except:
        return 0, 592

def get_db_stats():
    """Get database statistics"""
    with engine.connect() as conn:
        # Total records
        total = conn.execute(text(
            "SELECT COUNT(*) FROM financial_statements"
        )).scalar()
        
        # Companies with data
        companies = conn.execute(text(
            "SELECT COUNT(DISTINCT \"companyId\") FROM financial_statements"
        )).scalar()
        
        # Previously missing 16 companies
        missing_16 = [
            "CRDFA", "GARFA", "LIDFA", "ULUFA",  # Faktoring
            "ISFIN", "QNBFK", "SEKFK", "VAKFN",  # Leasing
            "BRKVY", "GLCVY", "SMRVA",           # Asset Mgmt
            "DOCO", "MARMR", "ISKUR", "KTLEV"    # Other
        ]
        
        found_missing = conn.execute(text("""
            SELECT c.code 
            FROM companies c
            JOIN financial_statements fs ON c.id = fs."companyId"
            WHERE c.code = ANY(:codes)
            GROUP BY c.code
        """), {"codes": missing_16}).fetchall()
        
        found_count = len(found_missing)
        found_symbols = [row[0] for row in found_missing]
        
        return total, companies, found_count, found_symbols

# Monitor
print("=" * 80)
print("📊 FINANCIAL SCRAPER V2 - LIVE MONITOR")
print("=" * 80)
print()

while True:
    current, total = get_progress()
    db_total, db_companies, found_16, found_symbols = get_db_stats()
    
    percent = (current / total * 100) if total > 0 else 0
    
    print(f"\r⏳ Progress: [{current}/{total}] {percent:.1f}% | ", end="")
    print(f"DB: {db_total:,} records, {db_companies} companies | ", end="")
    print(f"Missing 16: {found_16}/16 found    ", end="", flush=True)
    
    if current >= total:
        print("\n\n✅ SCRAPING COMPLETED!")
        print(f"\nFinal Statistics:")
        print(f"  - Total Records: {db_total:,}")
        print(f"  - Companies: {db_companies}/592")
        print(f"  - Previously Missing: {found_16}/16 recovered")
        if found_symbols:
            print(f"\n  Found: {', '.join(sorted(found_symbols))}")
        break
    
    time.sleep(10)  # Update every 10 seconds

print("\n" + "=" * 80)
