import requests
import xml.etree.ElementTree as ET
import json
import os
import re
from datetime import datetime
from dotenv import load_dotenv

class SecEdgarCollector:
    def __init__(self, user_agent):
        self.headers = {
            "User-Agent": user_agent,
            "Accept-Encoding": "gzip, deflate"
        }
        self.target_url = "https://www.sec.gov/cgi-bin/browse-edgar?action=getcurrent&type=4&output=atom"

    def fetch_latest_form4(self, limit=3):
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] SEC EDGAR 피드 수집 시작...")
        
        try:
            response = requests.get(self.target_url, headers=self.headers, timeout=10)
            response.raise_for_status()
            
            # 1단계: 메타데이터(껍데기) 수집
            basic_filings = self._parse_atom_feed(response.content)
            
            deep_parsed_data = []
            print(f"총 {len(basic_filings)}건의 공시 중 상위 {limit}건 딥 파싱 진행 중...")
            
            # 2단계: 실제 원문 링크 추적 및 알맹이 추출 (Deep Parsing)
            for filing in basic_filings[:limit]:
                detail = self._fetch_and_parse_form4_xml(filing['link'])
                if detail:
                    detail['raw_link'] = filing['link']
                    deep_parsed_data.append(detail)
                    
            return deep_parsed_data
            
        except requests.exceptions.RequestException as e:
            print(f"Error: SEC API 호출 중 문제가 발생했습니다: {e}")
            return []

    def _parse_atom_feed(self, xml_content):
        root = ET.fromstring(xml_content)
        namespace = {'atom': 'http://www.w3.org/2005/Atom'}
        
        filings = []
        for entry in root.findall('atom:entry', namespace):
            title = entry.find('atom:title', namespace).text
            link = entry.find('atom:link', namespace).attrib['href']
            
            if "4 -" in title:
                filings.append({
                    "title": title,
                    "link": link
                })
        return filings

    def _fetch_and_parse_form4_xml(self, index_link):
        # index.htm을 .txt로 변경하여 원문 요청
        raw_text_link = index_link.replace("-index.htm", ".txt")
        
        try:
            response = requests.get(raw_text_link, headers=self.headers, timeout=10)
            response.raise_for_status()
            
            # 정규식으로 순수 <XML> 블록 추출
            xml_match = re.search(r'<XML>(.*?)</XML>', response.text, re.DOTALL)
            if not xml_match:
                return None
                
            # 공백 및 줄바꿈 제거 (.strip()으로 파싱 에러 해결)
            xml_content = xml_match.group(1).strip()
            
            # 네임스페이스(xmlns)가 있으면 파싱 시 태그 조회가 까다로우므로 정규식으로 제거
            xml_content = re.sub(r'\sxmlns="[^"]+"', '', xml_content)
            
            root = ET.fromstring(xml_content)
            
            # 데이터 추출
            ticker = root.findtext(".//issuerTradingSymbol", default="UNKNOWN")
            
            title = "Insider"
            officer_title = root.findtext(".//officerTitle")
            is_director = root.findtext(".//isDirector")
            
            if officer_title:
                title = officer_title
            elif is_director in ["true", "1"]:
                title = "Director"
                
            transaction = root.find(".//nonDerivativeTransaction")
            if transaction is None:
                return None
                
            date = transaction.findtext(".//transactionDate/value", default="UNKNOWN")
            shares = transaction.findtext(".//transactionShares/value", default="0")
            acq_disp = transaction.findtext(".//transactionAcquiredDisposedCode/value", default="")
            
            tx_type = "Buy" if acq_disp == "A" else "Sell" if acq_disp == "D" else "Other"
            
            return {
                "ticker": ticker,
                "form_type": "4",
                "transaction_date": date,
                "insider_title": title,
                "shares_traded": float(shares) if shares.replace('.','',1).isdigit() else 0,
                "transaction_type": tx_type
            }
            
        except Exception as e:
            print(f"파싱 에러 ({index_link}): {e}")
            return None

if __name__ == "__main__":
    load_dotenv()
    
    USER_AGENT = os.getenv("SEC_USER_AGENT")
    if not USER_AGENT:
        raise ValueError("환경변수 'SEC_USER_AGENT'가 설정되지 않았습니다.")
    
    collector = SecEdgarCollector(user_agent=USER_AGENT)
    latest_data = collector.fetch_latest_form4(limit=3)
    
    print("\n[Deep Parsing 결과물]")
    print(json.dumps(latest_data, indent=4, ensure_ascii=False))