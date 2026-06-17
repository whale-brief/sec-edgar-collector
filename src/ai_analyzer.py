import os
import json
import logging
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv
from openai import OpenAI

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')

class WhaleBriefAIAnalyzer:
    """
    Language-Aware Dual-LLM 파이프라인.
    - Brain (Reasoning): qwen3.5-397b-a17b
    - Scribe (Korean): deepseek-v4-flash (직설적, 매운맛 커뮤니티 감성)
    - Scribe (Japanese): qwen3.5-122b-a10b (증권사 리포트, 격식 있는 경고 감성)
    """
    def __init__(self):
        load_dotenv()
        self.db_url = os.getenv("DATABASE_URL")
        self.api_key = os.getenv("NVIDIA_API_KEY")
        
        # .env에서 무료 모델 라우팅 설정 불러오기
        self.reasoning_model = os.getenv("AI_REASONING_MODEL")
        self.report_model_ko = os.getenv("AI_REPORT_MODEL_KO")
        self.report_model_ja = os.getenv("AI_REPORT_MODEL_JA")
        
        if not self.api_key:
            raise ValueError("API Key is not set.")

        self.client = OpenAI(
            base_url="https://integrate.api.nvidia.com/v1", 
            api_key=self.api_key
        )

    def process_pending_filings(self):
        logging.info("Scanning for PENDING SEC filings...")
        
        query = """
            SELECT 
                s.id as filing_id, s.ticker, s.form_type, s.filing_date, s.raw_parsed_data,
                f.darkpool_volume, f.dp_percentage, f.short_interest
            FROM sec_filings s
            LEFT JOIN finra_darkpool_daily f 
                   ON s.ticker = f.ticker AND f.trading_date <= s.filing_date
            WHERE s.ai_risk_level = 'PENDING'
            ORDER BY f.trading_date DESC
            LIMIT 10;
        """
        
        conn = None
        cursor = None
        try:
            conn = psycopg2.connect(self.db_url)
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            cursor.execute(query)
            pending_tasks = cursor.fetchall()

            if not pending_tasks:
                logging.info("No PENDING filings found.")
                return

            for task in pending_tasks:
                self._analyze_and_update(cursor, conn, task)
                
            logging.info(f"Multi-Agent Analysis completed for {len(pending_tasks)} filings.")
            
        except Exception as e:
            logging.error(f"Database error: {e}")
        finally:
            if cursor: cursor.close()
            if conn: conn.close()

    def _analyze_and_update(self, cursor, conn, task):
        ticker = task['ticker']
        form_type = task['form_type']
        filing_data = task['raw_parsed_data']
        dp_pct = task['dp_percentage'] or 0.0

        try:
            # ==========================================================
            # STEP 1: 공통 추론 (The Brain - Qwen3 235B Thinking)
            # ==========================================================
            logging.info(f"[{ticker}] Step 1: Reasoning phase (Qwen3)...")
            reasoning_prompt = f"""
            너는 최고 수준의 퀀트 트레이더다.
            아래 {ticker}의 SEC 공시 데이터({form_type})와 장외 다크풀 데이터를 분석하라.
            이 공시가 세력의 물량 떠넘기기(설거지)인지, 아니면 강력한 매수 신호인지 논리적으로 추론하라.
            - SEC 공시: {json.dumps(filing_data, ensure_ascii=False)}
            - 다크풀 매도 비율: {dp_pct}% (50% 이상 시 매도 우위)
            """

            reasoning_response = self.client.chat.completions.create(
                model=self.reasoning_model,
                messages=[{"role": "user", "content": reasoning_prompt}],
                temperature=0.4
            )
            raw_thoughts = reasoning_response.choices[0].message.content

            # ==========================================================
            # STEP 2: 한국어 리포트 정제 (The Scribe KO - DeepSeek R1)
            # ==========================================================
            logging.info(f"[{ticker}] Step 2: Formatting KO (DeepSeek R1)...")
            ko_prompt = f"""
            다음 퀀트 분석 보고서를 바탕으로 한국 개미 투자자들을 위한 3문장 브리핑을 작성하라.
            [분석 보고서]: {raw_thoughts}
            
            지시사항:
            - 말투는 디시인사이드 주식 커뮤니티처럼 직설적이고, 뼈를 때리는 '매운맛'으로 작성할 것. (예: 설거지, 엑시트 유동성, 도망쳐라 등)
            - 반드시 아래 JSON 형식으로만 응답하라.
            {{"ai_risk_level": "LOW|MEDIUM|HIGH|CRITICAL", "ai_summary": "한국어 3문장"}}
            """
            
            ko_response = self.client.chat.completions.create(
                model=self.report_model_ko,
                messages=[{"role": "user", "content": ko_prompt}],
                temperature=0.2,
                response_format={"type": "json_object"}
            )
            ko_result = json.loads(ko_response.choices[0].message.content.strip().replace("```json", "").replace("```", ""))

            # ==========================================================
            # STEP 3: 일본어 리포트 정제 (The Scribe JA - Qwen 2.5)
            # ==========================================================
            logging.info(f"[{ticker}] Step 3: Formatting JA (Qwen 2.5)...")
            ja_prompt = f"""
            以下のクアント分析レポートを基に、日本の個人投資家向けに3文のブリーフィングを作成せよ。
            [分析レポート]: {raw_thoughts}
            
            指示事項:
            - 文体は、野村證券などの公式なアナリストレポートのような格式高いトーンでありながら、リスク(高値掴み、ババ抜き等)を鋭く警告するスタイルとすること。
            - 必ず以下のJSON形式のみで応答せよ。マークダウンは使用しないこと。
            {{"ai_summary": "日本語の3文"}}
            """
            
            ja_response = self.client.chat.completions.create(
                model=self.report_model_ja,
                messages=[{"role": "user", "content": ja_prompt}],
                temperature=0.2,
                response_format={"type": "json_object"}
            )
            ja_result = json.loads(ja_response.choices[0].message.content.strip().replace("```json", "").replace("```", ""))

            # ==========================================================
            # STEP 4: DB 동시 업데이트
            # ==========================================================
            update_query = """
                UPDATE sec_filings 
                SET ai_risk_level = %s, ai_summary_ko = %s, ai_summary_ja = %s 
                WHERE id = %s
            """
            cursor.execute(update_query, (
                ko_result.get("ai_risk_level", "PENDING"), 
                ko_result.get("ai_summary", "분석 실패"),
                ja_result.get("ai_summary", "分析失敗"),
                task['filing_id']
            ))
            conn.commit()
            logging.info(f"[{ticker}] Pipeline Complete: Risk -> {ko_result.get('ai_risk_level')}")

        except Exception as e:
            logging.error(f"Multi-Agent API error for {ticker}: {e}")
            conn.rollback()

if __name__ == "__main__":
    analyzer = WhaleBriefAIAnalyzer()
    analyzer.process_pending_filings()