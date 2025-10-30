#!/bin/bash
# Setup Grafana + Prometheus Monitoring Stack
# 100% Open Source, No paid features required

set -e  # Exit on error

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${YELLOW}📊 Setting up Grafana + Prometheus monitoring stack...${NC}"

# Check if running on Ubuntu/Debian
if ! command -v apt &> /dev/null; then
    echo -e "${RED}❌ Error: This script requires Ubuntu/Debian${NC}"
    exit 1
fi

# Update package list
echo -e "${YELLOW}🔄 Updating package list...${NC}"
sudo apt update

# Install Prometheus
echo -e "${YELLOW}📦 Installing Prometheus...${NC}"
sudo apt install -y prometheus prometheus-node-exporter

# Start and enable Prometheus
sudo systemctl start prometheus
sudo systemctl enable prometheus
sudo systemctl start prometheus-node-exporter
sudo systemctl enable prometheus-node-exporter

echo -e "${GREEN}✅ Prometheus installed (http://localhost:9090)${NC}"

# Install Grafana
echo -e "${YELLOW}📦 Installing Grafana...${NC}"

# Add Grafana GPG key
sudo apt install -y software-properties-common
wget -q -O - https://packages.grafana.com/gpg.key | sudo apt-key add -

# Add Grafana repository
echo "deb https://packages.grafana.com/oss/deb stable main" | sudo tee /etc/apt/sources.list.d/grafana.list

# Install Grafana
sudo apt update
sudo apt install -y grafana

# Start and enable Grafana
sudo systemctl start grafana-server
sudo systemctl enable grafana-server

echo -e "${GREEN}✅ Grafana installed (http://localhost:3000)${NC}"

# Configure Prometheus as Grafana data source
echo -e "${YELLOW}⚙️  Configuring Prometheus data source...${NC}"

# Wait for Grafana to start
sleep 5

# Add Prometheus data source (via API)
curl -X POST -H "Content-Type: application/json" -d '{
  "name":"Prometheus",
  "type":"prometheus",
  "url":"http://localhost:9090",
  "access":"proxy",
  "isDefault":true
}' http://admin:admin@localhost:3000/api/datasources 2>/dev/null || echo "Data source may already exist"

echo -e "${GREEN}✅ Prometheus data source configured${NC}"

# Install postgres_exporter for PostgreSQL monitoring
echo -e "${YELLOW}📦 Installing postgres_exporter...${NC}"
sudo apt install -y prometheus-postgres-exporter

# Configure postgres_exporter
echo -e "${YELLOW}⚙️  Configuring postgres_exporter...${NC}"
sudo tee /etc/default/prometheus-postgres-exporter > /dev/null << EOF
DATA_SOURCE_NAME="postgresql://ademcelik:YOUR_PASSWORD@localhost:5432/bist_data?sslmode=disable"
EOF

echo -e "${YELLOW}⚠️  IMPORTANT: Edit /etc/default/prometheus-postgres-exporter and replace YOUR_PASSWORD${NC}"

# Start postgres_exporter
sudo systemctl start prometheus-postgres-exporter
sudo systemctl enable prometheus-postgres-exporter

# Configure Prometheus to scrape postgres_exporter
echo -e "${YELLOW}⚙️  Configuring Prometheus scrape targets...${NC}"
sudo tee -a /etc/prometheus/prometheus.yml > /dev/null << EOF

  - job_name: 'postgresql'
    static_configs:
      - targets: ['localhost:9187']
  
  - job_name: 'node'
    static_configs:
      - targets: ['localhost:9100']
EOF

# Restart Prometheus
sudo systemctl restart prometheus

# Update firewall (if UFW is enabled)
if sudo ufw status | grep -q "Status: active"; then
    echo -e "${YELLOW}🔥 Updating firewall rules...${NC}"
    sudo ufw allow 3000/tcp  # Grafana
    sudo ufw allow 9090/tcp  # Prometheus
    echo -e "${GREEN}✅ Firewall updated${NC}"
fi

# Print summary
echo -e "${GREEN}✨ Grafana + Prometheus setup complete!${NC}"
echo -e "${YELLOW}📊 Access URLs:${NC}"
echo -e "  • Grafana:    http://YOUR_VPS_IP:3000"
echo -e "  • Prometheus: http://YOUR_VPS_IP:9090"
echo -e ""
echo -e "${YELLOW}🔐 Grafana Login:${NC}"
echo -e "  • Username: admin"
echo -e "  • Password: admin (change on first login)"
echo -e ""
echo -e "${YELLOW}📋 Next Steps:${NC}"
echo -e "  1. Edit /etc/default/prometheus-postgres-exporter (add DB password)"
echo -e "  2. Restart postgres_exporter: sudo systemctl restart prometheus-postgres-exporter"
echo -e "  3. Login to Grafana"
echo -e "  4. Import dashboard: Dashboard → Import → 9628 (PostgreSQL Database)"
echo -e "  5. Import dashboard: Dashboard → Import → 1860 (Node Exporter Full)"
echo -e ""
echo -e "${YELLOW}📚 Recommended Dashboards (Free):${NC}"
echo -e "  • PostgreSQL: 9628"
echo -e "  • Node Exporter: 1860"
echo -e "  • PM2: Custom (create your own)"
