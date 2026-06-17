import os
import json
import logging
import psycopg2
from psycopg2.extras import execute_values
from dotenv import load_dotenv
from typing import List, Dict, Any

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')

class NeonDBManager:
    """
    NeonDB(PostgreSQL)와의 연결 및 데이터 적재를 전담하는 클래스.
    Idempotency(멱등성)를 보장하여 데이터 중복 적재를 방지합니다.
    """
    def __init__(self) -> None:
        load_dotenv()
        self.db_url = os.getenv("DATABASE_URL")
        if not self.db_url:
            raise ValueError("DATABASE_URL must be set in .env file")

    def insert_sec_filings(self, parsed_data_list: List[Dict[str, Any]]) -> None:
        """파싱된 공시 데이터를 NeonDB에 안전하게 병합(Upsert)합니다."""
        if not parsed_data_list:
            logging.info("No new data to insert into the database.")
            return

        insert_query = """
            INSERT INTO sec_filings (
                ticker, form_type, filing_date, transaction_type, 
                insider_title, shares_traded, raw_link, filing_title, raw_parsed_data
            ) VALUES %s
            ON CONFLICT (ticker, form_type, filing_date, raw_link) DO NOTHING;
        """

        values_to_insert = []
        unique_tickers = set()

        for data in parsed_data_list:
            unique_tickers.add(data['ticker'])
            raw_json_str = json.dumps(data, ensure_ascii=False)
            
            values_to_insert.append((
                data['ticker'], data['form_type'], data['transaction_date'],
                data['transaction_type'], data['insider_title'], data['shares_traded'],
                data['raw_link'], data['filing_title'], raw_json_str
            ))

        conn = None
        cursor = None
        try:
            conn = psycopg2.connect(self.db_url)
            cursor = conn.cursor()

            # 외래키 무결성 제약조건 방어를 위한 사전 기업 데이터 삽입
            self._ensure_companies_exist(cursor, list(unique_tickers))

            # Bulk Insert 실행
            execute_values(cursor, insert_query, values_to_insert)
            conn.commit()
            
            inserted_count = cursor.rowcount
            logging.info(f"Database Load Complete: {len(parsed_data_list)} attempted -> {inserted_count} newly inserted.")

        except Exception as e:
            logging.error(f"Critical error during database insertion: {e}")
            if conn:
                conn.rollback()
        finally:
            if cursor: cursor.close()
            if conn: conn.close()

    def insert_finra_darkpool(self, finra_data_list: List[Dict[str, Any]]) -> None:
        """FINRA 다크풀 및 공매도 배치 데이터를 Bulk Upsert 방식으로 적재합니다."""
        if not finra_data_list:
            logging.info("No FINRA data to insert.")
            return

        insert_query = """
            INSERT INTO finra_darkpool_daily (
                ticker, trading_date, darkpool_volume, short_interest, dp_percentage
            ) VALUES %s
            ON CONFLICT (ticker, trading_date) DO NOTHING;
        """

        values_to_insert = []
        unique_tickers = set()

        for data in finra_data_list:
            unique_tickers.add(data['ticker'])
            values_to_insert.append((
                data['ticker'], 
                data['trading_date'], 
                data['darkpool_volume'], 
                data['short_volume'], 
                data['dp_percentage']
            ))

        conn = None
        cursor = None
        try:
            conn = psycopg2.connect(self.db_url)
            cursor = conn.cursor()

            # [아키텍트의 무기] 8,000개의 듣보잡 티커가 들어와도 FK 에러가 나지 않도록 사전 적재
            self._ensure_companies_exist(cursor, list(unique_tickers))

            # Bulk Insert (수천 건의 데이터를 단 한 번의 트랜잭션으로 처리)
            execute_values(cursor, insert_query, values_to_insert)
            conn.commit()
            
            inserted_count = cursor.rowcount
            logging.info(f"FINRA DB Load Complete: {len(finra_data_list)} attempted -> {inserted_count} newly inserted.")

        except Exception as e:
            logging.error(f"Critical error during FINRA DB insertion: {e}")
            if conn:
                conn.rollback()
        finally:
            if cursor: cursor.close()
            if conn: conn.close()

    def _ensure_companies_exist(self, cursor: Any, tickers: List[str]) -> None:
        """외래키(FK) 에러 방지를 위해 수집된 Ticker를 메타 테이블에 선행 적재합니다."""
        if not tickers: return
        
        company_query = """
            INSERT INTO companies (ticker, company_name)
            VALUES %s
            ON CONFLICT (ticker) DO NOTHING;
        """
        company_values = [(ticker, f"{ticker} (Auto-added)") for ticker in tickers]
        execute_values(cursor, company_query, company_values)