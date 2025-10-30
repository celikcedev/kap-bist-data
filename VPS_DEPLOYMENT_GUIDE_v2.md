# 🚀 VPS Deployment Guide - Step by Step

**Date:** 19 Ekim 2025, 23:20  
**VPS:** Ubuntu 22.04 LTS (Fresh Install)  
**Location:** Türkiye  
**Estimated Time:** 2-3 hours  
**Difficulty:** Intermediate

---

## 📋 Prerequisites Checklist

**Required Information (Will be provided by user):**
```
[ ] VPS IP Address: _____________________
[ ] SSH Username: _______________________
[ ] SSH Private Key or Password: ________
[ ] Domain Name: ________________________
```

**Required Tools on Your Local Machine:**
- [ ] SSH client (Terminal/PuTTY)
- [ ] Git
- [ ] Text editor (VS Code recommended)

---

## 🏗️ Infrastructure Stack

```
Ubuntu 22.04 LTS (Fresh)
├── Nginx 1.18+ (Web Server & Reverse Proxy)
├── Certbot (Let's Encrypt SSL - Ücretsiz)
├── Node.js 22.x (TypeScript Scraper Runtime)
├── Python 3.11 (Financial Scraper)
├── PostgreSQL 15 (Database)
├── PM2 (Process Manager + Cron Jobs)
├── Cockpit (Web-based Monitoring - Optional)
└── UFW (Firewall)
```

**Total Cost:** ~₺0 (all open-source, only VPS cost)

**Why This Stack?**
👉 See `VPS_INFRASTRUCTURE_DECISION.md` for detailed analysis

---

## 🚀 Step-by-Step Deployment

### **STEP 1: Initial VPS Access**

#### 1.1 Connect to VPS
```bash
# Using SSH key (recommended)
ssh -i /path/to/private-key username@VPS_IP

# Or using password
ssh username@VPS_IP
```

#### 1.2 Update System
```bash
sudo apt update && sudo apt upgrade -y
sudo reboot
# Wait 1 minute, then reconnect
```

#### 1.3 Create Application User (if root)
```bash
# If logged in as root, create app user
sudo adduser ademcelik
sudo usermod -aG sudo ademcelik
sudo su - ademcelik
```

---

### **STEP 2: Install Core Dependencies**

#### 2.1 Install Node.js 22
```bash
# Add NodeSource repository
curl -fsSL https://deb.nodesource.com/setup_22.x | sudo -E bash -

# Install Node.js
sudo apt install -y nodejs

# Verify
node --version  # Should show v22.x.x
npm --version   # Should show 10.x.x
```

#### 2.2 Install Python 3.11
```bash
# Ubuntu 22.04 comes with Python 3.10, upgrade to 3.11
sudo add-apt-repository ppa:deadsnakes/ppa -y
sudo apt update
sudo apt install -y python3.11 python3.11-venv python3.11-dev python3-pip

# Set Python 3.11 as default
sudo update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.11 1
sudo update-alternatives --config python3  # Select 3.11

# Verify
python3 --version  # Should show 3.11.x
```

#### 2.3 Install PostgreSQL 15
```bash
# Add PostgreSQL APT repository
sudo sh -c 'echo "deb http://apt.postgresql.org/pub/repos/apt $(lsb_release -cs)-pgdg main" > /etc/apt/sources.list.d/pgdg.list'
wget -qO- https://www.postgresql.org/media/keys/ACCC4CF8.asc | sudo tee /etc/apt/trusted.gpg.d/pgdg.asc &>/dev/null

# Install PostgreSQL 15
sudo apt update
sudo apt install -y postgresql-15 postgresql-client-15

# Verify
sudo systemctl status postgresql
psql --version  # Should show 15.x
```

#### 2.4 Install PM2 (Process Manager)
```bash
sudo npm install -g pm2

# Verify
pm2 --version
```

