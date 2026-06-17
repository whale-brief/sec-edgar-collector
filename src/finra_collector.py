# src/finra_collector.py
import requests
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')

class FinraDarkpoolCollector:
    """
    FINRA 웹사이트에서 일별 Reg SHO (공매도 및 다크풀/장외거래) 데이터를
    다운로드하고 파싱하는 배치 수집기.
    """
    def __init__(self) -> None:
        self.base_url = "https://cdn.finra.org/equity/regsho/daily/"

    def fetch_daily_data(self, target_date: str = None) -> List[Dict[str, Any]]:
        """
        특정 날짜의 FINRA 데이터를 수집합니다. (기본값: 전일자)
        포맷: Date|Symbol|ShortVolume|ShortExemptVolume|TotalVolume|Market
        """
        # 타겟 날짜가 없으면 어제 날짜로 설정 (미국장 기준 새벽 배치용)
        if not target_date:
            yesterday = datetime.now() - timedelta(days=1)
            target_date = yesterday.strftime("%Y%m%d")

        filename = f"CNMSshvol{target_date}.txt"
        download_url = f"{self.base_url}{filename}"
        
        logging.info(f"Fetching FINRA Darkpool data for {target_date}...")
        
        try:
            response = requests.get(download_url, timeout=15)
            # 휴장일이거나 파일이 아직 안 올라온 경우 (404 Not Found 방어)
            if response.status_code == 404:
                logging.warning(f"FINRA data file not found for {target_date} (Likely weekend or holiday).")
                return []
                
            response.raise_for_status()
            
            lines = response.text.strip().split('\n')
            parsed_data = []
            
            # 첫 줄은 헤더이므로 생략 (인덱스 1부터 시작)
            for line in lines[1:]:
                parts = line.split('|')
                if len(parts) >= 5:
                    date_raw = parts[0]
                    ticker = parts[1]
                    short_vol = int(parts[2]) if parts[2].isdigit() else 0
                    total_vol = int(parts[4]) if parts[4].isdigit() else 0
                    
                    # 0으로 나누기 방지
                    dp_pct = round((short_vol / total_vol) * 100, 2) if total_vol > 0 else 0.0
                    
                    # Date 포맷 변환 (YYYYMMDD -> YYYY-MM-DD)
                    formatted_date = f"{date_raw[:4]}-{date_raw[4:6]}-{date_raw[6:]}"
                    
                    parsed_data.append({
                        "trading_date": formatted_date,
                        "ticker": ticker,
                        "darkpool_volume": total_vol, # TRF 장외 전체 거래량
                        "short_volume": short_vol,    # 공매도 거래량
                        "dp_percentage": dp_pct
                    })
                    
            logging.info(f"FINRA Extraction Complete: {len(parsed_data)} tickers processed.")
            return parsed_data
            
        except Exception as e:
            logging.error(f"Error fetching FINRA data: {e}")
            return []