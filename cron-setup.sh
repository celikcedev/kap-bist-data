#!/bin/bash

# KAP BIST Data Scraper - Cron Job Setup Script
# Bu script otomatik zamanlı çalıştırma için crontab ayarlarını yapılandırır

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_DIR="$PROJECT_DIR/logs/cron"

# Log dizinini oluştur
mkdir -p "$LOG_DIR"

echo "╔════════════════════════════════════════════════════════════╗"
echo "║    KAP BIST DATA SCRAPER - CRON JOB KURULUMU              ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo ""
echo "Proje Dizini: $PROJECT_DIR"
echo "Log Dizini: $LOG_DIR"
echo ""

# Mevcut crontab'ı yedekle
crontab -l > "$PROJECT_DIR/crontab_backup_$(date +%Y%m%d_%H%M%S).txt" 2>/dev/null

echo "🔧 Zamanlanmış görev eklenecek:"
echo ""
echo "1. ANA KAZIMA (npm run scrape:all)"
echo "   📅 Periyot: Haftalık (Her Pazar, 02:00)"
echo "   📝 Açıklama: Tüm şirketleri kazır, yenileri ekle, mevcutları güncelle"
echo "   ⏱️  Süre: ~51 dakika (710+ şirket)"
echo ""

# Crontab girişi
# Ana kazıma: Her Pazar 02:00 (~51 dakika sürer)
CRON_ENTRY_ALL="0 2 * * 0 cd $PROJECT_DIR && /usr/local/bin/npm run scrape:all >> $LOG_DIR/scrape-all.log 2>&1"

# Mevcut crontab'a ekle
(crontab -l 2>/dev/null; echo ""; echo "# KAP BIST Data Scraper - Haftalık Otomatik Kazıma"; echo "$CRON_ENTRY_ALL") | crontab -

echo "✅ Cron job'lar başarıyla eklendi!"
echo ""
echo "🔍 Kurulumu doğrulamak için:"
echo "   crontab -l"
echo ""
echo "📊 Log dosyalarını görüntülemek için:"
echo "   tail -f $LOG_DIR/scrape-all.log"
echo ""
echo "⚠️  NOT: İlk çalıştırma zamanları:"
echo "   • Ana Kazıma: Sonraki Pazar günü 02:00"
echo ""
echo "🛑 Cron job'ları kaldırmak için:"
echo "   crontab -e  (ve ilgili satırları silin)"
echo ""