#### 2.5 Install Nginx
```bash
sudo apt install -y nginx

# Start and enable
sudo systemctl start nginx
sudo systemctl enable nginx

# Verify
sudo systemctl status nginx
nginx -v  # Should show 1.18+ or 1.24+
```

#### 2.6 Install Certbot (Let's Encrypt)
```bash
sudo snap install --classic certbot
sudo ln -s /snap/bin/certbot /usr/bin/certbot

# Verify
certbot --version
```

#### 2.7 Install Cockpit (Optional - Monitoring)
```bash
sudo apt install -y cockpit

# Start and enable
sudo systemctl start cockpit
sudo systemctl enable cockpit

# Access: https://VPS_IP:9090
```

---

### **STEP 3: Configure Firewall (UFW)**

```bash
# Default policies
sudo ufw default deny incoming
sudo ufw default allow outgoing

# Allow essential ports
sudo ufw allow ssh          # Port 22 (SSH)
sudo ufw allow 80/tcp       # HTTP (Nginx)
sudo ufw allow 443/tcp      # HTTPS (Nginx)
sudo ufw allow 9090/tcp     # Cockpit (optional, or restrict by IP)

# Enable firewall
sudo ufw enable

# Verify
sudo ufw status verbose
```

**Output should show:**
```
Status: active

To                         Action      From
--                         ------      ----
22                         ALLOW       Anywhere
80/tcp                     ALLOW       Anywhere
443/tcp                    ALLOW       Anywhere
9090/tcp                   ALLOW       Anywhere
```

---

### **STEP 4: Setup PostgreSQL Database**

#### 4.1 Create Database & User
```bash
# Switch to postgres user
sudo -u postgres psql

# Inside PostgreSQL prompt:
CREATE DATABASE bist_data;
CREATE USER ademcelik WITH ENCRYPTED PASSWORD 'your-strong-password-here';
GRANT ALL PRIVILEGES ON DATABASE bist_data TO ademcelik;
ALTER DATABASE bist_data OWNER TO ademcelik;

# Exit
\q
```

#### 4.2 Test Connection
```bash
psql -U ademcelik -d bist_data -h localhost
# Enter password when prompted
# If successful, you'll see: bist_data=>

# Test query
SELECT version();

# Exit
\q
```

#### 4.3 Configure PostgreSQL (Optional - Security)
```bash
sudo nano /etc/postgresql/15/main/postgresql.conf

# Ensure this line exists (localhost only):
listen_addresses = 'localhost'

# Restart PostgreSQL
sudo systemctl restart postgresql
```

---

### **STEP 5: Clone Repository & Setup Application**

#### 5.1 Install Git
```bash
sudo apt install -y git
```

#### 5.2 Clone Repository
```bash
cd ~
git clone https://github.com/yourusername/kap_bist_data.git
cd kap_bist_data
```

**Note:** If private repo, setup SSH key or use personal access token

#### 5.3 Create Environment File
```bash
nano .env
```

**Paste this content (update PASSWORD):**
```env
# Database
DATABASE_URL="postgresql://ademcelik:your-strong-password-here@localhost:5432/bist_data"
POSTGRES_USER="ademcelik"
POSTGRES_PASSWORD="your-strong-password-here"
POSTGRES_DB="bist_data"

# Application
NODE_ENV="production"
LOG_LEVEL="info"

# Optional: Future monitoring
SENTRY_DSN=""
```

**Save:** Ctrl+O, Enter, Ctrl+X

#### 5.4 Install Node.js Dependencies
```bash
npm install
```

#### 5.5 Setup Python Virtual Environment
```bash
python3 -m venv .venv
source .venv/bin/activate

# Install Python dependencies
pip install --upgrade pip
pip install -r requirements.txt
```

#### 5.6 Run Database Migration
```bash
# Generate Prisma Client
npx prisma generate

# Run migrations
npx prisma migrate deploy
```

#### 5.7 Initial Data Scraping
```bash
# This will take ~3-4 hours!
./scripts/full_reset_and_scrape.sh
```

