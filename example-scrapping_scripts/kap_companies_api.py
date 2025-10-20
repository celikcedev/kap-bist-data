# -*- coding: utf-8 -*-
"""
This module provides a professional, Pydantic V2 based API client for fetching
a list of all companies traded on BIST from Turkey's Public Disclosure Platform (KAP)
by using Selenium to handle dynamic content.

The main functionality is to retrieve a list of all companies with their
stock code, name, province, and independent auditor information.

Quick start / Hızlı başlangıç

- Export companies list:
    zsh: python kap_companies_api.py companies --output companies.json --print

- Export general info (structured) for first N companies:
    zsh: python kap_companies_api.py general --limit 10 --output sample_general.json

- Export and persist (dry-run):
    zsh: python kap_companies_api.py general-persist --limit 10 --output sample_general.json --dry-run --batch-size 100

- Persist previously exported JSON with the unified CLI:
    zsh: python persist_cli.py general sample_general.json --dry-run --batch-size 100

See README:
- Quick Start: README.md#quick-start-macos-zsh
- Commands Reference: README.md#commands-reference
- DB/Schema: README.md#database-and-schema

Requirements: Python 3.10.17 venv, Chrome + matching ./chromedriver
"""

import time
import json
import os
from typing import List, Optional, Dict, Any
import argparse
import sys
import argparse

from bs4 import BeautifulSoup
from pydantic import BaseModel, Field, HttpUrl, ValidationError
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from datetime import datetime

# --- Pydantic Data Model ---

class CompanySummary(BaseModel):
    """Represents the summary information for a single company listed on KAP."""
    code: str = Field(..., description="The stock market code of the company.")
    name: str = Field(..., description="The official name of the company.")
    province: str = Field(..., description="The province where the company is located.")
    detail_url: HttpUrl = Field(..., description="The URL to the company's detailed information page on KAP.")
    auditor: Optional[str] = Field(None, description="The name of the independent audit firm.")

# --- Main API Class ---

