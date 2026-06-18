import os
import time
import logging
import psycopg2
import yfinance as yf
from psycopg2.extras import execute_batch
from dotenv import load_dotenv
from typing import Any

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')

class MetadataBackfiller:
    """
    Asynchronous maintenance worker engineered to enrich empty corporate metadata
    fields via the Yahoo Finance API, preventing main pipeline degradation.
    """
    def __init__(self) -> None:
        load_dotenv()
        self.db_url = os.getenv("DATABASE_URL")
        if not self.db_url:
            raise ValueError("DATABASE_URL must be supplied inside environment maps.")

    def run_backfill(self, batch_size: int = 100) -> None:
        """Identifies dummy shell records and overlays verifiable asset infrastructure metrics."""
        logging.info("Initiating corporate metadata enrichment sequence...")
        
        select_query = """
            SELECT ticker FROM companies 
            WHERE sector IS NULL OR company_name LIKE '%(Auto-added)%'
            LIMIT %s;
        """
        
        update_query = """
            UPDATE companies 
            SET company_name = %s, sector = %s, updated_at = CURRENT_TIMESTAMP 
            WHERE ticker = %s;
        """

        conn = None
        cursor = None
        try:
            conn = psycopg2.connect(self.db_url)
            cursor = conn.cursor()
            
            cursor.execute(select_query, (batch_size,))
            tickers_to_update = [row[0] for row in cursor.fetchall()]
            
            if not tickers_to_update:
                logging.info("Data lake equilibrium achieved. No un补 (Backfill) fields required.")
                return

            logging.info(f"Discovered {len(tickers_to_update)} anomalies. Interrogating Yahoo Finance API...")

            update_data = []
            for ticker in tickers_to_update:
                try:
                    stock = yf.Ticker(ticker)
                    info = stock.info
                    
                    # Defend against delisted tokens or dead acquisition shells
                    if 'shortName' not in info and 'longName' not in info:
                        logging.warning(f"Ticker {ticker} is non-existent on public boards. Invalidating.")
                        update_data.append((f"{ticker} (INVALID/DELISTED)", "UNKNOWN", ticker))
                        continue

                    company_name = info.get('longName') or info.get('shortName', ticker)
                    sector = info.get('sector', 'Other')
                    
                    update_data.append((company_name, sector, ticker))
                    logging.info(f"Enriched: {ticker} -> {company_name} [{sector}]")
                    
                    # Linear sleep cadence to respect Yahoo Finance's connection pool limits
                    time.sleep(0.5) 
                    
                except Exception as e:
                    logging.error(f"Failed to fetch upstream market indices for {ticker}: {e}")
                    update_data.append((f"{ticker} (RETRY_REQUIRED)", "UNKNOWN", ticker))

            if update_data:
                execute_batch(cursor, update_query, update_data)
                conn.commit()
                logging.info(f"Metadata Backfill Complete: {len(update_data)} records solidified.")

        except Exception as e:
            logging.error(f"Database communication breakdown during enrichment phase: {e}")
            if conn: conn.rollback()
        finally:
            if cursor: cursor.close()
            if conn: conn.close()

if __name__ == "__main__":
    backfiller = MetadataBackfiller()
    backfiller.run_backfill(batch_size=100)