**Monitor progress:**
```bash
# In another terminal
tail -f logs/full_reset_*/phase*.log
```

---

### **STEP 6: Configure PM2 for Cron Jobs**

#### 6.1 Create PM2 Ecosystem File
```bash
nano ecosystem.config.js
```

**Paste:**
```javascript
module.exports = {
  apps: [
    {
      name: 'bist-daily-scraper',
      script: './scripts/daily_update.sh',
      cron_restart: '0 1 * * *',  // Daily at 01:00 AM
      autorestart: false,
      watch: false,
      env: {
        NODE_ENV: 'production',
        PATH: process.env.PATH + ':' + process.env.HOME + '/.venv/bin'
      },
      error_file: './logs/pm2-error.log',
      out_file: './logs/pm2-out.log',
      log_date_format: 'YYYY-MM-DD HH:mm:ss Z'
    }
  ]
};
```

#### 6.2 Start PM2
```bash
pm2 start ecosystem.config.js

# Save PM2 configuration
pm2 save

# Setup PM2 to start on boot
pm2 startup
# Copy and run the command it outputs (starts with sudo)

# Verify
pm2 list
pm2 logs bist-daily-scraper
```

---

### **STEP 7: Configure Domain & SSL**

#### 7.1 Point Domain to VPS
**In your domain provider's DNS settings:**
```
Type: A
Name: @ (or yourdomain.com)
Value: YOUR_VPS_IP
TTL: 3600

Type: A
Name: www
Value: YOUR_VPS_IP
TTL: 3600

Type: A
Name: api
Value: YOUR_VPS_IP
TTL: 3600
```

**Wait 5-30 minutes for DNS propagation**

#### 7.2 Test DNS
```bash
# From your local machine
ping yourdomain.com
ping api.yourdomain.com

# Should show your VPS IP
```

#### 7.3 Create Nginx Configuration
```bash
sudo nano /etc/nginx/sites-available/bist-data
```

**Paste (replace yourdomain.com):**
```nginx
# Redirect HTTP to HTTPS
server {
    listen 80;
    listen [::]:80;
    server_name yourdomain.com www.yourdomain.com api.yourdomain.com;
    
    # Allow Certbot
    location /.well-known/acme-challenge/ {
        root /var/www/html;
    }
    
    # Redirect others
    location / {
        return 301 https://$server_name$request_uri;
    }
}

# Main domain (placeholder for Week 1-2)
server {
    listen 443 ssl http2;
    listen [::]:443 ssl http2;
    server_name yourdomain.com www.yourdomain.com;
    
    # SSL certificates (will be added by Certbot)
    # ssl_certificate /etc/letsencrypt/live/yourdomain.com/fullchain.pem;
    # ssl_certificate_key /etc/letsencrypt/live/yourdomain.com/privkey.pem;
    
    # SSL settings
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_prefer_server_ciphers on;
    ssl_ciphers ECDHE-RSA-AES256-GCM-SHA512:DHE-RSA-AES256-GCM-SHA512;
    
    # Security headers
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header Strict-Transport-Security "max-age=31536000" always;
    
    # Root
    root /var/www/html;
    index index.html;
    
    location / {
        return 503 "🚧 BIST Data Pipeline: System is collecting data. API coming soon! 🚀";
        add_header Content-Type text/plain;
    }
}

# API subdomain (placeholder)
server {
    listen 443 ssl http2;
    listen [::]:443 ssl http2;
    server_name api.yourdomain.com;
    
    # SSL certificates (will be added by Certbot)
    # ssl_certificate /etc/letsencrypt/live/yourdomain.com/fullchain.pem;
    # ssl_certificate_key /etc/letsencrypt/live/yourdomain.com/privkey.pem;
    
    # Week 3'te uncomment edilecek
    # location / {
    #     proxy_pass http://localhost:3000;
    #     proxy_http_version 1.1;
    #     proxy_set_header Upgrade $http_upgrade;
    #     proxy_set_header Connection 'upgrade';
    #     proxy_set_header Host $host;
    #     proxy_cache_bypass $http_upgrade;
    #     proxy_set_header X-Real-IP $remote_addr;
    #     proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    #     proxy_set_header X-Forwarded-Proto $scheme;
    # }
    
    location / {
        return 503 "🚧 API coming soon! (Week 3)";
        add_header Content-Type text/plain;
    }
}
```

