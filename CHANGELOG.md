# Changelog - BIST Data Pipeline

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased]

### Technical Debt
- `AsyncFinancialGroupScraper` class (250+ lines) production'da kullanılmıyor
- "Belki lazım olur" mantığı ile şimdilik bırakıldı
- VPS deployment sonrası karar verilecek
- Detay: `development-docs/TECHNICAL_DEBT.md`

---

## [1.0.0] - 2025-10-19 ✅ VALIDATED

### 🎉 Major Release - Production Ready

**🔬 Validation Test Results (19:10 - 22:38, 3.5 hours):**
- ✅ **1,782,602** financial statements (676 more than first test)
- ✅ **590/592** companies with financial groups (ISKUR, MARMR: None expected)
- ✅ **Zero duplicates** across all tables
- ✅ **Zero orphaned** foreign key records
- ✅ **Query performance**: 1.97ms (target: <100ms) ⚡️
- ✅ **All SQL queries** executed without syntax errors
- ✅ **Upsert mechanism** validated (0 duplicates after re-scraping)

#### Added
- ✅ Full data scraping: 1,781,926 financial statements
- ✅ 592 companies metadata (590 with financial data)
- ✅ 6 years coverage (2020-2025)
- ✅ Financial group mapping (XI_29, UFRS_K, etc.)
- ✅ Complete end-to-end test suite (8 phases)
- ✅ Upsert mechanism validation
- ✅ Production readiness validation
- ✅ Technical debt documentation

#### Fixed
- ✅ **Bug #1**: Async financial group scraper database save (line 364-402)
- ✅ **Bug #2**: Tradable filter removed - all 592 companies processed (line 48-72)
- ✅ **Bug #3**: SQL syntax errors in validation scripts (ORDER BY table → table_name)
- ✅ **Bug #4**: Duplicate class names (AsyncFinancialGroupScraper rename)
- ✅ **Bug #5**: Phase 6 import errors in test scripts

#### Changed
- 🔧 `scrape_financial_groups.py`: Tradable filter removed from `get_tradable_tickers()`
- 🔧 `full_reset_and_scrape.sh`: All SQL queries fixed for proper syntax
- 🔧 `AsyncFinancialGroupScraper`: Renamed from duplicate `FinancialGroupScraper`

#### Validated
- ✅ Zero duplicates across all tables
- ✅ Zero orphaned foreign key records
- ✅ 100% data integrity
- ✅ Query performance < 25ms (target: < 100ms)
- ✅ Upsert mechanism: 0 duplicates after re-scraping

---

## [0.9.0] - 2025-10-18

### Beta Release - Bug Discovery

#### Issues Found
- ❌ Async scraper not saving to database
- ❌ Tradable filter limiting scope to 56 companies
- ❌ Missing financial groups for 4/10 test companies
- ❌ Duplicate class definitions in scrape_financial_groups.py

#### Test Results
- Phase 1.1-1.4: Clean start (10 companies, 38,712 records)
- Phase 2.1-2.3: Upsert test successful (zero duplicates)
- Phase 3: All validation checks passed

---

## [0.8.0] - 2025-10-04

### Alpha Release - Full Rescrape

#### Added
- Financial scraper v2 with API integration
- Financial group mapping system
- Comprehensive logging system

#### Data
- 38,712 financial statements (10 test companies)
- 592 companies metadata
- 66 indices, 16 main sectors, 72 sub sectors

---

## [0.5.0] - 2025-10-01

### Initial Release - Metadata Scraping

#### Added
- Companies list scraper (TypeScript + Playwright)
- Companies detail scraper
- Indices, sectors, markets scrapers
- Prisma database schema
- PostgreSQL integration

#### Database Schema
- 14 tables created
- Foreign key relationships
- Proper indexing

---

## Release Notes

### Version 1.0.0 Highlights

**What's New:**
- 🎯 **Production Ready**: Full system tested and validated
- 📊 **Complete Data**: 1.78M financial statements, 590 companies
- 🐛 **Bug Fixes**: 5 critical bugs fixed and verified
- ✅ **Zero Errors**: No duplicates, no orphaned records
- 🚀 **Ready for VPS**: All validation checks passed

**Breaking Changes:**
- None (first production release)

**Upgrade Path:**
- Fresh installation recommended
- Run `./scripts/full_reset_and_scrape.sh` for complete setup

**Known Issues:**
- ISKUR, MARMR: No financial group data (expected)
- AsyncFinancialGroupScraper: Dead code (see TECHNICAL_DEBT.md)

**Next Steps:**
- VPS deployment
- API development
- Frontend dashboard

---

## Versioning Policy

- **MAJOR**: Breaking changes, database schema changes
- **MINOR**: New features, non-breaking changes
- **PATCH**: Bug fixes, performance improvements

## Links

- [Technical Debt](development-docs/TECHNICAL_DEBT.md)
- [Next Steps](next-steps.md)
- [Deployment Guide](development-docs/DEPLOYMENT_GUIDE.md)
- [Final Report](development-docs/FINAL-REPORT.md)

