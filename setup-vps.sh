#!/bin/bash
# VPS Kurulum Script'i - BIST Data Pipeline
# Bu script VPS sunucusunda tüm gerekli paketleri otomatik kurar

set -e  # Hata durumunda dur

echo "🚀 BIST Data Pipeline VPS Kurulumu Başlıyor..."

# Renk kodları
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# 1. Sistem Güncellemesi
echo -e "${YELLOW}📦 Sistem paketleri güncelleniyor...${NC}"
sudo apt-get update
sudo apt-get upgrade -y

# 2. Node.js ve npm (Zaten kurulu olmalı, kontrol edelim)
echo -e "${YELLOW}🟢 Node.js versiyonu kontrol ediliyor...${NC}"
if ! command -v node &> /dev/null; then
    echo -e "${RED}Node.js bulunamadı! Lütfen önce Node.js kurun.${NC}"
    exit 1
fi
echo -e "${GREEN}✅ Node.js $(node -v) kurulu${NC}"

# 3. PostgreSQL (Zaten kurulu olmalı)
echo -e "${YELLOW}🐘 PostgreSQL kontrol ediliyor...${NC}"
if ! command -v psql &> /dev/null; then
    echo -e "${RED}PostgreSQL bulunamadı! Lütfen önce PostgreSQL kurun.${NC}"
    exit 1
fi
echo -e "${GREEN}✅ PostgreSQL $(psql --version | awk '{print $3}') kurulu${NC}"

# 4. Python 3 (Financial scraper için)
echo -e "${YELLOW}🐍 Python 3 kontrol ediliyor...${NC}"
if ! command -v python3 &> /dev/null; then
    echo -e "${YELLOW}Python 3 kuruluyor...${NC}"
    sudo apt-get install -y python3 python3-pip python3-venv
fi
echo -e "${GREEN}✅ Python $(python3 --version | awk '{print $2}') kurulu${NC}"

# 5. Playwright Browser Dependencies
echo -e "${YELLOW}🎭 Playwright browser dependencies kuruluyor...${NC}"
sudo apt-get install -y \
  libatk1.0-0 \
  libatk-bridge2.0-0 \
  libcups2 \
  libxkbcommon0 \
  libatspi2.0-0 \
  libxcomposite1 \
  libxdamage1 \
  libxfixes3 \
  libxrandr2 \
  libgbm1 \
  libcairo2 \
  libpango-1.0-0 \
  libasound2 \
  libdbus-glib-1-2 \
  libxt6 \
  libxshmfence1 \
  libnss3 \
  libnspr4 \
  libxss1 \
  fonts-liberation \
  libappindicator3-1 \
  xdg-utils

echo -e "${GREEN}✅ Playwright dependencies kuruldu${NC}"

# 6. Git (Zaten kurulu olmalı)
echo -e "${YELLOW}📝 Git kontrol ediliyor...${NC}"
if ! command -v git &> /dev/null; then
    sudo apt-get install -y git
fi
echo -e "${GREEN}✅ Git $(git --version | awk '{print $3}') kurulu${NC}"

# 7. PM2 (Global, zaten kurulu olmalı)
echo -e "${YELLOW}⚙️  PM2 kontrol ediliyor...${NC}"
if ! command -v pm2 &> /dev/null; then
    echo -e "${YELLOW}PM2 kuruluyor...${NC}"
    sudo npm install -g pm2
fi
echo -e "${GREEN}✅ PM2 $(pm2 -v) kurulu${NC}"

# 8. Nginx (Zaten kurulu olmalı)
echo -e "${YELLOW}🌐 Nginx kontrol ediliyor...${NC}"
if ! command -v nginx &> /dev/null; then
    echo -e "${YELLOW}Nginx kuruluyor...${NC}"
    sudo apt-get install -y nginx
fi
echo -e "${GREEN}✅ Nginx $(nginx -v 2>&1 | awk '{print $3}') kurulu${NC}"

echo ""
echo -e "${GREEN}═══════════════════════════════════════════════${NC}"
echo -e "${GREEN}✅ VPS Sistem Kurulumu Tamamlandı!${NC}"
echo -e "${GREEN}═══════════════════════════════════════════════${NC}"
echo ""
echo -e "${YELLOW}📋 Sıradaki Adımlar:${NC}"
echo "1. Git clone: git clone https://github.com/celikcedev/kap-bist-data.git"
echo "2. Dizine gir: cd kap-bist-data"
echo "3. Node paketleri: npm install"
echo "4. Python venv: python3 -m venv .venv && source .venv/bin/activate"
echo "5. Python paketleri: pip install -r requirements.txt"
echo "6. Prisma migrate: npx prisma db push"
echo "7. PM2 başlat: pm2 start ecosystem.config.cjs && pm2 save"
echo ""
