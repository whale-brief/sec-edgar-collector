import requests
import xml.etree.ElementTree as ET
import json
import os
from datetime import datetime
from dotenv import load_dotenv

class SecEdgarCollector:
    def __init__(self, user_agent):
        """
        SEC API는 엄격한 User-Agent를 요구합니다.
        형식: '회사명/프로젝트명 (이메일)'
        """
        self.headers = {
            "User-Agent": user_agent,
            "Accept-Encoding": "gzip, deflate"
        }
        # Form 4(내부자 거래) 최신 문서를 가져오는 SEC 기본 Atom Feed URL
        self.target_url = "https://www.sec.gov/cgi-bin/browse-edgar?action=getcurrent&type=4&output=atom"

    def fetch_latest_form4(self):
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] SEC EDGAR Form 4 데이터 수집을 시작합니다...")
        
        try:
            response = requests.get(self.target_url, headers=self.headers, timeout=10)
            response.raise_for_status() # HTTP 에러 발생 시 예외 처리
            
            return self._parse_atom_feed(response.content)
            
        except requests.exceptions.RequestException as e:
            print(f"Error: SEC API 호출 중 문제가 발생했습니다: {e}")
            return []

    def _parse_atom_feed(self, xml_content):
        """
        SEC에서 응답한 XML(Atom Feed)을 파싱하여 AI가 읽기 좋은 JSON 구조로 정제합니다.
        """
        root = ET.fromstring(xml_content)
        namespace = {'atom': 'http://www.w3.org/2005/Atom'}
        
        filings = []
        
        for entry in root.findall('atom:entry', namespace):
            title = entry.find('atom:title', namespace).text
            summary = entry.find('atom:summary', namespace).text
            link = entry.find('atom:link', namespace).attrib['href']
            updated = entry.find('atom:updated', namespace).text
            
            # Form 4 공시만 필터링 및 데이터 객체화
            if "4 -" in title:
                filing_data = {
                    "title": title,
                    "summary": summary.strip() if summary else "",
                    "link": link,
                    "filed_at": updated,
                    "raw_data_type": "Form 4 (Insider Trading)"
                }
                filings.append(filing_data)
                
        return filings

if __name__ == "__main__":
    # 로컬 디렉토리의 .env 파일을 찾아 환경변수로 로드
    load_dotenv()
    
    # 환경변수에서 값 가져오기
    USER_AGENT = os.getenv("SEC_USER_AGENT")
    
    # 환경변수가 없을 경우의 안전장치(Fail-fast)
    if not USER_AGENT:
        raise ValueError("환경변수 'SEC_USER_AGENT'가 설정되지 않았습니다. .env 파일이나 시스템 환경변수를 확인해주세요.")
    
    collector = SecEdgarCollector(user_agent=USER_AGENT)
    latest_data = collector.fetch_latest_form4()
    
    print(json.dumps(latest_data[:5], indent=4, ensure_ascii=False))
    print(f"\n총 {len(latest_data)}건의 최신 Form 4 공시를 성공적으로 파싱했습니다.")