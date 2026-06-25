import requests
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any
from src.webhook_client import webhook_client

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')

class FinraDarkpoolCollector:
    """
    Batch collector that downloads and parses daily Reg SHO 
    (Short Volume & Darkpool/Off-exchange) data from the FINRA website.
    """
    def __init__(self) -> None:
        self.base_url = "https://cdn.finra.org/equity/regsho/daily/"

    def fetch_daily_data(self, target_date: str = None) -> None:
        """
        Retrieves FINRA data for a specific date (defaults to yesterday).
        Expected raw format: Date|Symbol|ShortVolume|ShortExemptVolume|TotalVolume|Market
        """
        if not target_date:
            yesterday = datetime.now() - timedelta(days=1)
            target_date = yesterday.strftime("%Y%m%d")

        filename = f"CNMSshvol{target_date}.txt"
        download_url = f"{self.base_url}{filename}"
        
        logging.info(f"Fetching FINRA Darkpool data for {target_date}...")
        
        try:
            response = requests.get(download_url, timeout=15)
            
            # Graceful exit if data is not yet available (e.g., weekends/holidays)
            if response.status_code == 404:
                logging.warning(f"FINRA data file not found for {target_date} (Likely weekend or holiday).")
                return []
                
            response.raise_for_status()
            lines = response.text.strip().split('\n')
            parsed_data = []
            
            # Skip the header row
            for line in lines[1:]:
                parts = line.split('|')
                if len(parts) >= 5:
                    date_raw = parts[0]
                    ticker = parts[1]
                    short_vol = int(parts[2]) if parts[2].isdigit() else 0
                    total_vol = int(parts[4]) if parts[4].isdigit() else 0
                    
                    # Prevent ZeroDivisionError
                    dp_pct = round((short_vol / total_vol) * 100, 2) if total_vol > 0 else 0.0
                    
                    # Convert YYYYMMDD to YYYY-MM-DD
                    formatted_date = f"{date_raw[:4]}-{date_raw[4:6]}-{date_raw[6:]}"
                    
                    parsed_data.append({
                        "trading_date": formatted_date,
                        "ticker": ticker,
                        "darkpool_volume": total_vol,
                        "short_volume": short_vol,   
                        "dp_percentage": dp_pct
                    })
                    
            logging.info(f"FINRA Extraction Complete: {len(parsed_data)} tickers processed.")
            webhook_payload = {
                "date": target_date,
                "records": parsed_data
            }
            webhook_client.send("finra-batch", webhook_payload)
            
        except Exception as e:
            logging.error(f"Error fetching FINRA data: {e}")

if __name__ == "__main__":
    logging.info("🚀 Starting FINRA Darkpool Batch Job...")

    collector.fetch_and_send_daily_data()
    
    logging.info("✅ FINRA Darkpool Batch Job Finished.")