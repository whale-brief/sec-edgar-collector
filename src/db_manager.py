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
    Database Access Object (DAO) that manages connection pooling and 
    idempotent data ingestion into NeonDB (PostgreSQL).
    """
    def __init__(self) -> None:
        load_dotenv()
        self.db_url = os.getenv("DATABASE_URL")
        if not self.db_url:
            raise ValueError("DATABASE_URL environment variable is missing.")

    def insert_sec_filings(self, parsed_data_list: List[Dict[str, Any]]) -> None:
        """Inserts parsed SEC filings into the database using a Bulk Upsert strategy."""
        if not parsed_data_list:
            logging.info("No SEC data provided for insertion.")
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

            # Prevent Foreign Key violations by pre-populating the companies table
            self._ensure_companies_exist(cursor, list(unique_tickers))

            execute_values(cursor, insert_query, values_to_insert)
            conn.commit()
            
            inserted_count = cursor.rowcount
            logging.info(f"SEC Database Load Complete: {len(parsed_data_list)} attempted -> {inserted_count} newly inserted.")

        except Exception as e:
            logging.error(f"Critical error during SEC database insertion: {e}")
            if conn: conn.rollback()
        finally:
            if cursor: cursor.close()
            if conn: conn.close()

    def insert_finra_darkpool(self, finra_data_list: List[Dict[str, Any]]) -> None:
        """Inserts bulk FINRA Reg SHO metrics into the database with Conflict handling."""
        if not finra_data_list:
            logging.info("No FINRA data provided for insertion.")
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

            self._ensure_companies_exist(cursor, list(unique_tickers))

            # Handle massive batch inserts within a single database transaction
            execute_values(cursor, insert_query, values_to_insert)
            conn.commit()
            
            inserted_count = cursor.rowcount
            logging.info(f"FINRA Database Load Complete: {len(finra_data_list)} attempted -> {inserted_count} newly inserted.")

        except Exception as e:
            logging.error(f"Critical error during FINRA database insertion: {e}")
            if conn: conn.rollback()
        finally:
            if cursor: cursor.close()
            if conn: conn.close()

    def _ensure_companies_exist(self, cursor: Any, tickers: List[str]) -> None:
        """Ensures all referenced tickers exist in the companies metadata table to safe-keep FK integrity."""
        if not tickers: return
        
        company_query = """
            INSERT INTO companies (ticker, company_name)
            VALUES %s
            ON CONFLICT (ticker) DO NOTHING;
        """
        company_values = [(ticker, f"{ticker} (Auto-added)") for ticker in tickers]
        execute_values(cursor, company_query, company_values)