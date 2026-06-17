import requests
import xml.etree.ElementTree as ET
import re
import logging
from typing import List, Dict, Optional, Any

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')

class SecEdgarCollector:
    """
    SEC EDGAR 시스템에서 실시간으로 데이터를 수집하고 파싱하는 코어 엔진 (Extract & Transform).
    """
    def __init__(self, user_agent: str) -> None:
        self.headers = {
            "User-Agent": user_agent,
            "Accept-Encoding": "gzip, deflate"
        }
        self.base_url = "https://www.sec.gov/cgi-bin/browse-edgar"

    def fetch_latest_form4(self, limit: int = 5) -> List[Dict[str, Any]]:
        """최신 Form 4 공시 메타데이터를 수집하고 딥 파싱을 수행합니다."""
        logging.info("Initiating SEC EDGAR Form 4 Feed Extraction...")
        params = {"action": "getcurrent", "type": "4", "output": "atom"}
        
        try:
            response = requests.get(self.base_url, params=params, headers=self.headers, timeout=10)
            response.raise_for_status()
            
            basic_filings = self._parse_atom_feed(response.text)
            logging.info(f"Found {len(basic_filings)} filings. Deep parsing top {limit} items...")
            
            deep_parsed_data = []
            for filing in basic_filings[:limit]:
                detail = self._fetch_and_parse_form4_xml(filing['link'])
                if detail:
                    detail['raw_link'] = filing['link']
                    detail['filing_title'] = filing['title']
                    deep_parsed_data.append(detail)
                    
            logging.info(f"Extraction Complete: {len(deep_parsed_data)} successfully parsed.")
            return deep_parsed_data
            
        except requests.exceptions.RequestException as e:
            logging.error(f"Network error during SEC API call: {e}")
            return []

    def _parse_atom_feed(self, xml_content: str) -> List[Dict[str, str]]:
        try:
            root = ET.fromstring(xml_content)
            namespace = {'atom': 'http://www.w3.org/2005/Atom'}
            
            filings = []
            for entry in root.findall('atom:entry', namespace):
                title_elem = entry.find('atom:title', namespace)
                link_elem = entry.find('atom:link', namespace)
                
                if title_elem is not None and link_elem is not None:
                    title = title_elem.text or ""
                    if "4 -" in title:
                        filings.append({
                            "title": title,
                            "link": link_elem.attrib.get('href', '')
                        })
            return filings
        except ET.ParseError as e:
            logging.error(f"Failed to parse Atom feed XML: {e}")
            return []

    def _fetch_and_parse_form4_xml(self, index_link: str) -> Optional[Dict[str, Any]]:
        raw_text_link = index_link.replace("-index.htm", ".txt")
        
        try:
            response = requests.get(raw_text_link, headers=self.headers, timeout=10)
            response.raise_for_status()
            
            xml_match = re.search(r'<XML>(.*?)</XML>', response.text, re.DOTALL)
            if not xml_match:
                return None
                
            xml_content = xml_match.group(1).strip()
            xml_content = re.sub(r'\sxmlns="[^"]+"', '', xml_content)
            
            root = ET.fromstring(xml_content)
            ticker = root.findtext(".//issuerTradingSymbol", default="UNKNOWN")
            
            title = root.findtext(".//officerTitle") or ("Director" if root.findtext(".//isDirector") in ["true", "1"] else "Insider")
            
            transaction = root.find(".//nonDerivativeTransaction")
            if transaction is None:
                return None
                
            date_str = transaction.findtext(".//transactionDate/value", default="UNKNOWN")
            shares_str = transaction.findtext(".//transactionShares/value", default="0")
            acq_disp = transaction.findtext(".//transactionAcquiredDisposedCode/value", default="")
            
            tx_type = "Buy" if acq_disp == "A" else "Sell" if acq_disp == "D" else "Other"
            
            return {
                "ticker": ticker,
                "form_type": "4",
                "transaction_date": date_str,
                "insider_title": title,
                "shares_traded": float(shares_str) if shares_str.replace('.', '', 1).isdigit() else 0.0,
                "transaction_type": tx_type
            }
        except Exception as e:
            logging.error(f"Error parsing detail XML ({index_link}): {e}")
            return None