class KAPCompaniesAPI:
    """A client to fetch company information from KAP."""
    BASE_URL = "https://www.kap.org.tr"
    COMPANIES_LIST_URL = f"{BASE_URL}/tr/bist-sirketler"

    def __init__(self, driver_path: str = 'chromedriver', driver: Optional[webdriver.Chrome] = None):
        """Initializes the API, using a shared driver if provided."""
        if driver:
            self.driver = driver
            self._shared_driver = True
        else:
            self._shared_driver = False
            chrome_options = Options()
            # Step A optimizations: new headless, disable images, eager load, fewer extras
            chrome_options.add_argument("--headless=new")
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--disable-dev-shm-usage")
            chrome_options.add_argument("--disable-gpu")
            chrome_options.add_argument("--disable-extensions")
            chrome_options.add_argument("--disable-notifications")
            chrome_options.add_argument("--window-size=1920,1080")
            # Do not load images to save bandwidth/CPU
            prefs = {
                "profile.managed_default_content_settings.images": 2,
                "profile.default_content_setting_values.images": 2,
            }
            chrome_options.add_experimental_option("prefs", prefs)
            # Faster page load strategy
            chrome_options.page_load_strategy = 'eager'
            
            if not os.path.exists(driver_path):
                raise FileNotFoundError(f"ChromeDriver not found at {driver_path}")

            try:
                service = Service(executable_path=driver_path)
                self.driver = webdriver.Chrome(service=service, options=chrome_options)
            except Exception as e:
                print(f"Failed to initialize Chrome Driver: {e}")
                self.driver = None

    def _get_soup_with_selenium(self, url: str, wait_selector: Optional[str] = None, timeout: int = 8, attempts: int = 3, backoff: float = 1.6) -> Optional[BeautifulSoup]:
        """Fetches a URL using Selenium (with retry/backoff) and returns a BeautifulSoup object."""
        if not self.driver:
            return None
        for attempt in range(1, attempts + 1):
            try:
                self.driver.get(url)
                if wait_selector:
                    try:
                        WebDriverWait(self.driver, timeout).until(
                            EC.presence_of_element_located((By.CSS_SELECTOR, wait_selector))
                        )
                    except Exception:
                        # Fallback static wait (short)
                        time.sleep(min(2.0, float(timeout)))
                else:
                    # Short generic wait
                    time.sleep(2.0)
                return BeautifulSoup(self.driver.page_source, "html.parser")
            except Exception as e:
                print(f"Attempt {attempt}/{attempts} failed fetching {url}: {e}")
                if attempt < attempts:
                    sleep_for = backoff ** attempt
                    time.sleep(sleep_for)
                else:
                    print(f"Giving up on {url}")
                    return None

    def _get_general_soup_and_expand(self, url: str, timeout: int = 8) -> Optional[BeautifulSoup]:
        """
        Navigate to the company's general info page, ensure the General tab is open
        and sections are expanded, then return a BeautifulSoup of the page.
        """
        if not self.driver:
            return None
        try:
            # Use retry-enabled loader
            soup_dummy = self._get_soup_with_selenium(url, wait_selector="#general", timeout=timeout)
            if not soup_dummy:
                return None

            # Attempt to expand all sections via the toggle button if present
            try:
                btn = self.driver.find_element(By.CSS_SELECTOR, "#general > div > div > div.flex.gap-3.justify-end.items-center.w-full.h-max.text-sm.font-medium.p-4.company__sgbf-remove > button")
                # Click up to 2 times to reach 'expanded' state if it's a toggle
                for _ in range(2):
                    btn.click()
                    time.sleep(0.4)
            except Exception:
                # Fallback: try to open each section by clicking its button
                try:
                    section_buttons = self.driver.find_elements(By.CSS_SELECTOR, "#general > div > div > div > div > button")
                    for b in section_buttons:
                        try:
                            # Click if aria-expanded is false or missing
                            expanded = b.get_attribute("aria-expanded")
                            if expanded is None or expanded == "false":
                                b.click()
                                time.sleep(0.4)
                        except Exception:
                            continue
                except Exception:
                    pass

            time.sleep(0.8)
            return BeautifulSoup(self.driver.page_source, "html.parser")
        except Exception as e:
            print(f"Error preparing General Info page at {url}: {e}")
            return None

    def _fetch_page_content(self, url: str, wait_selector: Optional[str] = None) -> Optional[dict]:
        """
        Navigate to the given URL and return a dict containing full page HTML and text.
        Returns None if navigation or parsing fails.

        Structure:
        {
            "fetched_url": str,
            "html": str,
            "text": str,
            "fetched_at": ISO-8601 timestamp string
        }
        """
        soup = self._get_soup_with_selenium(url, wait_selector=wait_selector)
        if not soup:
            return None

        try:
            html = str(soup)
            text = "\n".join(s for s in soup.stripped_strings)
            return {
                "fetched_url": url,
                "html": html,
                "text": text,
                "fetched_at": datetime.utcnow().isoformat() + "Z",
            }
        except Exception as e:
            print(f"Failed to serialize content for URL {url}: {e}")
            return None

    def get_companies_list(self) -> List[CompanySummary]:
        """
        Fetches the list of all BIST companies with their code, name, city, 
        and auditor information.
        """
        print("Fetching company list using Selenium...")
        soup = self._get_soup_with_selenium(self.COMPANIES_LIST_URL, wait_selector="tbody")
        if not soup:
            return []

        companies = []
        table_body = soup.find("tbody")
        if not table_body:
            print("Could not find the company list table body (tbody).")
            return []

        company_rows = table_body.find_all("tr", class_="border-b")

        for row in company_rows:
            cells = row.find_all("td")
            if len(cells) < 4:
                continue

            try:
                link_tag = cells[0].find('a', href=True)
                if not link_tag:
                    continue
                
                # --- Hybrid Code Parsing Logic ---
                full_code_text = link_tag.text.strip()
                potential_codes = [code for code in full_code_text.split(' ') if code] # Split and remove empty strings

                codes_to_process = []
                # Case 1: Hybrid Smart Selection (Exactly 2 codes, one short, one long)
                if len(potential_codes) == 2:
                    short_codes = [c for c in potential_codes if len(c) <= 3]
                    long_codes = [c for c in potential_codes if len(c) >= 4]
                    if len(short_codes) == 1 and len(long_codes) == 1:
                        codes_to_process.append(long_codes[0])
                        # print(f"INFO: Hybrid selection applied to '{full_code_text}'. Selected: '{long_codes[0]}'")
                    else:
                        # If the specific 2-code condition is not met, treat them as duplicates
                        codes_to_process.extend(potential_codes)
                # Case 2: Default to duplication for all other multi-code cases or single code
                else:
                    codes_to_process.extend(potential_codes)
                # --- End of Logic ---

                name = cells[1].text.strip()
                province = cells[2].text.strip()
                auditor = cells[3].text.strip()
                url_suffix = link_tag["href"]

                if auditor == '-':
                    auditor = None

                # Create a record for each code determined by the logic above
                for code in codes_to_process:
                    summary_data = {
                        "code": code,
                        "name": name,
                        "province": province,
                        "detail_url": f"{self.BASE_URL}{url_suffix}",
                        "auditor": auditor
                    }
                    companies.append(CompanySummary(**summary_data))

            except (ValidationError, KeyError, IndexError, AttributeError) as e:
                print(f"Skipping a row due to parsing error: {e}")

        print(f"Found {len(companies)} companies.")
        return companies

    # -------------- Utility parsing helpers --------------
    @staticmethod
    def _clean_text(val: Optional[str]) -> Optional[str]:
        if val is None:
            return None
        txt = " ".join(val.split())
        if txt == "" or txt == "-" or txt.lower() == "info not available":
            return None
        return txt

    @staticmethod
    def _parse_float(val: Optional[str]) -> Optional[float]:
        txt = KAPCompaniesAPI._clean_text(val)
        if txt is None:
            return None
        try:
            # Normalize Turkish-style numbers: 1.234.567,89 -> 1234567.89
            txt = txt.replace(".", "").replace(",", ".")
            return float(txt)
        except Exception:
            return None

    @staticmethod
    def _parse_int(val: Optional[str]) -> Optional[int]:
        f = KAPCompaniesAPI._parse_float(val)
        return int(f) if f is not None else None

    @staticmethod
    def _parse_date_ddmmyyyy(val: Optional[str]) -> Optional[str]:
        txt = KAPCompaniesAPI._clean_text(val)
        if txt is None:
            return None
        for fmt in ("%d/%m/%Y", "%d.%m.%Y", "%d-%m-%Y", "%Y-%m-%d", "%d/%m/%y", "%d.%m.%y"):
            try:
                dt = datetime.strptime(txt, fmt)
                return dt.date().isoformat()
            except Exception:
                continue
        return None

    @staticmethod
    def _parse_bool(val: Optional[str]) -> Optional[bool]:
        txt = KAPCompaniesAPI._clean_text(val)
        if txt is None:
            return None
        low = txt.lower()
        if low in ("yes", "true", "evet", "traded"):
            return True
        if low in ("no", "false", "hayır", "not traded"):
            return False
        return None

    @staticmethod
    def _parse_table(table_tag) -> dict:
        """Parse a table into columns and rows of dicts with cleaned text."""
        if not table_tag:
            return {"columns": [], "rows": []}
        # Headers
        headers = []
        thead = table_tag.find("thead")
        if thead:
            ths = thead.find_all("th")
            headers = [KAPCompaniesAPI._clean_text(th.get_text(strip=True)) for th in ths]
        # Rows
        rows_out = []
        tbody = table_tag.find("tbody")
        if tbody:
            for tr in tbody.find_all("tr"):
                cells = tr.find_all(["td", "th"])
                values = [KAPCompaniesAPI._clean_text(td.get_text(" ", strip=True)) for td in cells]
                # Map by headers if available; else use indices as keys
                if headers and len(headers) == len(values):
                    row = {headers[i]: values[i] for i in range(len(headers))}
                else:
                    row = {str(i): values[i] if i < len(values) else None for i in range(len(values))}
                rows_out.append(row)
        return {"columns": headers, "rows": rows_out}

    # Known table schemas by title -> column name -> type
    TABLE_SCHEMAS: Dict[str, Dict[str, str]] = {
        "Communication Address, Phone and Fax": {
            "Address": "string",
            "Phone": "string",
            "Fax": "string",
        },
        "Investor Relations Department or Contact People": {
            "Name-Surname": "string",
            "Position": "string",
            "Assignment Date": "date",
            "Phone": "string",
            "Email": "string",
            "Type of Licence Document": "string",
            "Licence Document No": "string",
        },
        "Current List of Other Exchanges or Organized Markets where the Company's Capital Market Instruments are Listed or Traded": {
            "Type of The Listed/Trading Capital Market Instrument": "string",
            "Initial Date of Listing/Trading": "date",
            "Country of the Market/Stock Exchange": "string",
            "Name of the Market/Stock Exchange": "string",
            "Relevant sub-market of the Market or Stock Exchange": "string",
        },
        "Board Members": {
            "Name-Surname": "string",
            "Real Person Acting on Behalf of Legal Person Member": "string",
            "Gender": "string",
            "Title": "string",
            "Profession": "string",
            "The First Election Date To Board": "date",
            "Whether Executive Director or Not": "string",
            "Positions Held in the Company in the Last 5 Years": "string",
            "Current Positions Held Outside the Company": "string",
            "Whether the Director has at Least 5 Years’ Experience on Audit, Accounting and/or Finance or not": "boolean",
            "Share in Capital (%)": "float",
            "The Share Group that the Board Member Representing": "string",
            "Independent Board Member or not": "string",
            "Link To PDP Notification That Includes The Independency Declaration": "url",
            "Whether the Independent Director Considered By The Nomination Committee": "boolean",
            "Whether She/He is the Director Who Ceased to Satisfy The Independence or Not": "boolean",
            "Committees Charged and Task": "string",
        },
        "Top Management": {
            "Name-Surname": "string",
            "Title": "string",
            "Profession": "string",
            "Positions Held in the Company in the Last 5 Years": "string",
            "Current Positions Held Outside the Company": "string",
        },
        "Breakdown of Shareholders Holding More Than 5% of the Capital and Voting Rights": {
            "Shareholder": "string",
            "Share in Capital (TL)": "float",
            "Ratio in Capital (%)": "float",
            "Voting Right Ratio(%)": "float",
        },
        "Actual Shares Outstanding": {
            "Exchange Code": "string",
            "Actual Shares Outstanding(TL)": "float",
            "Actual Outstanding Shares Ratio(%)": "float",
        },
        "Information About Shares Representing the Capital": {
            "Share Group": "string",
            "Registered / Bearer Share": "string",
            "Nominal Value per Share (TL)": "float",
            "Monetary Unit": "string",
            "Nominal Value of Shares": "float",
            "Ratio to Total Capital": "float",
            "Type of Privilege": "string",
            "Exchange Traded or Not": "boolean",
        },
        "Subsidiaries, Financial Non-Current Assets and Financial Investments": {
            "Company Title": "string",
            "Scope of Activities of Company": "string",
            "Paid-in/Issued Capital": "float",
            "Capital Share of Company": "float",
            "Monetary Unit": "string",
            "Ratio of Capital Share of Company (%)": "float",
            "Relation with the Company": "string",
        },
    }

    @staticmethod
    def _cast_value(value: Optional[str], typ: str) -> Any:
        if typ == "string":
            return KAPCompaniesAPI._clean_text(value)
        if typ == "float":
            return KAPCompaniesAPI._parse_float(value)
        if typ == "int":
            return KAPCompaniesAPI._parse_int(value)
        if typ == "date":
            return KAPCompaniesAPI._parse_date_ddmmyyyy(value)
        if typ == "boolean":
            return KAPCompaniesAPI._parse_bool(value)
        if typ == "url":
            v = KAPCompaniesAPI._clean_text(value)
            if v and (v.startswith("http://") or v.startswith("https://")):
                return v
            return None if v in (None, "-") else v
        return KAPCompaniesAPI._clean_text(value)

    def _apply_table_schema(self, table: dict, table_title: Optional[str]) -> dict:
        """Attach types and cast rows according to known schemas by title."""
        if not table_title:
            return {"columns": table.get("columns", []), "types": None, "rows": table.get("rows", [])}
        schema = self.TABLE_SCHEMAS.get(table_title)
        columns = table.get("columns", [])
        rows = table.get("rows", [])
        if not schema or not columns:
            return {"columns": columns, "types": None, "rows": rows}
        # Build types aligned with columns list
        types = []
        for col in columns:
            typ = schema.get(col or "", "string")
            types.append(typ)
        # Cast rows
        cast_rows = []
        for row in rows:
            cast_row = {}
            for i, col in enumerate(columns):
                typ = types[i] if i < len(types) else "string"
                val = row.get(col) if isinstance(row, dict) else None
                cast_row[col] = self._cast_value(val, typ)
            cast_rows.append(cast_row)
        return {"columns": columns, "types": types, "rows": cast_rows}

    # -------------- Section parsers using provided selectors --------------
    def _parse_contact_information(self, soup: BeautifulSoup) -> Optional[dict]:
        base_sel = "#general > div > div > div:nth-child(2)"
        out = {"section_key": "contact_information", "title": "CONTACT INFORMATION", "subsections": []}
        # Head Office Address
        h_title = soup.select_one(base_sel + " > div > div > div > div > div > div:nth-child(1) > div > div > div > span")
        h_value = soup.select_one(base_sel + " > div > div > div > div > div > div:nth-child(1) > div > div > span")
        out["subsections"].append({
            "content_type": "text",
            "title": self._clean_text(h_title.get_text(strip=True) if h_title else "Head Office Address"),
            "text": self._clean_text(h_value.get_text(" ", strip=True) if h_value else None)
        })

        # Communication Address, Phone and Fax (table)
        c_title = soup.select_one(base_sel + " > div > div > div > div > div > div:nth-child(2) > div > div.flex.items-center.justify-between.py-4.company__sgbf-h6-title > div.font-semibold.text-sm.text-danger")
        c_table = soup.select_one(base_sel + " > div > div > div > div > div > div:nth-child(2) > div > div.overflow-x-auto.w-full > table")
        c_title_text = self._clean_text(c_title.get_text(strip=True) if c_title else "Communication Address, Phone and Fax")
        out["subsections"].append({
            "content_type": "table",
            "title": c_title_text,
            "table": self._apply_table_schema(self._parse_table(c_table), c_title_text)
        })

        # Production Facilities Address (can be multiple lines / paragraphs)
        p_title = soup.select_one(base_sel + " > div > div > div > div > div > div:nth-child(3) > div > div > div > span")
        p_val_container = soup.select_one(base_sel + " > div > div > div > div > div > div:nth-child(3) > div > div > span")
        p_list = []
        if p_val_container:
            # Collect text from paragraphs if exist; else split lines
            paragraphs = p_val_container.find_all("p")
            if paragraphs:
                for p in paragraphs:
                    t = self._clean_text(p.get_text(" ", strip=True))
                    if t:
                        p_list.append(t)
            else:
                raw = self._clean_text(p_val_container.get_text("\n", strip=True))
                if raw:
                    for line in [l.strip() for l in raw.split("\n") if l.strip()]:
                        p_list.append(line)
        out["subsections"].append({
            "content_type": "list",
            "title": self._clean_text(p_title.get_text(strip=True) if p_title else "Production Facilities Address"),
            "items": p_list if p_list else None
        })

        # E-mail Address (table with single column)
        e_title = soup.select_one(base_sel + " > div > div > div > div > div > div:nth-child(4) > div > div.flex.items-center.justify-between.py-4.company__sgbf-h6-title > div.font-semibold.text-sm.text-danger")
        e_table = soup.select_one(base_sel + " > div > div > div > div > div > div:nth-child(4) > div > div.overflow-x-auto.w-full > table")
        e_title_text = self._clean_text(e_title.get_text(strip=True) if e_title else "E-mail Address")
        out["subsections"].append({
            "content_type": "table",
            "title": e_title_text,
            "table": self._apply_table_schema(self._parse_table(e_table), e_title_text)
        })

        # Web-site (simple value)
        w_title = soup.select_one(base_sel + " > div > div > div > div > div > div:nth-child(5) > div > div > div > span")
        w_value = soup.select_one(base_sel + " > div > div > div > div > div > div:nth-child(5) > div > div > span")
        out["subsections"].append({
            "content_type": "text",
            "title": self._clean_text(w_title.get_text(strip=True) if w_title else "Web-site"),
            "text": self._clean_text(w_value.get_text(" ", strip=True) if w_value else None)
        })

        # Investor Relations Department or Contact People (table)
        ir_title = soup.select_one(base_sel + " > div > div > div > div > div > div:nth-child(6) > div > div.flex.items-center.justify-between.py-4.company__sgbf-h6-title > div.font-semibold.text-sm.text-danger")
        ir_table = soup.select_one(base_sel + " > div > div > div > div > div > div:nth-child(6) > div > div.overflow-x-auto.w-full > table")
        ir_title_text = self._clean_text(ir_title.get_text(strip=True) if ir_title else "Investor Relations Department or Contact People")
        out["subsections"].append({
            "content_type": "table",
            "title": ir_title_text,
            "table": self._apply_table_schema(self._parse_table(ir_table), ir_title_text)
        })

        return out

    def _parse_scope_and_audit(self, soup: BeautifulSoup) -> Optional[dict]:
        base_sel = "#general > div > div > div:nth-child(3)"
        out = {
            "section_key": "scope_and_audit",
            "title": "SCOPE OF ACTIVITIES AND INDEPENDENT AUDIT COMPANY INFORMATION",
            "subsections": []
        }
        # Scope of Activities of Company (long text)
        s_title = soup.select_one(base_sel + " > div > div > div > div > div > div > div:nth-child(1) > div > div > span")
        s_val_container = soup.select_one(base_sel + " > div > div > div > div > div > div > div:nth-child(1) > div > span")
        scope_val = None
        if s_val_container:
            paras = s_val_container.find_all("p")
            if paras:
                scope_val = "\n".join(filter(None, [self._clean_text(p.get_text(" ", strip=True)) for p in paras])) or None
            else:
                scope_val = self._clean_text(s_val_container.get_text(" ", strip=True))
        out["subsections"].append({
            "content_type": "text",
            "title": self._clean_text(s_title.get_text(strip=True) if s_title else "Scope of Activities of Company"),
            "text": scope_val
        })

        # Duration of Company
        d_title = soup.select_one(base_sel + " > div > div > div > div > div > div > div:nth-child(2) > div > div > span")
        d_val = soup.select_one(base_sel + " > div > div > div > div > div > div > div:nth-child(2) > div > span")
        out["subsections"].append({
            "content_type": "text",
            "title": self._clean_text(d_title.get_text(strip=True) if d_title else "Duration of Company"),
            "text": self._clean_text(d_val.get_text(" ", strip=True) if d_val else None)
        })

        # Independent Audit Company
        i_title = soup.select_one(base_sel + " > div > div > div > div > div > div > div:nth-child(3) > div > div > span")
        i_val = soup.select_one(base_sel + " > div > div > div > div > div > div > div:nth-child(3) > div > span")
        out["subsections"].append({
            "content_type": "text",
            "title": self._clean_text(i_title.get_text(strip=True) if i_title else "Independent Audit Company"),
            "text": self._clean_text(i_val.get_text(" ", strip=True) if i_val else None)
        })

        # Sector of Company
        sec_title = soup.select_one(base_sel + " > div > div > div > div > div > div > div:nth-child(4) > div > div > span")
        sec_val = soup.select_one(base_sel + " > div > div > div > div > div > div > div:nth-child(4) > div > span")
        out["subsections"].append({
            "content_type": "text",
            "title": self._clean_text(sec_title.get_text(strip=True) if sec_title else "Sector of Company"),
            "text": self._clean_text(sec_val.get_text(" ", strip=True) if sec_val else None)
        })
        return out

    def _parse_markets_indices(self, soup: BeautifulSoup) -> Optional[dict]:
        base_sel = "#general > div > div > div:nth-child(4)"
        out = {"section_key": "markets_indices_instruments", "title": "MARKETS, INDICES AND CAPITAL MARKET INSTRUMENTS", "subsections": []}
        # BIST Market where Company's Capital Market Instruments are Traded
        m1_title = soup.select_one(base_sel + " > div > div > div > div > div > div:nth-child(1) > div:nth-child(1) > div > div > span")
        m1_val = soup.select_one(base_sel + " > div > div > div > div > div > div:nth-child(1) > div:nth-child(1) > div > span")
        out["subsections"].append({
            "content_type": "text",
            "title": self._clean_text(m1_title.get_text(strip=True) if m1_title else "BIST Market where Company's Capital Market Instruments are Traded"),
            "text": self._clean_text(m1_val.get_text(" ", strip=True) if m1_val else None)
        })

        # BIST Indices that the Company is Included
        m2_title = soup.select_one(base_sel + " > div > div > div > div > div > div:nth-child(1) > div:nth-child(2) > div > div > span")
        m2_val = soup.select_one(base_sel + " > div > div > div > div > div > div:nth-child(1) > div:nth-child(2) > div > span")
        out["subsections"].append({
            "content_type": "text",
            "title": self._clean_text(m2_title.get_text(strip=True) if m2_title else "BIST Indices that the Company is Included"),
            "text": self._clean_text(m2_val.get_text(" ", strip=True) if m2_val else None)
        })

        # Current List of Other Exchanges or Organized Markets ... (table)
        m3_title = soup.select_one(base_sel + " > div > div > div > div > div > div:nth-child(2) > div > div.flex.items-center.justify-between.py-4.company__sgbf-h6-title > div.font-semibold.text-sm.text-danger")
        m3_table = soup.select_one(base_sel + " > div > div > div > div > div > div:nth-child(2) > div > div.overflow-x-auto.w-full > table")
        m3_title_text = self._clean_text(m3_title.get_text(strip=True) if m3_title else "Current List of Other Exchanges or Organized Markets where the Company's Capital Market Instruments are Listed or Traded")
        out["subsections"].append({
            "content_type": "table",
            "title": m3_title_text,
            "table": self._apply_table_schema(self._parse_table(m3_table), m3_title_text)
        })

        # Information About Issued Capital Market Instruments Other Than Shares (text)
        m4_title = soup.select_one(base_sel + " > div > div > div > div > div > div:nth-child(3) > div > div > div.font-semibold.text-sm.text-danger")
        m4_val = soup.select_one(base_sel + " > div > div > div > div > div > div:nth-child(3) > div > span")
        out["subsections"].append({
            "content_type": "text",
            "title": self._clean_text(m4_title.get_text(strip=True) if m4_title else "Information About Issued Capital Market Instruments Other Than Shares"),
            "text": self._clean_text(m4_val.get_text(" ", strip=True) if m4_val else None)
        })
        return out

    def _parse_registration_tax(self, soup: BeautifulSoup) -> Optional[dict]:
        base_sel = "#general > div > div > div:nth-child(5)"
        out = {"section_key": "registration_tax", "title": "REGISTRATION AND TAX OFFICE INFORMATION", "subsections": []}
        fields = [
            ("Registry Office", 1, self._clean_text),
            ("Registration Date", 2, self._parse_date_ddmmyyyy),
            ("Registration Number", 3, self._parse_int),
            ("Tax Number", 4, self._parse_int),
            ("Tax Office", 5, self._clean_text),
        ]
        for title, idx, fn in fields:
            t_node = soup.select_one(f"{base_sel} > div > div > div > div > div > div > div:nth-child({idx}) > div > div > span")
            v_node = soup.select_one(f"{base_sel} > div > div > div > div > div > div > div:nth-child({idx}) > div > span")
            raw = v_node.get_text(" ", strip=True) if v_node else None
            out["subsections"].append({
                "content_type": "text",
                "title": self._clean_text(t_node.get_text(strip=True) if t_node else title),
                "text": fn(raw) if fn else self._clean_text(raw)
            })
        return out

    def _parse_company_management(self, soup: BeautifulSoup) -> Optional[dict]:
        base_sel = "#general > div > div > div:nth-child(6)"
        out = {"section_key": "company_management", "title": "COMPANY MANAGEMENT", "subsections": []}
        # Board Members (table)
        b_title = soup.select_one(base_sel + " > div > div > div > div > div > div:nth-child(1) > div > div.flex.items-center.justify-between.py-4.company__sgbf-h6-title > div.font-semibold.text-sm.text-danger")
        b_table = soup.select_one(base_sel + " > div > div > div > div > div > div:nth-child(1) > div > div.overflow-x-auto.w-full > table")
        b_title_text = self._clean_text(b_title.get_text(strip=True) if b_title else "Board Members")
        out["subsections"].append({
            "content_type": "table",
            "title": b_title_text,
            "table": self._apply_table_schema(self._parse_table(b_table), b_title_text)
        })
        # Top Management (table)
        t_title = soup.select_one(base_sel + " > div > div > div > div > div > div:nth-child(2) > div > div.flex.items-center.justify-between.py-4.company__sgbf-h6-title > div.font-semibold.text-sm.text-danger")
        t_table = soup.select_one(base_sel + " > div > div > div > div > div > div:nth-child(2) > div > div.overflow-x-auto.w-full > table")
        t_title_text = self._clean_text(t_title.get_text(strip=True) if t_title else "Top Management")
        out["subsections"].append({
            "content_type": "table",
            "title": t_title_text,
            "table": self._apply_table_schema(self._parse_table(t_table), t_title_text)
        })
        return out

    def _parse_capital_shareholders(self, soup: BeautifulSoup) -> Optional[dict]:
        base_sel = "#general > div > div > div:nth-child(7)"
        out = {"section_key": "capital_shareholders", "title": "CAPITAL AND SHAREHOLDER STRUCTURE", "subsections": []}
        # Paid-in/Issued Capital (int)
        p_title = soup.select_one(base_sel + " > div > div > div > div > div > div:nth-child(1) > div:nth-child(1) > div > div > span")
        p_val = soup.select_one(base_sel + " > div > div > div > div > div > div:nth-child(1) > div:nth-child(1) > div > span")
        out["subsections"].append({
            "content_type": "text",
            "title": self._clean_text(p_title.get_text(strip=True) if p_title else "Paid-in/Issued Capital"),
            "text": self._parse_int(p_val.get_text(" ", strip=True) if p_val else None)
        })
        # Authorized Capital (int)
        a_title = soup.select_one(base_sel + " > div > div > div > div > div > div:nth-child(1) > div:nth-child(2) > div > div > span")
        a_val = soup.select_one(base_sel + " > div > div > div > div > div > div:nth-child(1) > div:nth-child(2) > div > span")
        out["subsections"].append({
            "content_type": "text",
            "title": self._clean_text(a_title.get_text(strip=True) if a_title else "Authorized Capital"),
            "text": self._parse_int(a_val.get_text(" ", strip=True) if a_val else None)
        })
        # Breakdown of Shareholders Holding More Than 5% ... (table)
        sh_title = soup.select_one(base_sel + " > div > div > div > div > div > div:nth-child(2) > div > div.flex.items-center.justify-between.py-4.company__sgbf-h6-title > div.font-semibold.text-sm.text-danger")
        sh_table = soup.select_one(base_sel + " > div > div > div > div > div > div:nth-child(2) > div > div.overflow-x-auto.w-full > table")
        sh_title_text = self._clean_text(sh_title.get_text(strip=True) if sh_title else "Breakdown of Shareholders Holding More Than 5% of the Capital and Voting Rights")
        sh = {"content_type": "table", "title": sh_title_text,
              "table": self._apply_table_schema(self._parse_table(sh_table), sh_title_text)}
        out["subsections"].append(sh)

        # Current Breakdown of Indirect Shareholders (text)
        ib_title = soup.select_one(base_sel + " > div > div > div > div > div > div:nth-child(4) > div > div > div.font-semibold.text-sm.text-danger")
        ib_val = soup.select_one(base_sel + " > div > div > div > div > div > div:nth-child(4) > div > span")
        out["subsections"].append({
            "content_type": "text",
            "title": self._clean_text(ib_title.get_text(strip=True) if ib_title else "Current Breakdown of Indirect Shareholders"),
            "text": self._clean_text(ib_val.get_text(" ", strip=True) if ib_val else None)
        })

        # Actual Shares Outstanding (table)
        aso_title = soup.select_one(base_sel + " > div > div > div > div > div > div:nth-child(5) > div > div.flex.items-center.justify-between.py-4.company__sgbf-h6-title > div.font-semibold.text-sm.text-danger, "
                                     + base_sel + " > div > div > div > div > div > div:nth-child(5) > div > div.flex.items-center.justify-between.py-4.company__sgbf-h6-title > div.font-semibold.text-sm.text-danger")
        aso_table = soup.select_one(base_sel + " > div > div > div > div > div > div:nth-child(5) > div > div.overflow-x-auto.w-full > table")
        aso_title_text = self._clean_text(aso_title.get_text(strip=True) if aso_title else "Actual Shares Outstanding")
        out["subsections"].append({
            "content_type": "table",
            "title": aso_title_text,
            "table": self._apply_table_schema(self._parse_table(aso_table), aso_title_text)
        })

        # Information About Shares Representing the Capital (table)
        isrc_title = soup.select_one(base_sel + " > div > div > div > div > div > div:nth-child(7) > div > div.flex.items-center.justify-between.py-4.company__sgbf-h6-title > div.font-semibold.text-sm.text-danger")
        isrc_table = soup.select_one(base_sel + " > div > div > div > div > div > div:nth-child(7) > div > div.overflow-x-auto.w-full > table")
        isrc_title_text = self._clean_text(isrc_title.get_text(strip=True) if isrc_title else "Information About Shares Representing the Capital")
        out["subsections"].append({
            "content_type": "table",
            "title": isrc_title_text,
            "table": self._apply_table_schema(self._parse_table(isrc_table), isrc_title_text)
        })
        return out

    def _parse_subsidiaries(self, soup: BeautifulSoup) -> Optional[dict]:
        base_sel = "#general > div > div > div:nth-child(8)"
        out = {"section_key": "subsidiaries_investments", "title": "SUBSIDIARIES, FINANCIAL NON-CURRENT ASSETS AND FINANCIAL INVESTMENTS", "subsections": []}
        s_title = soup.select_one(base_sel + " > div > div > div > div > div > div > div > div.flex.items-center.justify-between.py-4.company__sgbf-h6-title > div.font-semibold.text-sm.text-danger")
        s_table = soup.select_one(base_sel + " > div > div > div > div > div > div > div > div.overflow-x-auto.w-full > table")
        s_title_text = self._clean_text(s_title.get_text(strip=True) if s_title else "Subsidiaries, Financial Non-Current Assets and Financial Investments")
        out["subsections"].append({
            "content_type": "table",
            "title": s_title_text,
            "table": self._apply_table_schema(self._parse_table(s_table), s_title_text)
        })
        return out

    def _parse_miscellaneous(self, soup: BeautifulSoup) -> Optional[dict]:
        base_sel = "#general > div > div > div:nth-child(9)"
        out = {"section_key": "miscellaneous", "title": "MISCELLANEOUS", "subsections": []}
        m_title = soup.select_one(base_sel + " > div > div > div > div > div > div > div > div > div > span")
        m_val = soup.select_one(base_sel + " > div > div > div > div > div > div > div > div > span")
        out["subsections"].append({
            "content_type": "text",
            "title": self._clean_text(m_title.get_text(strip=True) if m_title else "Miscellaneous"),
            "text": self._clean_text(m_val.get_text(" ", strip=True) if m_val else None)
        })
        return out

    def parse_general_page(self, url: str) -> dict:
        """
        Parse the general info page to a structured, hierarchical JSON-friendly dict
        using only the given general 'detail_url'. All empty values become None.
        """
        soup = self._get_general_soup_and_expand(url)
        entry_errors: List[str] = []
        if not soup:
            return {"detail_url": url, "fetched_at": datetime.utcnow().isoformat() + "Z", "sections": [], "errors": ["Failed to load page"]}

        sections = []
        try:
            sections.append(self._parse_contact_information(soup))
        except Exception as e:
            msg = f"Contact information parse error: {e}"
            print(msg)
            entry_errors.append(msg)
        try:
            sections.append(self._parse_scope_and_audit(soup))
        except Exception as e:
            msg = f"Scope & audit parse error: {e}"
            print(msg)
            entry_errors.append(msg)
        try:
            sections.append(self._parse_markets_indices(soup))
        except Exception as e:
            msg = f"Markets & indices parse error: {e}"
            print(msg)
            entry_errors.append(msg)
        try:
            sections.append(self._parse_registration_tax(soup))
        except Exception as e:
            msg = f"Registration & tax parse error: {e}"
            print(msg)
            entry_errors.append(msg)
        try:
            sections.append(self._parse_company_management(soup))
        except Exception as e:
            msg = f"Company management parse error: {e}"
            print(msg)
            entry_errors.append(msg)
        try:
            sections.append(self._parse_capital_shareholders(soup))
        except Exception as e:
            msg = f"Capital & shareholder parse error: {e}"
            print(msg)
            entry_errors.append(msg)
        try:
            sections.append(self._parse_subsidiaries(soup))
        except Exception as e:
            msg = f"Subsidiaries parse error: {e}"
            print(msg)
            entry_errors.append(msg)
        try:
            sections.append(self._parse_miscellaneous(soup))
        except Exception as e:
            msg = f"Miscellaneous parse error: {e}"
            print(msg)
            entry_errors.append(msg)

        result = {
            "detail_url": url,
            "fetched_at": datetime.utcnow().isoformat() + "Z",
            "sections": [s for s in sections if s],
        }
        if entry_errors:
            result["errors"] = entry_errors
        return result

    def export_general_pages_structured_to_json(self, output_path: str, limit: int = 10) -> str:
        """
        Use only companies' detail_url (switching 'ozet' to 'genel'), parse the general
        page into a hierarchical JSON structure, and export for the first `limit` companies.
        """
        results = []
        companies = self.get_companies_list()
        if not companies:
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump([], f, ensure_ascii=False, indent=2)
            return output_path

        print(f"Parsing structured data for first {limit if limit > 0 else 'ALL'} companies...")
        for idx, company in enumerate(companies[:max(0, limit)] if limit > 0 else companies, start=1):
            try:
                detail_url = str(company.detail_url)
                general_url = detail_url.replace("ozet", "genel") if "ozet" in detail_url else detail_url
                # parse structured
                page_content = self.parse_general_page(general_url)
                # Build entry with code and name first
                entry = {
                    "code": company.code,
                    "name": company.name,
                    **page_content,
                }
                results.append(entry)
                total = len(companies) if limit <= 0 else min(limit, len(companies))
                print(f"[{idx}/{total}] Parsed: {general_url}")
            except Exception as e:
                msg = f"Error parsing company at {company.detail_url}: {e}"
                print(msg)
                results.append({
                    "code": company.code,
                    "name": company.name,
                    "detail_url": str(company.detail_url),
                    "fetched_at": datetime.utcnow().isoformat() + "Z",
                    "sections": [],
                    "errors": [msg]
                })

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        print(f"Structured JSON exported to {output_path}")
        return output_path

    def export_general_pages_to_json(self, output_path: str) -> str:
        """
        Fetch the companies list, visit each company's general info page
        (by replacing 'ozet' with 'genel' in the detail URL when applicable),
        capture the full page HTML and extracted text, and write everything to
        a single JSON file at output_path.

        The JSON structure is an array of entries like:
        {
            "company": { CompanySummary fields },
            "general_page": { "fetched_url", "html", "text", "fetched_at" }
        }
        """
        results = []
        companies = self.get_companies_list()
        if not companies:
            print("No companies found. Skipping export.")
            # Still write an empty JSON array for determinism
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump([], f, ensure_ascii=False, indent=2)
            return output_path

        print("\nFetching general pages for each company...")
        for idx, company in enumerate(companies, start=1):
            try:
                detail_url = str(company.detail_url)
                # Prefer 'genel' page if the URL includes 'ozet'. Otherwise try appending '/genel' conservatively.
                if "ozet" in detail_url:
                    general_url = detail_url.replace("ozet", "genel")
                else:
                    # In case detail_url is like .../sirket-bilgileri/ozet missing, keep as-is
                    general_url = detail_url

                content = self._fetch_page_content(general_url)
                if not content and general_url != detail_url:
                    # Fallback to the original detail URL if replacing failed
                    content = self._fetch_page_content(detail_url)

                entry = {
                    "company": company.model_dump(mode="json"),
                    "general_page": content if content else {
                        "fetched_url": general_url,
                        "html": None,
                        "text": None,
                        "fetched_at": datetime.utcnow().isoformat() + "Z",
                        "error": "Failed to fetch content"
                    }
                }
                results.append(entry)
                # Lightweight progress update
                if idx % 10 == 0:
                    print(f"Processed {idx}/{len(companies)} companies...")
            except Exception as e:
                print(f"Error while processing company {company.code}: {e}")

        # Write to file
        try:
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(results, f, ensure_ascii=False, indent=2)
            print(f"\nExported {len(results)} company general pages to: {output_path}")
        except Exception as e:
            print(f"Failed to write JSON output to {output_path}: {e}")
        return output_path

    def close(self):
        """Closes the Selenium WebDriver only if it's not a shared instance."""
        if self.driver and not self._shared_driver:
            self.driver.quit()

