"""Quick start / Hızlı başlangıç

- Export markets JSON:
    zsh: python kap_markets_api.py export --output sample_markets.json

- Export then persist (dry-run):
    zsh: python kap_markets_api.py export-persist --output sample_markets.json --dry-run --batch-size 200

- Persist via unified CLI (from an exported JSON):
    zsh: python persist_cli.py markets sample_markets.json --dry-run --batch-size 200

Bkz./See README:
- Quick Start: README.md#quick-start-macos-zsh
- Commands Reference: README.md#commands-reference
- Troubleshooting (Chromedriver): README.md#troubleshooting

Gereksinimler: Python 3.10.17 sanal ortam, Chrome + ./chromedriver
"""

import os
import re
import time
import json
import argparse
from typing import List, Optional

from bs4 import BeautifulSoup
from pydantic import BaseModel, Field, ValidationError
from selenium import webdriver
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait


class Company(BaseModel):
    """Bir pazar veya alt pazar içindeki tek bir şirketi/fonu temsil eder."""
    rank: int
    code: str
    name: str
    url: Optional[str] = None


class SubMarket(BaseModel):
    """Bir alt pazarı ve içindeki şirketleri/fonları temsil eder."""
    name: str
    company_count: int
    companies: List[Company] = Field(default_factory=list)


class Market(BaseModel):
    """
    Bir ana pazarı, doğrudan bağlı şirketleri ve alt pazarları ile birlikte temsil eder.
    """
    name: str
    company_count: Optional[int] = None # Ana pazarların toplam sayacı olmayabilir
    companies: List[Company] = Field(default_factory=list)
    sub_markets: List[SubMarket] = Field(default_factory=list)


class MarketInfo(BaseModel):
    """Sadece pazar adlarını ve alt pazar adlarını içeren basit model."""
    main_market: str
    sub_markets: List[str] = Field(default_factory=list)


