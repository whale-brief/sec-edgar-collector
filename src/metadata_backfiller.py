import os
import time
import logging
import requests
import psycopg2
import yfinance as yf
from psycopg2.extras import execute_batch
from dotenv import load_dotenv
from typing import Any, Dict

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')

class MetadataBackfiller:
    """
    Hybrid Metadata Backfiller with Continuous Batching & Rate Limit Defense.
    Safely processes 10,000+ records without triggering API IP bans or DB timeouts.
    """
    def __init__(self) -> None:
        load_dotenv()
        self.db_url = os.getenv("DATABASE_URL")
        self.user_agent = os.getenv("SEC_USER_AGENT")
        
        if not self.db_url or not self.user_agent:
            raise ValueError("DATABASE_URL or SEC_USER_AGENT is missing from environment variables.")

    def fetch_sec_cik_mapping(self) -> Dict[str, str]:
        """Downloads the official Ticker to CIK mapping JSON from the SEC EDGAR system."""
        logging.info("Downloading official SEC Ticker-CIK mapping data...")
        url = "https://www.sec.gov/files/company_tickers.json"
        headers = {"User-Agent": self.user_agent}
        
        try:
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            mapping = {}
            for item in data.values():
                mapping[item['ticker']] = str(item['cik_str']).zfill(10)
            
            logging.info(f"Successfully loaded {len(mapping)} CIK mappings from SEC.")
            return mapping
        except Exception as e:
            logging.error(f"Failed to fetch SEC CIK mapping: {e}")
            return {}

    def run_backfill(self, batch_size: int = 100) -> None:
        """Executes a continuous while-loop to process all remaining records in safe chunks."""
        logging.info("Starting Continuous Hybrid Metadata Enrichment Sequence...")
        
        # Load SEC mapping once in memory to avoid redundant large downloads
        sec_mapping = self.fetch_sec_cik_mapping()
        
        select_query = """
            SELECT ticker FROM companies 
            WHERE sector IS NULL 
               OR cik IS NULL 
               OR company_name LIKE '%%(Auto-added)%%'
            LIMIT %s;
        """
        
        update_query = """
            UPDATE companies 
            SET company_name = %s, sector = %s, cik = %s, updated_at = CURRENT_TIMESTAMP 
            WHERE ticker = %s;
        """

        total_processed = 0

        # 💡 [CORE ARCHITECTURE] Infinite loop until all empty profiles are filled
        while True:
            conn = None
            cursor = None
            try:
                # Open a fresh DB connection per batch to prevent long-running session drops
                conn = psycopg2.connect(self.db_url)
                cursor = conn.cursor()
                
                cursor.execute(select_query, (batch_size,))
                tickers_to_update = [row[0] for row in cursor.fetchall()]
                
                if not tickers_to_update:
                    logging.info(f"All company metadata is 100% up to date. Total processed: {total_processed}")
                    break # Graceful exit when query returns 0 rows

                logging.info(f"Fetched batch of {len(tickers_to_update)} companies. Commencing enrichment...")

                update_data = []
                for ticker in tickers_to_update:
                    try:
                        cik = sec_mapping.get(ticker, None)
                        stock = yf.Ticker(ticker)
                        info = stock.info
                        
                        if 'shortName' not in info and 'longName' not in info:
                            logging.warning(f"[{ticker}] Not found on YFinance. Tagging as Unknown/Delisted.")
                            update_data.append((f"{ticker} (UNKNOWN)", "UNKNOWN", cik, ticker))
                            continue

                        company_name = info.get('longName') or info.get('shortName', ticker)
                        quote_type = info.get('quoteType', '')

                        if quote_type in ['ETF', 'MUTUALFUND']:
                            sector = info.get('category') or 'ETF/Fund'
                        else:
                            sector = info.get('sector') or 'Other'
                        
                        update_data.append((company_name, sector, cik, ticker))
                        logging.info(f"Enriched: {ticker} -> {company_name} | Sector: {sector} | CIK: {cik}")
                        
                        # Micro-sleep to respect YFinance API limits
                        time.sleep(0.5) 
                        
                    except Exception as e:
                        logging.error(f"Failed to extract data for {ticker}: {e}")
                        update_data.append((f"{ticker} (FETCH_ERROR)", "UNKNOWN", None, ticker))

                if update_data:
                    execute_batch(cursor, update_query, update_data)
                    conn.commit()
                    total_processed += len(update_data)
                    logging.info(f"Batch DB sync complete. Cumulative processed: {total_processed}")

            except Exception as e:
                logging.error(f"PostgreSQL connection fault during enrichment: {e}")
                if conn: conn.rollback()
                logging.info("Network unstable. Sleeping for 10 seconds before retrying...")
                time.sleep(10)
            finally:
                if cursor: cursor.close()
                if conn: conn.close()
            
            # 💡 [RATE LIMIT DEFENSE] Macro-sleep between batches to prevent IP ban
            if tickers_to_update:
                logging.info("Batch complete. Cooling down for 5 seconds to prevent API Ban...")
                time.sleep(5)

if __name__ == "__main__":
    backfiller = MetadataBackfiller()
    backfiller.run_backfill(batch_size=100)