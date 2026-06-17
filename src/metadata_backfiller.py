import os
import time
import logging
import psycopg2
import yfinance as yf
from psycopg2.extras import execute_batch
from dotenv import load_dotenv

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')

class MetadataBackfiller:
    """
    주말 배치(Batch) 전용 워커.
    companies 테이블에서 정보가 누락된(Auto-added) 티커를 찾아
    Yahoo Finance API를 통해 실존 기업 데이터로 메타데이터를 덮어씁니다(Backfill).
    """
    def __init__(self):
        load_dotenv()
        self.db_url = os.getenv("DATABASE_URL")
        if not self.db_url:
            raise ValueError("DATABASE_URL is not set.")

    def run_backfill(self, batch_size=50):
        logging.info("Initiating Metadata Backfill sequence...")
        
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
            
            # 1. 갱신이 필요한 티커 조회
            cursor.execute(select_query, (batch_size,))
            tickers_to_update = [row[0] for row in cursor.fetchall()]
            
            if not tickers_to_update:
                logging.info("No missing metadata found. All companies are up to date.")
                return

            logging.info(f"Found {len(tickers_to_update)} companies to backfill. Fetching from Yahoo Finance...")

            update_data = []
            for ticker in tickers_to_update:
                try:
                    # 야후 파이낸스에서 티커 정보 조회
                    stock = yf.Ticker(ticker)
                    info = stock.info
                    
                    # 폐지되었거나 유효하지 않은 티커 방어 로직
                    if 'shortName' not in info and 'longName' not in info:
                        logging.warning(f"Ticker {ticker} not found in Yahoo Finance. Marking as INVALID.")
                        update_data.append((f"{ticker} (INVALID/DELISTED)", "UNKNOWN", ticker))
                        continue

                    company_name = info.get('longName') or info.get('shortName', ticker)
                    sector = info.get('sector', 'Other')
                    
                    update_data.append((company_name, sector, ticker))
                    logging.info(f"Extracted: {ticker} -> {company_name} ({sector})")
                    
                    # YFinance Rate Limit 방어용 백오프
                    time.sleep(0.5) 
                    
                except Exception as e:
                    logging.error(f"Error fetching data for {ticker}: {e}")
                    # 에러 발생 시 무한 루프를 막기 위해 임시 태그 부착
                    update_data.append((f"{ticker} (FETCH_ERROR)", "UNKNOWN", ticker))

            # 2. DB 일괄 업데이트 (Batch Update)
            if update_data:
                execute_batch(cursor, update_query, update_data)
                conn.commit()
                logging.info(f"Successfully backfilled {len(update_data)} companies.")

        except Exception as e:
            logging.error(f"Database error during backfill: {e}")
            if conn: conn.rollback()
        finally:
            if cursor: cursor.close()
            if conn: conn.close()

if __name__ == "__main__":
    backfiller = MetadataBackfiller()
    # 한 번에 너무 많은 티커를 조회하면 야후 파이낸스에서 IP 차단. 
    # 배치 1회당 50~100개씩 안전하게 처리.
    backfiller.run_backfill(batch_size=100)