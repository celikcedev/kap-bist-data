#!/bin/bash

# KAP BIST Data Scraper - Python Ortamı Kurulum Scripti
# Gelecekte finansal tablo kazıma için Python ortamını hazırlar

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "╔════════════════════════════════════════════════════════════╗"
echo "║    PYTHON GELİŞTİRME ORTAMI KURULUMU                       ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo ""
echo "📍 Proje Dizini: $PROJECT_DIR"
echo ""

# Python 3.11 kontrolü
PYTHON_311="/opt/homebrew/opt/python@3.11/bin/python3.11"

if [ -f "$PYTHON_311" ]; then
    PYTHON_BIN="$PYTHON_311"
    echo "✅ Python 3.11 bulundu: $PYTHON_BIN"
elif command -v python3.11 &> /dev/null; then
    PYTHON_BIN="python3.11"
    echo "✅ Python 3.11 bulundu (PATH'te)"
elif command -v python3 &> /dev/null; then
    PYTHON_BIN="python3"
    echo "⚠️  Python 3.11 bulunamadı, sistem Python kullanılıyor"
else
    echo "❌ Python 3 bulunamadı. Lütfen Python 3.11+ yükleyin."
    exit 1
fi

PYTHON_VERSION=$($PYTHON_BIN --version)
echo "📍 Kullanılacak versiyon: $PYTHON_VERSION"
echo ""

# İdeal versiyon kontrolü
if [[ "$PYTHON_VERSION" == *"3.11"* ]]; then
    echo "✅ Python 3.11 - Trading uygulaması için ideal LTS sürüm"
elif [[ "$PYTHON_VERSION" == *"3.12"* ]]; then
    echo "✅ Python 3.12 - Yeni sürüm, stabil"
elif [[ "$PYTHON_VERSION" == *"3.10"* ]]; then
    echo "⚠️  Python 3.10 - Eski ama çalışır"
else
    echo "⚠️  $PYTHON_VERSION - Python 3.11 önerilir"
fi
echo ""

# Virtual environment oluştur (.venv standart dizin)
echo "🔧 Virtual environment oluşturuluyor (.venv)..."
$PYTHON_BIN -m venv .venv

if [ $? -ne 0 ]; then
    echo "❌ Virtual environment oluşturulamadı."
    exit 1
fi

echo "✅ Virtual environment oluşturuldu: $PROJECT_DIR/.venv"
echo ""

# Virtual environment'ı aktifleştir
echo "🔧 Bağımlılıklar yükleniyor..."
source .venv/bin/activate

# Pip'i güncelle
pip install --upgrade pip

# Requirements'ı yükle
pip install -r requirements.txt

if [ $? -eq 0 ]; then
    echo ""
    echo "✅ Tüm bağımlılıklar başarıyla yüklendi!"
    echo ""
    echo "📝 Kullanım:"
    echo "   1. Virtual environment'ı aktifleştirin:"
    echo "      source .venv/bin/activate"
    echo ""
    echo "   2. Python scriptlerinizi çalıştırın:"
    echo "      python scripts/financial_scraper.py  (gelecek feature)"
    echo ""
    echo "   3. Çıkmak için:"
    echo "      deactivate"
    echo ""
else
    echo "❌ Bağımlılıklar yüklenirken hata oluştu."
    exit 1
fi