class KAPMarketsAPI:
    """
    Dinamik içeriği işlemek için Selenium kullanarak Kamuoyu Aydınlatma Platformu'ndan (KAP)
    pazarları ve bu pazarlardaki şirket/fon verilerini getiren ve ayrıştıran bir sınıf.
    URL: https://www.kap.org.tr/tr/Pazarlar
    """

    def __init__(self, driver_path: str = 'chromedriver', driver: Optional[webdriver.Chrome] = None):
        """Initializes the API, using a shared driver if provided."""
        self.base_url = "https://www.kap.org.tr/tr/Pazarlar"
        self._shared_driver = bool(driver)

        if driver:
            self.driver = driver
        else:
            options = webdriver.ChromeOptions()
            options.add_argument('--headless')
            options.add_argument('--no-sandbox')
            options.add_argument('--disable-dev-shm-usage')
            options.add_argument(
                "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
            )
            
            try:
                service = Service(executable_path=driver_path)
                self.driver = webdriver.Chrome(service=service, options=options)
            except Exception as e:
                print(f"WebDriver başlatılırken hata oluştu: {e}")
                raise

    def _get_soup(self) -> Optional[BeautifulSoup]:
        """
        Selenium kullanarak temel URL'den içeriği alır ve bir BeautifulSoup nesnesi döndürür.
        Sayfanın ana tablo elemanının yüklenmesini bekler.
        """
        if not self.driver:
            return None
        try:
            self.driver.get(self.base_url)
            WebDriverWait(self.driver, 20).until(
                EC.presence_of_element_located((By.ID, "marketsTable"))
            )
            time.sleep(3)  # Dinamik içeriğin tam olarak render olması için ek bekleme
            return BeautifulSoup(self.driver.page_source, "html.parser")
        except TimeoutException:
            print("Sayfa içeriğinin yüklenmesi zaman aşımına uğradı.")
            return None
        except Exception as e:
            print(f"Sayfa getirilirken bir hata oluştu: {e}")
            return None

    def get_markets_list(self) -> List[MarketInfo]:
        """
        Pazar seçim menüsünü (dropdown) ayrıştırarak sadece ana ve alt pazarların
        adlarını içeren bir liste döndürür.
        """
        if not self.driver:
            print("WebDriver başlatılamadı.")
            return []
            
        markets_list = []
        try:
            self.driver.get(self.base_url)
            # Dropdown'ı açmak için tıkla
            toggle_element = WebDriverWait(self.driver, 20).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "#stickyDropdown .custom__select--toggle"))
            )
            self.driver.execute_script("arguments[0].click();", toggle_element)
            
            # Dropdown içeriğinin görünür olmasını bekle
            WebDriverWait(self.driver, 10).until(
                EC.visibility_of_element_located((By.CSS_SELECTOR, "#stickyDropdown div.select__items"))
            )
            time.sleep(1)
            soup = BeautifulSoup(self.driver.page_source, "html.parser")

            # Ana pazar ve alt pazar seçeneklerini bul
            market_options = soup.select("#stickyDropdown div.select__option")
            for option in market_options:
                main_market_tag = option.select_one("div.select__option--all")
                if not main_market_tag:
                    continue
                
                main_market_name = main_market_tag.text.strip()
                if main_market_name == "Tüm Pazarlar":
                    continue

                sub_market_tags = option.select("div.select__under--item > div")
                sub_markets = [tag.text.strip() for tag in sub_market_tags]
                
                markets_list.append(MarketInfo(main_market=main_market_name, sub_markets=sub_markets))

        except (TimeoutException, NoSuchElementException) as e:
            print(f"Pazar listesi alınırken bir eleman bulunamadı veya zaman aşımı oldu: {e}")
        except ValidationError as e:
            print(f"Pydantic doğrulama hatası: {e}")
        except Exception as e:
            print(f"Pazar listesi alınırken beklenmedik bir hata oluştu: {e}")
        finally:
            # Test için dropdown'ı kapatmaya gerek yok, bir sonraki işlem sayfayı yenileyecek.
            pass
            
        return markets_list

    def get_all_market_data(self) -> List[Market]:
        """
        Sayfadaki ana tabloyu ayrıştırarak tüm pazar, alt pazar ve şirket
        verilerini yapılandırılmış bir liste olarak döndürür.
        """
        soup = self._get_soup()
        if not soup:
            return []

        table = soup.find('table', id='marketsTable')
        if not table or not table.tbody:
            print("Pazar tablosu (marketsTable) veya tbody bulunamadı.")
            return []

        all_markets: List[Market] = []
        current_market: Optional[Market] = None
        current_sub_market: Optional[SubMarket] = None

        for row in table.tbody.find_all('tr', recursive=False):
            # Ana Pazar veya Alt Pazar Başlığı
            header_cell = row.select_one("td[colspan='4']")
            if header_cell:
                # Ana Pazar Başlığı
                if 'active' in header_cell.get('class', []):
                    if current_market:
                        all_markets.append(current_market)
                    
                    name_div = header_cell.select_one("div.px-4.font-semibold")
                    name = name_div.text.strip() if name_div else "Bilinmeyen Ana Pazar"
                    current_market = Market(name=name)
                    current_sub_market = None
                # Alt Pazar Başlığı
                else:
                    name_span = header_cell.select_one("span.px-4.font-semibold")
                    count_span = header_cell.select_one("span.font-normal.text-sm")
                    if name_span and count_span and current_market:
                        name = name_span.text.strip()
                        count_text = count_span.text.strip()
                        match = re.search(r'(\d+)', count_text)
                        count = int(match.group(1)) if match else 0
                        current_sub_market = SubMarket(name=name, company_count=count)
                        current_market.sub_markets.append(current_sub_market)
            
            # Şirket Satırı
            elif 'border-b' in row.get('class', []):
                cols = row.find_all('td')
                if len(cols) >= 3 and cols[0].text.strip().isdigit():
                    try:
                        rank = int(cols[0].text.strip())
                        code_tag = cols[1].find('a')
                        name_tag = cols[2].find('a')

                        code = code_tag.text.strip() if code_tag else "N/A"
                        name = name_tag.text.strip() if name_tag else "N/A"
                        
                        url_tag = name_tag if name_tag and name_tag.has_attr('href') else code_tag
                        url = f"https://www.kap.org.tr{url_tag['href']}" if url_tag and url_tag.has_attr('href') and url_tag['href'] != '#' else None

                        company = Company(rank=rank, code=code, name=name, url=url)

                        if current_sub_market:
                            current_sub_market.companies.append(company)
                        elif current_market:
                            # Doğrudan ana pazara bağlı şirketler (varsa)
                            current_market.companies.append(company)

                    except (ValueError, IndexError, ValidationError) as e:
                        print(f"Bir şirket satırı ayrıştırılırken hata oluştu: {row.text.strip()} - Hata: {e}")
                        continue

        if current_market:
            all_markets.append(current_market)

        return all_markets

    def close_driver(self):
        """Closes the Selenium WebDriver only if it's not a shared instance."""
        if self.driver and not self._shared_driver:
            try:
                self.driver.quit()
            except Exception as e:
                print(f"WebDriver kapatılırken bir hata oluştu: {e}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="KAP Pazarlar - JSON Export/Persist")
    sub = parser.add_subparsers(dest="cmd", required=False)

    p_exp = sub.add_parser("export", help="Sadece JSON export yap")
    p_exp.add_argument("--output", default="markets.json", help="Çıktı JSON dosya yolu")
    p_exp.add_argument("--print", action="store_true", help="JSON'u konsola yazdır")

    p_exp_persist = sub.add_parser("export-persist", help="Export + persist zinciri")
    p_exp_persist.add_argument("--output", default="markets.json")
    p_exp_persist.add_argument("--dry-run", action="store_true")
    p_exp_persist.add_argument("--batch-size", type=int, default=0)

    # Back-compat flags
    parser.add_argument("--output", help=argparse.SUPPRESS)
    parser.add_argument("--print", help=argparse.SUPPRESS)
    args = parser.parse_args()

    driver_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '.', 'chromedriver'))

    api = None
    try:
        api = KAPMarketsAPI(driver_path=driver_path)
        data = api.get_all_market_data()
        payload = [m.model_dump() for m in data]
        # Determine out path
        out = getattr(args, "output", None) or "markets.json"
        if getattr(args, "cmd", None) in (None, "export"):
            if getattr(args, "print", False):
                print(json.dumps(payload, ensure_ascii=False, indent=2))
            with open(out, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False, indent=2)
            print(f"Pazar verileri JSON olarak kaydedildi: {out}")
        elif args.cmd == "export-persist":
            with open(out, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False, indent=2)
            print(f"Pazar verileri JSON olarak kaydedildi: {out}")
            # Persist
            from persist_cli import persist_markets
            print("Persist işlemi başlatılıyor...")
            persist_markets(out, dry_run=args.dry_run, batch_size=args.batch_size)
    except Exception as e:
        print(f"Hata: {e}")
    finally:
        if api:
            api.close_driver()
