import os
import logging
from dotenv import load_dotenv
from src.collector import SecEdgarCollector
from src.finra_collector import FinraDarkpoolCollector
from src.db_manager import NeonDBManager
from src.ai_analyzer import WhaleBriefAIAnalyzer # 💡 AI 모듈 추가

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')

def run_pipeline():
    load_dotenv()
    user_agent = os.getenv("SEC_USER_AGENT")
    
    sec_collector = SecEdgarCollector(user_agent=user_agent)
    finra_collector = FinraDarkpoolCollector()
    db_manager = NeonDBManager()
    ai_analyzer = WhaleBriefAIAnalyzer() # 💡 AI 인스턴스화

    logging.info("=== Starting Whale-Brief ETL Multi-Pipeline ===")
    
    # ---------------------------------------------------------
    # 1. SEC 공시 데이터 파이프라인 (Overhang / Insider Tracking)
    # ---------------------------------------------------------
    logging.info(">> [Job 1] SEC EDGAR Filings (Fetching latest Delta)")
    sec_data = sec_collector.fetch_latest_form4(limit=200)
    if sec_data:
        db_manager.insert_sec_filings(sec_data)
        
    # ---------------------------------------------------------
    # 2. FINRA 다크풀 데이터 파이프라인 (Smart Money Tracking
    # ---------------------------------------------------------
    logging.info(">> [Job 2] FINRA Darkpool & Short Volume (Bulk Load)")
    finra_data = finra_collector.fetch_daily_data() 
    if finra_data:
        db_manager.insert_finra_darkpool(finra_data)

    # ---------------------------------------------------------
    # 3. AI 인텔리전스 레이어 (Transform / AI Mashing)
    # ---------------------------------------------------------
    logging.info(">> [Job 3] Multi-Agent AI Analysis (Reasoning & Formatting)")
    ai_analyzer.process_pending_filings()

    logging.info("=== All Pipelines & AI Analysis Execution Finished ===")

if __name__ == "__main__":
    run_pipeline()