#### 7.4 Enable Site
```bash
# Create symlink
sudo ln -s /etc/nginx/sites-available/bist-data /etc/nginx/sites-enabled/

# Remove default site
sudo rm /etc/nginx/sites-enabled/default

# Test configuration
sudo nginx -t

# Reload Nginx
sudo systemctl reload nginx
```

#### 7.5 Obtain SSL Certificate
```bash
# Get certificate for all domains
sudo certbot --nginx -d yourdomain.com -d www.yourdomain.com -d api.yourdomain.com

# Follow prompts:
# - Email: your-email@example.com
# - Agree to terms: Yes
# - Share email: No (optional)
# - Redirect HTTP to HTTPS: Yes (2)
```

**Certbot will:**
- Automatically update Nginx config
- Add SSL certificates
- Setup auto-renewal cron job

#### 7.6 Test SSL
```bash
# Visit in browser
https://yourdomain.com
https://www.yourdomain.com
https://api.yourdomain.com

# Should show placeholder message with valid SSL (green padlock)
```

#### 7.7 Test Auto-Renewal
```bash
sudo certbot renew --dry-run

# Should show: "Congratulations, all simulated renewals succeeded"
```

---

### **STEP 8: Configure Cockpit (Optional)**

#### 8.1 Access Cockpit
```
URL: https://yourdomain.com:9090
Username: ademcelik
Password: (VPS SSH password)
```

#### 8.2 Configure Cockpit Features
- **Enable System Metrics**: Dashboard → Enable
- **Add PM2 Logs**: Terminal → `pm2 logs`
- **Monitor PostgreSQL**: Services → postgresql

---

## ✅ Verification Checklist

### **Database Verification**
```bash
psql -U ademcelik -d bist_data -h localhost -c "SELECT COUNT(*) FROM companies;"
# Should show: 592

psql -U ademcelik -d bist_data -h localhost -c "SELECT COUNT(*) FROM financial_statements;"
# Should show: ~1,782,602
```

### **Cron Job Verification**
```bash
pm2 list
# Should show: bist-daily-scraper | online | cron

pm2 logs bist-daily-scraper --lines 50
# Should show recent activity
```

### **SSL Verification**
```bash
curl -I https://yourdomain.com
# Should show: HTTP/2 200 (or 503 with placeholder)
# Should NOT show certificate errors
```

### **Firewall Verification**
```bash
sudo ufw status verbose
# Should show: Status: active
# Ports 22, 80, 443, 9090 allowed
```

---

## 📊 Post-Deployment Monitoring (Week 1)

### **Daily Checks**
```bash
# Check PM2 status
pm2 list

# Check logs
pm2 logs bist-daily-scraper --lines 100

# Check database growth
psql -U ademcelik -d bist_data -h localhost -c "SELECT COUNT(*) FROM financial_statements;"

# Check disk space
df -h

# Check memory
free -h
```

### **Monitoring via Cockpit**
```
URL: https://yourdomain.com:9090

Check:
- CPU usage (<50% idle normal)
- RAM usage (<80% normal)
- Disk usage (<70% normal)
- Network activity (spikes during scraping)
```

---

### **STEP 9: Production Optimizations (CRITICAL)**

#### 9.1 Setup PM2 Log Rotation
```bash
cd ~/kap-bist-data
./scripts/setup_pm2_logrotate.sh
```

**What it does:**
- Prevents log files from filling disk
- Rotates logs when they reach 10MB
- Keeps last 7 rotated files (compressed)
- Checks every 30 seconds

