import os
import logging
from dotenv import load_dotenv
from src.collector import SecEdgarCollector
from src.db_manager import NeonDBManager

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')

def run_pipeline():
    """
    Extract-Transform-Load (ETL) 파이프라인을 실행합니다.
    1. SEC EDGAR에서 데이터를 수집 및 파싱 (Extract & Transform)
    2. NeonDB에 중복 없이 안전하게 적재 (Load)
    """
    load_dotenv()
    
    # 1. 환경 변수 검증
    user_agent = os.getenv("SEC_USER_AGENT")
    if not user_agent:
        logging.error("SEC_USER_AGENT is not set in environment variables. Aborting.")
        return

    # 2. 클래스 인스턴스화
    collector = SecEdgarCollector(user_agent=user_agent)
    db_manager = NeonDBManager()

    # 3. 파이프라인 실행
    logging.info("--- Starting Whale-Brief ETL Pipeline ---")
    
    # Extract & Transform
    parsed_data = collector.fetch_latest_form4(limit=5)
    
    # Load
    if parsed_data:
        db_manager.insert_sec_filings(parsed_data)
    else:
        logging.warning("No data extracted. Skipping database load phase.")
        
    logging.info("--- Pipeline Execution Finished ---")

if __name__ == "__main__":
    run_pipeline()