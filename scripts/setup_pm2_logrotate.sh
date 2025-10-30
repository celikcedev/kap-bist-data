#!/bin/bash
# Setup PM2 Log Rotation - Prevents disk from filling up
# Run this once after PM2 installation

set -e  # Exit on error

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${YELLOW}🔄 Setting up PM2 Log Rotation...${NC}"

# Check if PM2 is installed
if ! command -v pm2 &> /dev/null; then
    echo -e "${RED}❌ Error: PM2 is not installed${NC}"
    echo -e "${YELLOW}Install PM2 first: sudo npm install -g pm2${NC}"
    exit 1
fi

# Install pm2-logrotate module
echo -e "${YELLOW}📦 Installing pm2-logrotate module...${NC}"
pm2 install pm2-logrotate

# Wait for installation
sleep 3

# Configure pm2-logrotate
echo -e "${YELLOW}⚙️  Configuring log rotation settings...${NC}"

# Max size per log file: 10MB
pm2 set pm2-logrotate:max_size 10M
echo -e "${GREEN}✅ Max log size: 10MB${NC}"

# Keep last 7 rotated files
pm2 set pm2-logrotate:retain 7
echo -e "${GREEN}✅ Retain: 7 files${NC}"

# Compress rotated logs
pm2 set pm2-logrotate:compress true
echo -e "${GREEN}✅ Compression: enabled${NC}"

# Date format for rotated files
pm2 set pm2-logrotate:dateFormat 'YYYY-MM-DD_HH-mm-ss'
echo -e "${GREEN}✅ Date format: YYYY-MM-DD_HH-mm-ss${NC}"

# Rotate even if empty
pm2 set pm2-logrotate:rotateModule true
echo -e "${GREEN}✅ Rotate PM2 module logs: enabled${NC}"

# Worker interval (check every 30 seconds)
pm2 set pm2-logrotate:workerInterval 30
echo -e "${GREEN}✅ Check interval: 30 seconds${NC}"

# Verify configuration
echo -e "${YELLOW}📋 Current pm2-logrotate configuration:${NC}"
pm2 conf pm2-logrotate

echo -e "${GREEN}✨ PM2 Log Rotation setup complete!${NC}"
echo -e "${YELLOW}📊 Logs will be rotated when they reach 10MB, keeping last 7 files (compressed)${NC}"
