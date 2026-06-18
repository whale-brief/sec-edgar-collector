import os
import logging
from dotenv import load_dotenv
from src.collector import SecEdgarCollector
from src.finra_collector import FinraDarkpoolCollector
from src.db_manager import NeonDBManager
from src.ai_analyzer import WhaleBriefAIAnalyzer

# Configure logging for production tracing
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')

def run_pipeline() -> None:
    """
    Executes the End-to-End (E2E) ETL and AI analysis pipeline.
    1. Extracts delta filings from SEC EDGAR.
    2. Extracts bulk darkpool data from FINRA.
    3. Loads transformed data into PostgreSQL (NeonDB).
    4. Triggers Multi-Agent LLMs to reason and format localized risk reports.
    """
    load_dotenv()
    user_agent = os.getenv("SEC_USER_AGENT")
    
    if not user_agent:
        logging.error("SEC_USER_AGENT is not set. Aborting pipeline.")
        return

    # Initialize modules
    sec_collector = SecEdgarCollector(user_agent=user_agent)
    finra_collector = FinraDarkpoolCollector()
    db_manager = NeonDBManager()
    ai_analyzer = WhaleBriefAIAnalyzer()

    logging.info("=== Starting Whale-Brief ETL Multi-Pipeline ===")
    
    # ---------------------------------------------------------
    # Job 1: SEC EDGAR Filings (Overhang / Insider Tracking)
    # ---------------------------------------------------------
    logging.info(">> [Job 1] SEC EDGAR Filings (Fetching latest Delta)")
    sec_data = sec_collector.fetch_latest_form4(limit=200)
    if sec_data:
        db_manager.insert_sec_filings(sec_data)
        
    # ---------------------------------------------------------
    # Job 2: FINRA Darkpool & Short Volume (Smart Money Tracking)
    # ---------------------------------------------------------
    logging.info(">> [Job 2] FINRA Darkpool & Short Volume (Bulk Load)")
    finra_data = finra_collector.fetch_daily_data() 
    if finra_data:
        db_manager.insert_finra_darkpool(finra_data)

    # ---------------------------------------------------------
    # Job 3: AI Intelligence Layer (Transform via LLM Mashing)
    # ---------------------------------------------------------
    logging.info(">> [Job 3] Multi-Agent AI Analysis (Reasoning & Formatting)")
    ai_analyzer.process_pending_filings()

    logging.info("=== All Pipelines & AI Analysis Execution Finished ===")

if __name__ == "__main__":
    run_pipeline()