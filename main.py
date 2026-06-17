import os
import logging
from dotenv import load_dotenv
from src.collector import SecEdgarCollector
from src.finra_collector import FinraDarkpoolCollector
from src.db_manager import NeonDBManager

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')

def run_pipeline():
    load_dotenv()
    user_agent = os.getenv("SEC_USER_AGENT")
    
    sec_collector = SecEdgarCollector(user_agent=user_agent)
    finra_collector = FinraDarkpoolCollector()
    db_manager = NeonDBManager()

    logging.info("=== Starting Whale-Brief ETL Multi-Pipeline ===")
    
    # ---------------------------------------------------------
    # 1. SEC 공시 데이터 파이프라인 (Overhang / Insider Tracking)
    # ---------------------------------------------------------
    logging.info(">> [Job 1] SEC EDGAR Filings")
    sec_data = sec_collector.fetch_latest_form4(limit=50)
    if sec_data:
        db_manager.insert_sec_filings(sec_data)
        
    # ---------------------------------------------------------
    # 2. FINRA 다크풀 데이터 파이프라인 (Smart Money Tracking)
    # ---------------------------------------------------------
    logging.info(">> [Job 2] FINRA Darkpool & Short Volume")
    # 주의: 오늘이 월요일이라면 주말 데이터가 없으므로 테스트를 위해 금요일 날짜를 강제 입력할 수 있습니다.
    # finra_data = finra_collector.fetch_daily_data(target_date="20240517") # 수동 날짜 테스트용
    finra_data = finra_collector.fetch_daily_data() 
    if finra_data:
        db_manager.insert_finra_darkpool(finra_data)

    logging.info("=== All ETL Pipelines Execution Finished ===")

if __name__ == "__main__":
    run_pipeline()