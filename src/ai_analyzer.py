import os
import json
import logging
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv
from openai import OpenAI
from typing import Dict, Any, List

# Configure clean logging format
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')

class WhaleBriefAIAnalyzer:
    """
    Advanced Multi-Agent Pipeline with Quant-grade Filtering & Overhang Detection.
    - Applies Asymmetrical Insider Logic (Buy = Strong Signal, Sell = Check for Noise/Diversification).
    - Filters out micro-trades (< $100k) and non-market codes (M, F, G).
    - Identifies Overhang risks combining SEC Form 4 and FINRA Darkpool data.
    """
    def __init__(self) -> None:
        load_dotenv()
        self.db_url = os.getenv("DATABASE_URL")
        self.api_key = os.getenv("NVIDIA_API_KEY")
        
        # Production Tier Models
        self.reasoning_model = os.getenv("AI_REASONING_MODEL", "meta/llama-3.1-8b-instruct")
        self.report_model_ko = os.getenv("AI_REPORT_MODEL_KO", "meta/llama-3.1-8b-instruct")
        self.report_model_ja = os.getenv("AI_REPORT_MODEL_JA", "meta/llama-3.1-8b-instruct")
        
        if not self.api_key:
            raise ValueError("NVIDIA_API_KEY environment variable is required.")

        # Fail-fast Architecture: No hidden retries, aggressive timeout
        self.client = OpenAI(
            base_url="https://integrate.api.nvidia.com/v1", 
            api_key=self.api_key,
            timeout=15.0,  
            max_retries=0  
        )

    def process_pending_filings(self) -> None:
        """Fetches PENDING filings, filters noise via Safe Parsing, and batches for AI."""
        logging.info("Scanning database for PENDING filings (Quant Optimization Mode)...")
        
        query = """
            SELECT 
                s.id as filing_id, s.ticker, s.form_type, s.filing_date, 
                s.shares_traded, s.raw_parsed_data,
                f.darkpool_volume, f.dp_percentage
            FROM sec_filings s
            LEFT JOIN finra_darkpool_daily f 
                   ON s.ticker = f.ticker AND f.trading_date <= s.filing_date
            WHERE s.ai_risk_level = 'PENDING'
            ORDER BY s.ticker, s.filing_date DESC
            LIMIT 50;
        """
        
        conn = None
        cursor = None
        try:
            conn = psycopg2.connect(self.db_url)
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            cursor.execute(query)
            pending_tasks = cursor.fetchall()

            if not pending_tasks:
                logging.info("No PENDING items found. Intelligence Pipeline is idling.")
                return

            grouped_tasks: Dict[str, Dict[str, Any]] = {}
            ignored_ids: List[int] = []

            for row in pending_tasks:
                ticker = row['ticker']
                shares = float(row['shares_traded']) if row['shares_traded'] else 0.0
                
                # Safe JSONB Parsing
                raw_data = row['raw_parsed_data']
                if isinstance(raw_data, str):
                    try:
                        raw_data = json.loads(raw_data)
                    except json.JSONDecodeError:
                        raw_data = {}
                
                # Extract deep quant metrics (with fallback defaults to prevent Pipeline collapse)
                tx_code = raw_data.get('transaction_code', '') 
                price_per_share = float(raw_data.get('price_per_share', 0.0))
                total_amount = shares * price_per_share

                # 💡 [필터링 1] stock option(M), tax(F), give(G)
                if tx_code in ['M', 'F', 'G']:
                    ignored_ids.append(row['filing_id'])
                    continue

                
                if price_per_share > 0 and total_amount < 100000.0:
                    ignored_ids.append(row['filing_id'])
                    continue

                if ticker not in grouped_tasks:
                    grouped_tasks[ticker] = {
                        'filing_ids': [],
                        'filings_data': [],
                        'dp_percentage': float(row['dp_percentage']) if row['dp_percentage'] else 0.0,
                        'form_type': row['form_type']
                    }
                
                grouped_tasks[ticker]['filing_ids'].append(row['filing_id'])
                grouped_tasks[ticker]['filings_data'].append(raw_data)

            if ignored_ids:
                ignore_query = """
                    UPDATE sec_filings 
                    SET ai_risk_level = 'LOW', 
                        ai_summary_ko = '단순 소액 거래, 스톡옵션 행사 또는 10b5-1 예약 매매로 판단되어 AI 분석에서 제외되었습니다.', 
                        ai_summary_ja = '少額取引、ストックオプション行使、または10b5-1計画に基づく取引のため、AI分析から除外されました。' 
                    WHERE id = ANY(%s)
                """
                cursor.execute(ignore_query, (ignored_ids,))
                conn.commit()
                logging.info(f"Filtered out {len(ignored_ids)} noise/micro-trades to preserve API latency.")

            for ticker, group_data in grouped_tasks.items():
                self._execute_batch_llm_chain(cursor, conn, ticker, group_data)
                
            logging.info(f"AI Pipeline efficiently metabolized {len(pending_tasks)} datasets.")
            
        except Exception as e:
            logging.error(f"Database transaction collapse in AI engine: {e}")
        finally:
            if cursor: cursor.close()
            if conn: conn.close()

    def _execute_batch_llm_chain(self, cursor: Any, conn: Any, ticker: str, group_data: Dict[str, Any]) -> None:
        """Executes Overhang & Asymmetrical analysis on verified filing clusters."""
        filing_ids = group_data['filing_ids']
        filings_data = group_data['filings_data']
        dp_pct = group_data['dp_percentage']
        batch_count = len(filing_ids)

        try:
            # ==========================================================
            # STAGE 1: Asymmetrical Quant Reasoning & Overhang Detection
            # ==========================================================
            logging.info(f"[{ticker}] Stage 1: Asymmetrical Reasoning for {batch_count} clustered filings...")
            
            reasoning_system = (
                "너는 월스트리트 헤지펀드의 시니어 퀀트 애널리스트다. "
                "SEC 공시와 FINRA 다크풀을 결합하여, 유동성 함정(Overhang Risk)과 "
                "내부자 매매 비대칭성(Buy=강력, Sell=다각화 노이즈 가능성)을 철저히 계산한다."
            )
            
            reasoning_user = f"""
            ## 분석 대상
            - 종목: {ticker}
            - 공시 건수: 동일 시점에 발생한 {batch_count}건의 내부자/기관 거래 클러스터

            ## 입력 데이터 (JSON)
            ```json
            {json.dumps(filings_data, ensure_ascii=False, indent=2)}
            ```

            ## 시장 유동성 지표
            - 다크풀 쇼트(공매도) 비율: {dp_pct}% (50% 초과 시 기관의 은밀한 하방 배팅으로 간주)

            ## 퀀트 분석 프레임워크
            아래 4단계를 순서대로 수행하라:
            1. 클러스터 매매 판별: 이것이 단일 인물의 독립 거래인지, 다수 임원/기관이 동시다발적으로 던진 '그룹 매매(Clustering)'인지 파악하라.
            2. 비대칭성 기반 의도 추론: 
               - 내부자 매수(Buy)는 무조건 강력한 'ACCUMULATION(저가 매집)'으로 해석하라.
               - 내부자 매도(Sell)는 단순 자산 다각화일 수 있으나, 만약 '다수 임원의 동시 매도'이거나 '10b5-1 계획이 아닌 임의 매도'라면 'DISTRIBUTION(엑시트/설거지)'으로 가중치를 부여하라.
            3. 오버행(Overhang) 리스크 검증: 내부자 매도와 다크풀 쇼트 비율(50% 이상)이 겹칠 경우, 주가 상승을 억누르는 '대기 매도 물량(Overhang Risk)'이 터진 것으로 간주하라.
            4. 최종 리스크 판정:
               - CRITICAL: 그룹 매도(설거지) + 다크풀 쇼트 50% 이상 (오버행 폭발 위험)
               - HIGH: 매도 우위 신호가 뚜렷함
               - MEDIUM: 10b5-1 기계적 매도이거나 신호가 혼재됨
               - LOW: 내부자 매집(Buy) 또는 무해한 거래

            ## 출력 형식 (Strict JSON)
            {{
              "intent": "DISTRIBUTION|ACCUMULATION|NEUTRAL|AMBIGUOUS",
              "risk_level": "LOW|MEDIUM|HIGH|CRITICAL",
              "overhang_risk_detected": true/false,
              "filing_summary": "비대칭성과 오버행을 포함한 핵심 요약 2문장",
              "reasoning": "3문장의 논리적 근거 (수량/금액/다크풀 교차 검증 포함)"
            }}
            """

            reasoning_response = self.client.chat.completions.create(
                model=self.reasoning_model,
                messages=[
                    {"role": "system", "content": reasoning_system},
                    {"role": "user", "content": reasoning_user}
                ],
                temperature=0.1,
                response_format={"type": "json_object"}
            )
            raw_insights = reasoning_response.choices[0].message.content

            # ==========================================================
            # STAGE 2: Korean Localization (Aggressive Retail Alert)
            # ==========================================================
            logging.info(f"[{ticker}] Stage 2: Compiling Korean Retail Alert...")
            ko_system = "너는 한국 디시인사이드 주식갤러리 유저들을 위해 퀀트 보고서를 매운맛으로 번역하는 브리핑 봇이다."
            ko_user = f"""
            아래 {ticker} 분석 결과를 바탕으로 3문장 브리핑을 JSON으로 작성하라.
            {raw_insights}

            [규칙]
            - 직설적이고 경고성 짙은 말투 사용 (예: 오버행 터졌다, 설거지 엑시트 중이다, 세력 매집 포착 등)
            - Overhang Risk(잠재 대규모 매도 대기 물량)가 발견되었다면 반드시 경고에 포함시킬 것.
            - 출력 포맷: {{"ai_risk_level": "분석보고서의_위험도", "ai_summary": "한국어 3문장"}}
            """
            ko_res = self.client.chat.completions.create(
                model=self.report_model_ko,
                messages=[{"role": "system", "content": ko_system}, {"role": "user", "content": ko_user}],
                temperature=0.2, response_format={"type": "json_object"}
            )
            ko_result = json.loads(ko_res.choices[0].message.content)

            # ==========================================================
            # STAGE 3: Japanese Localization (Formal Brokerage Alert)
            # ==========================================================
            logging.info(f"[{ticker}] Stage 3: Compiling Japanese Brokerage Alert...")
            ja_system = "あなたはクオンツ分析を日本の個人投資家向けに伝える証券アナリストです。"
            ja_user = f"""
            以下の{ticker}の分析結果を基に、3文のブリーフィングをJSONで作成せよ。
            {raw_insights}

            [規則]
            - 野村證券のような格式高い文体でありながら、リスクを鋭く警告すること。
            - オーバーハング（Overhang：株式の需給悪化、将来の大量売却リスク）が検出された場合は必ず言及すること。
            - 出力形式: {{"ai_risk_level": "LOW|MEDIUM|HIGH|CRITICAL", "ai_summary": "日本語の3文"}}
            """
            ja_res = self.client.chat.completions.create(
                model=self.report_model_ja,
                messages=[{"role": "system", "content": ja_system}, {"role": "user", "content": ja_user}],
                temperature=0.2, response_format={"type": "json_object"}
            )
            ja_result = json.loads(ja_res.choices[0].message.content)

            # ==========================================================
            # STAGE 4: Bulk Database State Sync
            # ==========================================================
            update_query = """
                UPDATE sec_filings 
                SET ai_risk_level = %s, ai_summary_ko = %s, ai_summary_ja = %s 
                WHERE id = ANY(%s)
            """
            cursor.execute(update_query, (
                ko_result.get("ai_risk_level", "PENDING"), 
                ko_result.get("ai_summary", "Analysis mapping error"),
                ja_result.get("ai_summary", "分析マッピングエラー"),
                filing_ids
            ))
            conn.commit()
            logging.info(f"[{ticker}] Overhang Analysis Complete. Batched {batch_count} records.")

        except Exception as e:
            logging.error(f"Execution error during AI routing for {ticker}: {e}")
            conn.rollback()

if __name__ == "__main__":
    logging.info("Running Quant-Optimized AI Analyzer in standalone mode...")
    analyzer = WhaleBriefAIAnalyzer()
    analyzer.process_pending_filings()