# sec-edgar-collector (Whale-Brief Engine 🐋)

<div align="right">
  <strong>Like this project? Support us with a Star!</strong> ↗️ ⭐️ <strong>Star</strong> 
</div>

![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)
![Python: 3.10+](https://img.shields.io/badge/python-3.10%2B-blue)
![Database: PostgreSQL](https://img.shields.io/badge/database-PostgreSQL-blue)

A 100% serverless, zero-cost ETL pipeline and Dual-LLM intelligence engine designed to eliminate the information asymmetry between Wall Street institutions and non-English speaking retail investors.

## The Philosophy (Why we built this)
Retail investors in Asia trading US equities often become "exit liquidity" for institutional investors. Critical structural signals—such as sudden F-3 (shelf offering) activations or FINRA darkpool short volume spikes—are buried in dense SEC XML filings and raw text dumps. By the time this data is manually translated and reaches retail communities, the market has already moved.

This project autonomously extracts, joins, and reasons over cross-domain financial data (SEC + FINRA) to deliver localized, institutional-grade risk signals before the retail market reacts.

## Architecture & Tech Stack

We engineered this pipeline to operate at **\$0 infrastructure cost** by leveraging serverless environments and optimizing LLM reasoning tiers.

- **Orchestration:** GitHub Actions (Cron-based batch processing)
- **Database:** NeonDB (Serverless PostgreSQL)
- **Intelligence (Dual-LLM):** NVIDIA NIM (Qwen 397B for Reasoning, DeepSeek-V4/Qwen-122B for localized formatting)
- **Data Sources:** SEC EDGAR (Atom Feeds), FINRA (Reg SHO Daily)

### System Flow Diagram
```text
┌─────────────────┐       [Extract: Delta]        ┌──────────────────────┐
│ SEC EDGAR (XML) ├──────────────────────────────►│ src/collector.py     │
└─────────────────┘                               └──────────┬───────────┘
                                                             │ (Transform)
┌─────────────────┐       [Extract: Bulk]         ┌──────────▼───────────┐
│ FINRA Reg SHO   ├──────────────────────────────►│ src/db_manager.py    │
└─────────────────┘                               └──────────┬───────────┘
                                                             │ (Load / Upsert)
                                                  ┌──────────▼───────────┐
                                                  │ NeonDB (PostgreSQL)  │
                                                  └──────────┬───────────┘
                                                             │ (Query Pending)
┌────────────────────────────────────────────────────────────▼───────────┐
│ src/ai_analyzer.py (Language-Aware Dual-LLM Engine)                    │
│                                                                        │
│  1. The Brain (Qwen 397B)    : "Analyze the correlation between SEC    │
│                                insider trades & Darkpool short volume" │
│  2. The Scribe KO (DeepSeek) : "Format as aggressive Korean JSON"      │
│  3. The Scribe JA (Qwen 122B): "Format as formal Japanese JSON"        │
└────────────────────────────────────────────────────────────┬───────────┘
                                                             │ (Update)
                                                  ┌──────────▼───────────┐
                                                  │ Final Risk JSONs     │
                                                  └──────────────────────┘
```

### Installation & Setup

1. Clone the repository

```Bash
git clone https://github.com/whale-brief/sec-edgar-collector.git
cd sec-edgar-collector
```

2. Set up the environment
Create a virtual environment and install the required dependencies.

```Bash
python3 -m venv venv
source venv/bin/activate  # On Windows use `venv\Scripts\activate`
pip install -r requirements.txt
```

3. Configure Environment Variables
Copy the example environment file and fill in your credentials.

```Bash
cp .env.example .env
```

Edit .env to include your NeonDB connection string, SEC User-Agent, and NVIDIA API key.

4. Run the Pipeline Locally
To manually trigger the complete End-to-End pipeline:

```Bash
python main.py
```

---

## Roadmap & Global Contribution

Currently, this engine supports high-fidelity **Korean** and **Japanese** LLM inference. **Chinese (ZH) support is officially on the roadmap!** 🚀

We believe language should never be a barrier to global investment insights. We warmly welcome contributors from all over the world to help expand this project into your own native languages!

*   [ ] Chinese (ZH) Prompt & Inference Support (Coming Soon)
*   [ ] Prompt localization & refinement for other languages (Help us! 🤝)

### Join the Global Translation & Prompt Pipeline!
*   **한국어:** 미국 주식 공시를 분석해서 지지않는 매매를 할 수 있도록, 프롬프트 효율화 및 파이프라인 기여를 기다리고 있습니다!
*   **日本語:** 世界中の投資家が直感的に米国株を分析できるように, 各言語のプロンプトやロジックへの貢献・PRを大歓迎します！
*   **简体中文:** 欢迎中国开发者加入！我们即将支持中文推理，非常期待您为中文提示词（Prompt）和本地化贡献力量。

---

## ⚠️ Disclaimer

This project is for research, data-parsing, and educational purposes only. It does **not** provide financial or investment advice. Users are solely responsible for ensuring their deployment environment complies with regional availability and usage policies of any third-party AI services used (such as OpenAI or NVIDIA NIM).

---

### License

This project is licensed under the MIT License - see the LICENSE file for details.
