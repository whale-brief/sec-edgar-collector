import requests
import xml.etree.ElementTree as ET
import re
import time
import logging
from bs4 import BeautifulSoup
from typing import List, Dict, Optional, Any, Set
from src.webhook_client import webhook_client

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')

class SecEdgarCollector:
    """
    Multi-form SEC EDGAR monitoring engine.
    Strictly adheres to SEC rate limits (max 10 requests/second).
    Features advanced HTML-to-Text extraction for LLM summarization.
    """
    def __init__(self, user_agent: str) -> None:
        self.headers = {
            "User-Agent": user_agent,
            "Accept-Encoding": "gzip, deflate"
        }
        self.base_url = "https://www.sec.gov/cgi-bin/browse-edgar"
        self.seen_filing_links: Set[str] = set()
        
        # 🛡️ ANTI-BLOCK MECHANISM 🛡️
        # Polling cycle interval for the SEC RSS feed.
        self.feed_poll_interval = 120 

        # 🎯 Target forms for the Whale-Brief service
        self.target_forms = ["4", "8-K", "6-K", "13D", "13G", "S-1", "S-3", "424B5"]

    def run_continuous_watcher(self) -> None:
        """Iterates through all target forms and monitors the feed."""
        logging.info(f"🚀 SEC Watcher Started. Targets: {', '.join(self.target_forms)}")
        
        while True:
            for form in self.target_forms:
                self._poll_and_process(form)
            
            logging.info(f"💤 Cycle complete. Sleeping for {self.feed_poll_interval} seconds...")
            time.sleep(self.feed_poll_interval)

    def _poll_and_process(self, form_type: str) -> None:
        params = {"action": "getcurrent", "type": form_type, "output": "atom"}
        
        try:
            response = requests.get(self.base_url, params=params, headers=self.headers, timeout=10)
            response.raise_for_status()
            
            basic_filings = self._parse_atom_feed(response.text, form_type)
            new_filings_count = 0
            
            for filing in basic_filings:
                filing_link = filing['link']
                
                if filing_link in self.seen_filing_links:
                    continue
                    
                new_filings_count += 1
                self.seen_filing_links.add(filing_link)
                
                # SEC allows max 10 req/sec. 0.15s sleep limits us to ~6.6 req/sec.
                time.sleep(0.15) 
                
                detail = self._dispatch_parser(filing_link, form_type)
                
                if detail:
                    detail['raw_link'] = filing_link
                    detail['filing_title'] = filing['title']
                    webhook_client.send("sec-filing", detail)
            
            if new_filings_count > 0:
                logging.info(f"📄 Form {form_type}: Dispatched {new_filings_count} new filings.")

            if len(self.seen_filing_links) > 5000:
                self.seen_filing_links.clear()

        except Exception as e:
            logging.error(f"❌ Network error (Form {form_type}): {e}")

    def _parse_atom_feed(self, xml_content: str, target_form: str) -> List[Dict[str, str]]:
        """Extracts filing titles and index links from the Atom feed."""
        try:
            root = ET.fromstring(xml_content)
            namespace = {'atom': 'http://www.w3.org/2005/Atom'}
            filings = []
            
            for entry in root.findall('atom:entry', namespace):
                title_elem = entry.find('atom:title', namespace)
                link_elem = entry.find('atom:link', namespace)
                
                if title_elem is not None and link_elem is not None:
                    title = title_elem.text or ""
                    # Ensure exact match (e.g., "8-K -" to avoid matching "10-Q/A")
                    if f"{target_form} -" in title:
                        filings.append({
                            "title": title,
                            "link": link_elem.attrib.get('href', '')
                        })
            return filings
        except ET.ParseError as e:
            logging.error(f"❌ Failed to parse Atom feed: {e}")
            return []

    def _dispatch_parser(self, index_link: str, form_type: str) -> Optional[Dict[str, Any]]:
        """Routes the link to the appropriate parser based on form type."""
        if form_type == "4":
            return self._parse_form_4(index_link)
        elif form_type in ["8-K", "6-K", "13D", "13G", "S-1", "S-3", "424B5"]:
            # For unstructured or complex forms, we extract clean text for the LLM
            return self._extract_clean_text_for_llm(index_link, form_type)
        return None

    def _parse_form_4(self, index_link: str) -> Optional[Dict[str, Any]]:
        """Extracts structured XML data specifically for Form 4."""
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
                "shares_traded": float(shares_str) if shares_str.replace('.', '', 1).isdigit() else 0.0,
                "transaction_type": tx_type
            }
        except Exception as e:
            logging.error(f"❌ Form 4 XML Parsing Error: {e}")
            return None

    def _extract_clean_text_for_llm(self, index_link: str, form_type: str) -> Optional[Dict[str, Any]]:
        """
        Advanced text extraction for unstructured forms (e.g., 8-K).
        Strips out HTML tables, scripts, and CSS to provide pure context for the API Server's LLM.
        """
        raw_text_link = index_link.replace("-index.htm", ".txt")
        try:
            response = requests.get(raw_text_link, headers=self.headers, timeout=15)
            response.raise_for_status()
            
            # Attempt to extract Ticker from the header metadata
            ticker_match = re.search(r'COMPANY CONFORMED NAME:\s+(.*?)\s+CENTRAL INDEX KEY:', response.text)
            ticker = "UNKNOWN"
            # Extract Trading Symbol if available in metadata
            symbol_match = re.search(r'TRADING SYMBOL:\s+([A-Za-z]+)', response.text)
            if symbol_match:
                ticker = symbol_match.group(1).upper()
            
            # Isolate the main HTML document to avoid parsing attachments
            html_match = re.search(r'<DOCUMENT>\s*<TYPE>([^\n]+).*?<TEXT>(.*?)</TEXT>', response.text, re.DOTALL | re.IGNORECASE)
            
            if html_match:
                html_content = html_match.group(2)
                soup = BeautifulSoup(html_content, 'html.parser')
                
                # 🧹 CLEANUP LOGIC 🧹
                # Remove scripts, styles, and data tables (tables confuse LLMs and consume massive tokens)
                for element in soup(["script", "style", "table"]):
                    element.decompose()
                
                # Extract text and compress multiple newlines/spaces
                clean_text = soup.get_text(separator=' ', strip=True)
                clean_text = re.sub(r'\s+', ' ', clean_text)
            else:
                # Fallback if no specific <TEXT> tags are found
                clean_text = re.sub(r'<[^>]+>', ' ', response.text)
                clean_text = re.sub(r'\s+', ' ', clean_text)
            
            # Cap the text length to prevent LLM token overflow (approx 30,000 chars)
            final_text = clean_text[:30000]
            
            return {
                "ticker": ticker,
                "form_type": form_type,
                "raw_text": final_text
            }
            
        except Exception as e:
            logging.error(f"❌ Text Extraction Error (Form {form_type}): {e}")
            return None

if __name__ == "__main__":
    # SEC REQUIRES a valid User-Agent
    USER_AGENT = "WhaleBrief DataCrawler (admin@whalebrief.com)"
    collector = SecEdgarCollector(user_agent=USER_AGENT)
    collector.run_continuous_watcher()