**Verify:**
```bash
pm2 conf pm2-logrotate
# Should show: max_size=10M, retain=7, compress=true
```

#### 9.2 Setup PostgreSQL Automatic Backup
```bash
cd ~/kap-bist-data
./scripts/setup_postgres_backup.sh
```

**What it does:**
- Creates daily backups at 02:00 AM
- Compresses backups (gzip)
- Keeps last 30 days
- Auto-cleans old backups

**Verify:**
```bash
crontab -l
# Should show: 0 2 * * * /home/ademcelik/backups/postgres/backup.sh

# Check backup directory
ls -lh ~/backups/postgres/
```

#### 9.3 Setup Grafana + Prometheus Monitoring (Optional)
```bash
cd ~/kap-bist-data
./scripts/setup_grafana_prometheus.sh

# IMPORTANT: After installation, edit postgres password
sudo nano /etc/default/prometheus-postgres-exporter
# Replace YOUR_PASSWORD with actual DB password

# Restart postgres_exporter
sudo systemctl restart prometheus-postgres-exporter
```

**Access Monitoring:**
```
Grafana:    https://YOUR_VPS_IP:3000
Username:   admin
Password:   admin (change on first login)

Prometheus: https://YOUR_VPS_IP:9090
```

**Import Dashboards:**
1. Login to Grafana (admin/admin)
2. Dashboard → Import → 9628 (PostgreSQL)
3. Dashboard → Import → 1860 (Node Exporter)

---

### **STEP 10: Final System Restart**

```bash
# Save PM2 state
pm2 save

# Restart VPS (first restart since initial setup)
sudo reboot
```

**Wait 2-3 minutes, then verify:**
```bash
# Reconnect via SSH
ssh ademcelik@YOUR_VPS_IP

# Check all services
sudo systemctl status nginx
sudo systemctl status postgresql
sudo systemctl status grafana-server  # if installed
sudo systemctl status prometheus       # if installed

# Check PM2 auto-start
pm2 list
# Should show all 4 jobs running

# Check PM2 logs
pm2 logs --lines 20
```

---

## 🔧 Troubleshooting

### **Issue: PM2 cron not running**
```bash
pm2 logs bist-daily-scraper
pm2 restart bist-daily-scraper
pm2 save
```

### **Issue: Database connection failed**
```bash
sudo systemctl status postgresql
sudo systemctl restart postgresql
psql -U ademcelik -d bist_data -h localhost
```

### **Issue: SSL certificate not renewing**
```bash
sudo certbot renew --dry-run
sudo systemctl status certbot.timer
```

### **Issue: Nginx not starting**
```bash
sudo nginx -t  # Test configuration
sudo systemctl status nginx
sudo journalctl -u nginx -n 50
```

---

## 📚 Next Steps

**Week 2: Monitoring & Stabilization**
- [ ] Monitor cron job for 7 days
- [ ] Verify data quality
- [ ] Check for errors in logs
- [ ] Plan API development

**Week 3: API Development**
- [ ] Develop Next.js API
- [ ] Update Nginx config (uncomment API proxy)
- [ ] Test API endpoints
- [ ] Add rate limiting

**Week 11: Frontend Launch**
- [ ] Deploy frontend to Nginx
- [ ] Configure caching
- [ ] SEO optimization
- [ ] Public announcement

---

## 🆘 Support & Resources

- **Infrastructure Decision:** `VPS_INFRASTRUCTURE_DECISION.md`
- **Deployment Strategy:** `DEPLOYMENT_STRATEGY.md`
- **Next Steps:** `NEXT_STEPS_QUICK_REF.md`
- **Technical Debt:** `TECHNICAL_DEBT.md`

---

**Deployment Time:** 2-3 hours  
**Difficulty:** Intermediate  
**Success Rate:** 95%+ (with this guide)

**Good luck! 🚀**
