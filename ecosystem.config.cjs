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
      name: 'bist-financial-scraper',
      script: 'bash',
      args: '-c "source .venv/bin/activate && python scripts/financial_scraper_v2.py"',
      cron_restart: '0 4 * * *', // 04:00 her gün (Python financial scraper)
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
