import os
import json
import logging
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv
from openai import OpenAI

# Configure clean logging format
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')

class WhaleBriefAIAnalyzer:
    """
    Advanced Dual-LLM Pipeline Engine with structured Prompt Optimization.
    - Brain (Reasoning): Qwen 397B MoE (Performs structured Chain-of-Thought)
    - Scribe KO (Korean): DeepSeek V4 Flash (Generates community-style alerts)
    - Scribe JA (Japanese): Qwen 122B MoE (Generates professional analyst reports)
    """
    def __init__(self) -> None:
        load_dotenv()
        self.db_url = os.getenv("DATABASE_URL")
        self.api_key = os.getenv("NVIDIA_API_KEY")
        
        self.reasoning_model = os.getenv("AI_REASONING_MODEL", "qwen3.5-397b-a17b")
        self.report_model_ko = os.getenv("AI_REPORT_MODEL_KO", "deepseek-v4-flash")
        self.report_model_ja = os.getenv("AI_REPORT_MODEL_JA", "qwen3.5-122b-a10b")
        
        if not self.api_key:
            raise ValueError("NVIDIA_API_KEY environment variable is required.")

        self.client = OpenAI(
            base_url="https://integrate.api.nvidia.com/v1", 
            api_key=self.api_key
        )

    def process_pending_filings(self) -> None:
        """Finds PENDING filings in the database and runs the optimized AI pipeline."""
        logging.info("Scanning database for PENDING filings to analyze...")
        
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
                logging.info("No PENDING items found. Pipeline is idling.")
                return

            for task in pending_tasks:
                self._execute_optimized_llm_chain(cursor, conn, task)
                
            logging.info(f"AI Pipeline finished processing {len(pending_tasks)} datasets.")
            
        except Exception as e:
            logging.error(f"Database transaction failure in AI engine: {e}")
        finally:
            if cursor: cursor.close()
            if conn: conn.close()

    def _execute_optimized_llm_chain(self, cursor: Any, conn: Any, task: Dict[str, Any]) -> None:
        """Executes the improved three-stage multi-agent pipeline with role separation."""
        ticker = task['ticker']
        form_type = task['form_type']
        filing_data = task['raw_parsed_data']
        dp_pct = float(task['dp_percentage']) if task['dp_percentage'] is not None else 0.0

        try:
            # ==========================================================
            # STAGE 1: Structured Quant Reasoning (Qwen 397B MoE)
            # ==========================================================
            logging.info(f"[{ticker}] Starting Stage 1: Structured Reasoning...")
            
            reasoning_system = (
                "너는 SEC 공시와 다크풀 데이터를 교차 분석하는 퀀트 리서치 애널리스트다. "
                "데이터에 근거한 논리적 추론만 수행하며, 근거 없는 추측은 하지 않는다."
            )
            
            reasoning_user = f"""
            ## 분석 대상
            - 종목: {ticker}
            - 공시 유형: {form_type}

            ## 입력 데이터
            ### SEC 공시 원문
            ```json
            {json.dumps(filing_data, ensure_ascii=False, indent=2)}
            ```

            ### 다크풀 지표
            - 다크풀 매도 비율: {dp_pct}%
            - 해석 기준: 50% 이상 = 매도 우위, 40~50% = 중립, 40% 미만 = 매수 우위

            ## 분석 프레임워크
            아래 4단계를 순서대로 수행하라:
            1. 공시 핵심 요약: 이 공시의 핵심 내용을 2문장으로 요약하라.
            2. 의도 추론: 공시 주체(내부자/기관)의 가능한 의도를 아래 중 분류하라.
               - DISTRIBUTION: 물량 분산 매도 (설거지/엑시트)
               - ACCUMULATION: 저가 매집 (매수 신호)
               - NEUTRAL: 정기 보고/의무 공시 등 방향성 없음
               - AMBIGUOUS: 데이터 부족으로 판단 불가
            3. 다크풀 교차 검증: 다크풀 매도 비율이 위 의도 추론을 지지하는지, 모순되는지 분석하라.
            4. 리스크 판정: 종합하여 리스크 레벨을 판정하라.
               - CRITICAL: 공시+다크풀 모두 강한 매도 신호
               - HIGH: 한쪽이 강한 매도 신호, 다른 쪽이 이를 지지
               - MEDIUM: 신호가 혼재되거나 중립
               - LOW: 공시+다크풀 모두 매수 우위 또는 무해

            ## 출력 형식
            반드시 아래 JSON만 출력하라. 다른 텍스트를 포함하지 마라.
            {{
              "intent": "DISTRIBUTION|ACCUMULATION|NEUTRAL|AMBIGUOUS",
              "risk_level": "LOW|MEDIUM|HIGH|CRITICAL",
              "confidence": 0.0~1.0,
              "filing_summary": "공시 핵심 2문장",
              "darkpool_alignment": "SUPPORTS|CONTRADICTS|INCONCLUSIVE",
              "reasoning": "3~5문장의 근거 요약"
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
            # STAGE 2: Korean Localization (DeepSeek V4 Flash)
            # ==========================================================
            logging.info(f"[{ticker}] Starting Stage 2: Localizing Korean Report...")
            
            ko_system = "너는 한국 주식 커뮤니티 스타일로 SEC 공시 분석을 전달하는 브리핑 작성자다. 반드시 지정된 JSON 형식으로만 응답한다."
            ko_user = f"""
            ## 입력 데이터
            아래는 {ticker}에 대한 퀀트 분석 보고서다.
            {raw_insights}

            ## 작성 규칙
            1. 한국 개미 투자자를 위한 정확히 3문장 브리핑을 작성하라.
            2. 말투: 디시인사이드 주식갤러리 스타일. 직설적이고 뼈를 때리는 '매운맛'.
               - 허용 표현 예시: "설거지 당하기 싫으면 도망쳐라", "엑시트 유동성 그 자체", "세력이 물량 떠넘기는 중"
            3. 분석 보고서의 risk_level을 그대로 사용하라. 보고서에 없으면 내용 기반으로 판단하라.
            4. 분석 보고서에 없는 내용을 지어내지 마라 (Hallucination 금지).

            ## 출력 형식 (JSON만 출력, 마크다운 코드블록 금지)
            {{"ai_risk_level": "LOW|MEDIUM|HIGH|CRITICAL", "ai_summary": "한국어 3문장"}}

            ## 출력 예시
            {{"ai_risk_level": "HIGH", "ai_summary": "이거 완전 세력 설거지. 다크풀에서 매도 물량 쏟아지는데 공시로 호재인 척 개미 꼬시고 있네. 지금 들어가면 엑시트 유동성 되는 거니까 잘 판단하셈."}}
            """
            
            ko_response = self.client.chat.completions.create(
                model=self.report_model_ko,
                messages=[
                    {"role": "system", "content": ko_system},
                    {"role": "user", "content": ko_user}
                ],
                temperature=0.2,
                response_format={"type": "json_object"}
            )
            ko_cleaned = ko_response.choices[0].message.content.strip().replace("```json", "").replace("```", "")
            ko_result = json.loads(ko_cleaned)
# ==========================================================
            # STAGE 3: Japanese Localization (Qwen 122B MoE)
            # ==========================================================
            logging.info(f"[{ticker}] Starting Stage 3: Localizing Japanese Report...")
            
            ja_system = "あなたはSEC開示分析を日本の個人投資家向けに伝えるブリーフィング作成者です。必ず指定されたJSON形式のみで応答してください。"
            ja_user = f"""
            ## 入力データ
            以下は{ticker}に関するクオンツ分析レポートである。
            {raw_insights}

            ## 作成ルール
            1. 日本の個人投資家向けに正確に3文のブリーフィングを作成せよ。
            2. 文体: 野村證券・大和証券のアナリストレポートのような格式高いトーン。ただし、リスクは鋭く警告すること。
               - 許容表現例: 「高値掴みのリスクが極めて高い」「ババ抜きの様相を呈している」「機関投資家の売り抜け局面」
            3. 分析レポートのrisk_levelをそのまま使用せよ。レポートにない場合は内容に基づき判断せよ。
            4. 分析レポートにない内容を捏造しないこと。

            ## 出力形式 (JSONのみ、マークダウン禁止)
            {{"ai_risk_level": "LOW|MEDIUM|HIGH|CRITICAL", "ai_summary": "日本語の3文"}}

            ## 出力例
            {{"ai_risk_level": "HIGH", "ai_summary": "当該銘柄では機関投資家による大規模な持分売却が確認されており、ダークプール指標においても継続的な売り圧力が観測されています。現時点での新規買いエントリーは高値圧力リスクを伴う可能性があります。"}}
            """
            
            ja_response = self.client.chat.completions.create(
                model=self.report_model_ja,
                messages=[
                    {"role": "system", "content": ja_system},
                    {"role": "user", "content": ja_user}
                ],
                temperature=0.2,
                response_format={"type": "json_object"}
            )
            ja_cleaned = ja_response.choices[0].message.content.strip().replace("```json", "").replace("```", "")
            ja_result = json.loads(ja_cleaned)

            # ==========================================================
            # STAGE 4: Database State Sync
            # ==========================================================
            update_query = """
                UPDATE sec_filings 
                SET ai_risk_level = %s, ai_summary_ko = %s, ai_summary_ja = %s 
                WHERE id = %s
            """
            cursor.execute(update_query, (
                ko_result.get("ai_risk_level", "PENDING"), 
                ko_result.get("ai_summary", "Analysis failed"),
                ja_result.get("ai_summary", "Analysis failed"),
                task['filing_id']
            ))
            conn.commit()
            logging.info(f"[{ticker}] Clean Intelligence Update Successful. State synchronized.")

        except Exception as e:
            logging.error(f"Critical execution error during optimized LLM chain for {ticker}: {e}")
            conn.rollback()
if __name__ == "__main__":
    # For local unit testing of the AI module independently from main.py
    logging.info("Running AI Analyzer in standalone debug mode...")
    analyzer = WhaleBriefAIAnalyzer()
    analyzer.process_pending_filings()