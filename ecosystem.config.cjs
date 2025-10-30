module.exports = {
  apps: [
    {
      name: 'bist-daily-scraper',
      script: 'npm',
      args: 'run orchestrate',
      cron_restart: '0 1 * * *', // 01:00 her gün (TypeScript scraper: companies, indices, markets)
      autorestart: false,
      max_memory_restart: '1500M',
      env: {
        NODE_ENV: 'production',
        NODE_OPTIONS: '--max-old-space-size=1280'
      },
      error_file: './logs/pm2-scraper-error.log',
      out_file: './logs/pm2-scraper-out.log',
      time: true
    },
    {
      name: 'bist-financial-quarter',
      script: 'bash',
      args: '-c "source .venv/bin/activate && python scripts/financial_scraper_v2.py"',
      cron_restart: '0 4 1-20 2,5,8,11 *', // Çeyrek aylar (Şub, May, Ağu, Kas): 1-20 arası her gün 04:00
      autorestart: false,
      max_memory_restart: '1000M',
      env: {
        PYTHONUNBUFFERED: '1'
      },
      error_file: './logs/pm2-financial-error.log',
      out_file: './logs/pm2-financial-out.log',
      time: true
    },
    {
      name: 'bist-financial-normal',
      script: 'bash',
      args: '-c "source .venv/bin/activate && python scripts/financial_scraper_v2.py"',
      cron_restart: '0 4 * 1,3,4,6,7,9,10,12 3,6', // Normal aylar: Çarşamba (3) + Cumartesi (6) 04:00
      autorestart: false,
      max_memory_restart: '1000M',
      env: {
        PYTHONUNBUFFERED: '1'
      },
      error_file: './logs/pm2-financial-normal-error.log',
      out_file: './logs/pm2-financial-normal-out.log',
      time: true
    },
    {
      name: 'bist-financial-groups-updater',
      script: 'bash',
      args: '-c "source .venv/bin/activate && python scripts/scrape_financial_groups.py"',
      cron_restart: '0 3 1 * *', // Her ayın 1'i, 03:00 (Ayda bir financial groups güncelleme)
      autorestart: false,
      max_memory_restart: '500M',
      env: {
        PYTHONUNBUFFERED: '1'
      },
      error_file: './logs/pm2-financial-groups-error.log',
      out_file: './logs/pm2-financial-groups-out.log',
      time: true
    }
  ]
};
