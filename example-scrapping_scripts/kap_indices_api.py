import os
"""Quick start / Hızlı başlangıç

- Export indices JSON:
    zsh: python kap_indices_api.py export --output sample_indices.json

- Export then persist (dry-run):
    zsh: python kap_indices_api.py export-persist --output sample_indices.json --dry-run --batch-size 200

- Persist via unified CLI (from an exported JSON):
    zsh: python persist_cli.py indices sample_indices.json --dry-run --batch-size 200

Bkz./See README:
- Quick Start: README.md#quick-start-macos-zsh
- Commands Reference: README.md#commands-reference
- Troubleshooting (Chromedriver): README.md#troubleshooting

Gereksinimler: Python 3.10.17 sanal ortam, Chrome + ./chromedriver
"""

import time
import json
import argparse
from typing import List, Optional

from bs4 import BeautifulSoup
from pydantic import BaseModel, ValidationError
from selenium import webdriver
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait


class Index(BaseModel):
    """KAP'taki tek bir endeksi temsil eder."""
    name: str
    code: str
    details: Optional[str] = None


class CompanyInIndex(BaseModel):
    """Bir endeks içindeki tek bir şirketi temsil eder."""
    rank: int
    code: str
    name: str
    url: Optional[str] = None


class KAPIndicesAPI:
    """
    Dinamik içeriği işlemek için Selenium kullanarak Kamuoyu Aydınlatma Platformu'ndan (KAP)
    piyasa endekslerini ve içlerindeki şirketleri getiren ve ayrıştıran bir sınıf.
    """

    def __init__(self, driver_path: str = 'chromedriver', driver: Optional[webdriver.Chrome] = None):
        """Initializes the API, using a shared driver if provided."""
        self.base_url = "https://www.kap.org.tr/tr/Endeksler"
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
            try:
                self.driver = webdriver.Chrome(service=service, options=options)
            except Exception as e:
                print(f"WebDriver başlatılırken hata oluştu: {e}")
                raise

    def _get_soup(self) -> Optional[BeautifulSoup]:
        """Selenium kullanarak temel URL'den içeriği alır ve bir BeautifulSoup nesnesi döndürür."""
        if not self.driver:
            return None
        try:
            self.driver.get(self.base_url)
            WebDriverWait(self.driver, 20).until(
                EC.presence_of_element_located((By.ID, "indicesTable"))
            )
            return BeautifulSoup(self.driver.page_source, "html.parser")
        except TimeoutException:
            print("Sayfa içeriğinin yüklenmesi zaman aşımına uğradı.")
            return None
        except Exception as e:
            print(f"Sayfa getirilirken bir hata oluştu: {e}")
            return None

    def get_all_indices(self) -> List[Index]:
        """Mevcut tüm endekslerin bir listesini almak için KAP endeksleri sayfasını ayrıştırır."""
        soup = self._get_soup()
        if not soup:
            return []

        indices = []
        options = soup.find_all('div', class_='select__option')
        for option in options:
            try:
                name = option.find('span', class_='font-semibold').text.strip()
                code = option.find('span', class_='font-medium').text.strip()
                details = option.find('span', class_='text-select-text').text.strip()
                indices.append(Index(name=name, code=code, details=details))
            except (AttributeError, ValidationError) as e:
                print(f"Bir endeks girişi ayrıştırılamadı: {e}")
                continue
        return indices

    def get_companies_by_index(self, index_name: str) -> List[CompanyInIndex]:
        """Belirli bir endekse ait şirketlerin listesini getirir."""
        soup = BeautifulSoup(self.driver.page_source, 'html.parser')
        table = soup.find('table', id='indicesTable')
        if not table:
            print("Endeks tablosu bulunamadı.")
            return []

        companies = []
        all_rows = table.find_all('tr')
        start_parsing = False

        for row in all_rows:
            header_td = row.find('td', attrs={'colspan': '12'})

            if header_td:
                # Bu bir başlık satırıdır. İstediğimiz başlık mı yoksa durmalı mıyız kontrol et.
                header_span = header_td.find('span', class_='px-4')
                if header_span and header_span.text.strip().lower() == index_name.lower():
                    start_parsing = True
                elif start_parsing:
                    # Bir sonraki başlığa ulaşıldı, bu yüzden dur.
                    break
                continue  # Şirket olarak ayrıştırılmaması için başlık satırını atla

            if start_parsing:
                cols = row.find_all('td')
                if len(cols) >= 3 and cols[0].text.strip().isdigit():
                    try:
                        rank = int(cols[0].text.strip())
                        code = cols[1].text.strip()
                        name = cols[2].text.strip()
                        link_tag = cols[1].find('a')
                        url = f"https://www.kap.org.tr{link_tag['href']}" if link_tag and link_tag.has_attr('href') else None
                        companies.append(CompanyInIndex(rank=rank, code=code, name=name, url=url))
                    except (ValueError, IndexError, ValidationError) as e:
                        # print(f"'{index_name}' endeksi için bir satır ayrıştırma hatası nedeniyle atlanıyor: {e}")
                        continue
        return companies

    def close_driver(self):
        """Closes the Selenium WebDriver only if it's not a shared instance."""
        if self.driver and not self._shared_driver:
            self.driver.quit()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="KAP Endeksler - JSON Export/Persist")
    sub = parser.add_subparsers(dest="cmd", required=False)

    p_exp = sub.add_parser("export", help="Sadece JSON export yap")
    p_exp.add_argument("--output", default="indices.json", help="Çıktı JSON dosya yolu")
    p_exp.add_argument("--with-companies", action="store_true", help="Her endeks için şirketleri de topla")
    p_exp.add_argument("--print", action="store_true", help="JSON'u konsola yazdır")

    p_exp_persist = sub.add_parser("export-persist", help="Export + persist zinciri")
    p_exp_persist.add_argument("--output", default="indices.json")
    p_exp_persist.add_argument("--with-companies", action="store_true")
    p_exp_persist.add_argument("--dry-run", action="store_true")
    p_exp_persist.add_argument("--batch-size", type=int, default=0)

    # Back-compat flags
    parser.add_argument("--output", help=argparse.SUPPRESS)
    parser.add_argument("--with-companies", help=argparse.SUPPRESS)
    parser.add_argument("--print", help=argparse.SUPPRESS)
    args = parser.parse_args()

    driver_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'chromedriver')
    if not os.path.exists(driver_path):
        print(f"ChromeDriver şurada bulunamadı: {driver_path}")
    else:
        api = KAPIndicesAPI(driver_path=driver_path)
        try:
            indices = api.get_all_indices()
            payload = []
            for idx in indices:
                obj = idx.model_dump()
                if getattr(args, "with_companies", False):
                    companies = api.get_companies_by_index(idx.name)
                    obj["companies"] = [c.model_dump() for c in companies]
                payload.append(obj)
            out = getattr(args, "output", None) or "indices.json"
            if getattr(args, "cmd", None) in (None, "export"):
                if getattr(args, "print", False):
                    print(json.dumps(payload, ensure_ascii=False, indent=2))
                with open(out, "w", encoding="utf-8") as f:
                    json.dump(payload, f, ensure_ascii=False, indent=2)
                print(f"Endeks verileri JSON olarak kaydedildi: {out}")
            elif args.cmd == "export-persist":
                with open(out, "w", encoding="utf-8") as f:
                    json.dump(payload, f, ensure_ascii=False, indent=2)
                print(f"Endeks verileri JSON olarak kaydedildi: {out}")
                from persist_cli import persist_indices
                print("Persist işlemi başlatılıyor...")
                persist_indices(out, dry_run=args.dry_run, batch_size=args.batch_size)
        finally:
            if api:
                api.close_driver()