# --- Main Execution Block ---

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="KAP Companies Exporters")
    sub = parser.add_subparsers(dest="cmd", required=False)

    # legacy general exporters
    p_gen = sub.add_parser("general", help="Export general pages (structured or raw)")
    p_gen.add_argument("--mode", choices=["structured", "raw"], default="structured")
    p_gen.add_argument("--limit", type=int, default=0)
    p_gen.add_argument("--output", default="kap_companies_general_info.json")

    # companies list exporter
    p_comp = sub.add_parser("companies", help="Export companies list JSON (for persist_cli companies)")
    p_comp.add_argument("--output", default="companies.json")
    p_comp.add_argument("--print", action="store_true")

    # general export + persist wrapper
    p_gen_persist = sub.add_parser("general-persist", help="Export general (structured) and persist via persist_cli")
    p_gen_persist.add_argument("--output", default="kap_companies_general_info.json")
    p_gen_persist.add_argument("--limit", type=int, default=0)
    p_gen_persist.add_argument("--dry-run", action="store_true")
    p_gen_persist.add_argument("--batch-size", type=int, default=0)

    # default for backward-compat: general structured
    parser.add_argument("--output", help=argparse.SUPPRESS)
    parser.add_argument("--mode", help=argparse.SUPPRESS)
    parser.add_argument("--limit", help=argparse.SUPPRESS)

    args = parser.parse_args()

    driver_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '.', 'chromedriver'))
    api = KAPCompaniesAPI(driver_path=driver_path)
    if not api.driver:
        sys.exit(1)
    try:
        # Backward compatible path if no subcommand given
        if not args.cmd:
            out = getattr(args, "output", None) or "kap_companies_general_info.json"
            limit = int(getattr(args, "limit", 0) or 0)
            mode = getattr(args, "mode", None) or "structured"
            output_file = os.path.abspath(os.path.join(os.path.dirname(__file__), out))
            if mode == "structured":
                print(f"Starting structured export of general pages ({'all' if limit == 0 else f'first {limit}'} companies)...")
                api.export_general_pages_structured_to_json(output_file, limit=limit)
            else:
                print(f"Starting RAW export of general pages ({'all' if limit == 0 else f'first {limit}'} companies)...")
                api.export_general_pages_to_json(output_file)
        elif args.cmd == "companies":
            companies = api.get_companies_list()
            payload = [c.model_dump(mode="json") for c in companies]
            if args.print:
                print(json.dumps(payload, ensure_ascii=False, indent=2))
            out = os.path.abspath(os.path.join(os.path.dirname(__file__), args.output))
            with open(out, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False, indent=2)
            print(f"Companies JSON exported to {out}")
        elif args.cmd == "general":
            out = os.path.abspath(os.path.join(os.path.dirname(__file__), args.output))
            if args.mode == "structured":
                print(f"Starting structured export of general pages ({'all' if args.limit == 0 else f'first {args.limit}'} companies)...")
                api.export_general_pages_structured_to_json(out, limit=args.limit)
            else:
                print(f"Starting RAW export of general pages ({'all' if args.limit == 0 else f'first {args.limit}'} companies)...")
                api.export_general_pages_to_json(out)
        elif args.cmd == "general-persist":
            out = os.path.abspath(os.path.join(os.path.dirname(__file__), args.output))
            print(f"Exporting structured general info to {out} ...")
            api.export_general_pages_structured_to_json(out, limit=args.limit)
            # Persist via persist_cli
            try:
                from persist_cli import persist_general
                print("Persisting exported general info...")
                persist_general(out, dry_run=args.dry_run, limit=0, batch_size=args.batch_size)
            except Exception as e:
                print(f"Persist step failed: {e}")
                sys.exit(2)
        else:
            print("Unknown command")
            sys.exit(2)
    finally:
        print("Closing Selenium driver...")
        api.close()