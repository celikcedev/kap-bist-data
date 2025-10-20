#!/bin/bash
# Financial Scraping Progress Monitor

LOG_FILE=$(ls -t logs/financial_scraper_clean_start_*.log 2>/dev/null | head -1)

if [ -z "$LOG_FILE" ]; then
    echo "❌ Log dosyası bulunamadı!"
    exit 1
fi

echo "==================================================================="
echo "📊 FİNANSAL KAZIMA İLERLEME RAPORU"
echo "==================================================================="
echo ""
echo "📄 Log Dosyası: $LOG_FILE"
echo ""

# Son işlenen şirket
echo "🏢 Son İşlenen:"
tail -100 "$LOG_FILE" | grep "\[.*Processing:" | tail -1
echo ""

# Başarı/Hata sayıları
SUCCESS_COUNT=$(grep "✓ Success:" "$LOG_FILE" | wc -l | tr -d ' ')
FAILED_COUNT=$(grep "✗ Failed:" "$LOG_FILE" | wc -l | tr -d ' ')
TOTAL=$((SUCCESS_COUNT + FAILED_COUNT))

echo "📈 İstatistikler:"
echo "  ✅ Başarılı: $SUCCESS_COUNT"
echo "  ❌ Başarısız: $FAILED_COUNT"
echo "  📊 Toplam: $TOTAL / 592"
if [ $TOTAL -gt 0 ]; then
    SUCCESS_RATE=$((SUCCESS_COUNT * 100 / TOTAL))
    echo "  💯 Başarı Oranı: ${SUCCESS_RATE}%"
fi
echo ""

# Financial group dağılımı (son 50 işlemden)
echo "📋 Son İşlenen Gruplar (son 50):"
tail -200 "$LOG_FILE" | grep "Financial Group:" | tail -50 | \
    awk -F'Financial Group: ' '{print $2}' | \
    awk -F' \\(' '{print $1}' | \
    sort | uniq -c | sort -rn
echo ""

# Hata varsa göster
if [ $FAILED_COUNT -gt 0 ]; then
    echo "❌ Başarısız Şirketler:"
    grep "✗ Failed:" "$LOG_FILE" | tail -10
    echo ""
fi

# DB kayıt sayısı
echo "💾 Veritabanı Durumu:"
psql postgresql://bist:12345@localhost:5432/bist_data -t -c "SELECT COUNT(*) FROM financial_statements;" 2>/dev/null | \
    awk '{print "  📦 Toplam Kayıt: " $1}'

echo ""
echo "==================================================================="
echo "⏱️  $(date '+%Y-%m-%d %H:%M:%S')"
echo "==================================================================="
