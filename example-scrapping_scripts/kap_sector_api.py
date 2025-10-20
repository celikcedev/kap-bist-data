"""Quick start / Hızlı başlangıç

- Export sectors JSON:
    zsh: python kap_sector_api.py export --output sample_sectors.json

- Export then persist (dry-run):
    zsh: python kap_sector_api.py export-persist --output sample_sectors.json --dry-run --batch-size 200

- Persist via unified CLI (from an exported JSON):
    zsh: python persist_cli.py sectors sample_sectors.json --dry-run --batch-size 200

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
from pydantic import BaseModel, ValidationError, Field
from selenium import webdriver
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait


class Company(BaseModel):
    """Bir sektör veya alt sektör içindeki tek bir şirketi temsil eder."""
    rank: int
    code: str
    name: str
    url: Optional[str] = None


class SubSector(BaseModel):
    """Bir alt sektörü ve içindeki şirketleri temsil eder."""
    name: str
    companies: List[Company] = Field(default_factory=list)


class Sector(BaseModel):
    """
    Bir ana sektörü, doğrudan bağlı şirketleri ve alt sektörleri ile birlikte temsil eder.
    """
    name: str
    company_count: int
    companies: List[Company] = Field(default_factory=list)
    sub_sectors: List[SubSector] = Field(default_factory=list)


class SectorInfo(BaseModel):
    """Sadece sektör adlarını ve alt sektör adlarını içeren basit model."""
    main_sector: str
    sub_sectors: List[str] = Field(default_factory=list)


class KAPSectorAPI:
    """
    Dinamik içeriği işlemek için Selenium kullanarak Kamuoyu Aydınlatma Platformu'ndan (KAP)
    sektörleri ve içlerindeki şirketleri getiren ve ayrıştıran bir sınıf.
    """

    def __init__(self, driver_path: str = 'chromedriver', driver: Optional[webdriver.Chrome] = None):
        """Initializes the API, using a shared driver if provided."""
        self.base_url = "https://www.kap.org.tr/tr/Sektorler"
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
            
            service = Service(executable_path=driver_path)
            self.driver = webdriver.Chrome(service=service, options=options)


    def _get_soup(self) -> Optional[BeautifulSoup]:
        """Selenium kullanarak temel URL'den içeriği alır ve bir BeautifulSoup nesnesi döndürür."""
        if not self.driver:
            return None
        try:
            self.driver.get(self.base_url)
            WebDriverWait(self.driver, 20).until(
                EC.presence_of_element_located((By.ID, "sectorsTable"))
            )
            # Sayfanın tam olarak yüklenmesi için kısa bir bekleme süresi
            time.sleep(2)
            return BeautifulSoup(self.driver.page_source, "html.parser")
        except TimeoutException:
            print("Sayfa içeriğinin yüklenmesi zaman aşımına uğradı.")
            return None
        except Exception as e:
            print(f"Sayfa getirilirken bir hata oluştu: {e}")
            return None

    def get_sectors_list(self) -> List[SectorInfo]:
        """
        Sadece ana ve alt sektörlerin adlarını içeren bir liste döndürmek için
        sektör seçimi dropdown'ını ayrıştırır.
        """
        soup = self._get_soup()
        if not soup:
            return []

        sectors_list = []
        # Dropdown'ı açmak için tıklama simülasyonu
        try:
            toggle_element = self.driver.find_element(By.CSS_SELECTOR, ".custom__select--toggle")
            self.driver.execute_script("arguments[0].click();", toggle_element)
            WebDriverWait(self.driver, 10).until(
                EC.visibility_of_element_located((By.CSS_SELECTOR, "div.select__items"))
            )
            soup = BeautifulSoup(self.driver.page_source, "html.parser")
        except Exception as e:
            print(f"Dropdown açılırken hata: {e}")
            return []

        sector_containers = soup.select("div.select__all > div")

        for container in sector_containers:
            main_sector_tag = container.select_one("div.select__option--all")
            if not main_sector_tag:
                continue

            main_sector_name = main_sector_tag.text.strip()
            if main_sector_name.lower() == 'tüm sektörler':
                continue

            sub_sector_tags = container.select("div.select__under--item div.text-danger")
            sub_sectors = [tag.text.strip() for tag in sub_sector_tags]

            try:
                sectors_list.append(SectorInfo(main_sector=main_sector_name, sub_sectors=sub_sectors))
            except ValidationError as e:
                print(f"Sektör bilgisi doğrulanırken hata: {e}")

        # Dropdown'ı kapat
        try:
            toggle_element = self.driver.find_element(By.CSS_SELECTOR, ".custom__select--toggle")
            self.driver.execute_script("arguments[0].click();", toggle_element)
        except:
            pass # Zaten kapalıysa sorun değil

        return sectors_list

    def get_all_sector_data(self) -> List[Sector]:
        """
        Sayfadaki ana tabloyu ayrıştırarak tüm sektör, alt sektör ve şirket
        verilerini yapılandırılmış bir liste olarak döndürür.
        """
        soup = self._get_soup()
        if not soup:
            return []

        table = soup.find('table', id='sectorsTable')
        if not table or not table.tbody:
            print("Sektör tablosu veya tbody bulunamadı.")
            return []

        all_sectors: List[Sector] = []
        current_sector: Optional[Sector] = None
        current_sub_sector: Optional[SubSector] = None

        for row in table.tbody.find_all('tr', recursive=False):
            # Ana Sektör Başlığı
            if 'static' in row.get('class', []):
                if current_sector:
                    all_sectors.append(current_sector)

                header_span = row.select_one("span.px-4.font-semibold")
                count_span = row.select_one("span.font-normal.text-sm")
                if header_span and count_span:
                    name = header_span.text.strip()
                    count_text = count_span.text.strip()
                    # "5 Şirket Bulundu" gibi bir metinden sayıyı al
                    match = re.search(r'(\d+)', count_text)
                    count = int(match.group(1)) if match else 0
                    current_sector = Sector(name=name, company_count=count)
                    current_sub_sector = None

            # Alt Sektör Başlığı
            elif 'bg-gray-200' in row.get('class', []):
                td = row.find('td')
                if td and current_sector:
                    sub_sector_name = td.text.strip()
                    current_sub_sector = SubSector(name=sub_sector_name)
                    current_sector.sub_sectors.append(current_sub_sector)

            # Şirket Satırı
            elif 'border-b' in row.get('class', []):
                cols = row.find_all('td')
                if len(cols) >= 3 and cols[0].text.strip().isdigit():
                    try:
                        rank = int(cols[0].text.strip())
                        code_tag = cols[1].find('a')
                        name_tag = cols[2].find('a')

                        code = code_tag.text.strip() if code_tag else cols[1].text.strip()
                        name = name_tag.text.strip() if name_tag else cols[2].text.strip()
                        
                        url_tag = name_tag if name_tag and name_tag.has_attr('href') else code_tag
                        url = f"https://www.kap.org.tr{url_tag['href']}" if url_tag and url_tag.has_attr('href') and url_tag['href'] != '#' else None

                        company = Company(rank=rank, code=code, name=name, url=url)

                        if current_sub_sector:
                            current_sub_sector.companies.append(company)
                        elif current_sector:
                            current_sector.companies.append(company)

                    except (ValueError, IndexError, ValidationError) as e:
                        print(f"Bir şirket satırı ayrıştırılırken hata oluştu: {e}")
                        continue
            
            # "Kayıt Bulunamadı!" satırı
            elif 'text-center' in row.get('class', []):
                # Bu satırda özel bir işlem yapmaya gerek yok, sadece atla.
                # Şirket sayısı zaten başlıktan alınıyor.
                pass

        if current_sector:
            all_sectors.append(current_sector)

        return all_sectors

    def close_driver(self):
        """Closes the Selenium WebDriver only if it's not a shared instance."""
        if self.driver and not self._shared_driver:
            self.driver.quit()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="KAP Sektörler - JSON Export/Persist")
    sub = parser.add_subparsers(dest="cmd", required=False)

    p_exp = sub.add_parser("export", help="Sadece JSON export yap")
    p_exp.add_argument("--output", default="sectors.json", help="Çıktı JSON dosya yolu")
    p_exp.add_argument("--print", action="store_true", help="JSON'u konsola yazdır")

    p_exp_persist = sub.add_parser("export-persist", help="Export + persist zinciri")
    p_exp_persist.add_argument("--output", default="sectors.json")
    p_exp_persist.add_argument("--dry-run", action="store_true")
    p_exp_persist.add_argument("--batch-size", type=int, default=0)

    # Back-compat flags
    parser.add_argument("--output", help=argparse.SUPPRESS)
    parser.add_argument("--print", help=argparse.SUPPRESS)
    args = parser.parse_args()

    driver_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '.', 'chromedriver'))

    api = None
    try:
        api = KAPSectorAPI(driver_path=driver_path)
        data = api.get_all_sector_data()
        payload = [s.model_dump() for s in data]
        out = getattr(args, "output", None) or "sectors.json"
        if getattr(args, "cmd", None) in (None, "export"):
            if getattr(args, "print", False):
                print(json.dumps(payload, ensure_ascii=False, indent=2))
            with open(out, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False, indent=2)
            print(f"Sektör verileri JSON olarak kaydedildi: {out}")
        elif args.cmd == "export-persist":
            with open(out, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False, indent=2)
            print(f"Sektör verileri JSON olarak kaydedildi: {out}")
            from persist_cli import persist_sectors
            print("Persist işlemi başlatılıyor...")
            persist_sectors(out, dry_run=args.dry_run, batch_size=args.batch_size)
    except Exception as e:
        print(f"Hata: {e}")
    finally:
        if api:
            api.close_driver()

