# SEC EDGAR Collector 🐋

![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)
![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)
![Rust](https://img.shields.io/badge/rust-latest-orange.svg)

> High-performance, ultra-lightweight SEC EDGAR filing and Form 4 (Insider Trading) parsing engine built with Python and Rust.

## The Motivation

Navigating the SEC EDGAR database is notoriously painful. Existing parsing tools are often bloated, slow, and return deeply nested XML documents that are difficult to consume in modern data pipelines.

More importantly, real-time financial data—especially insider trading activity (Form 4)—is often locked behind expensive proprietary terminals or buried within dense regulatory filings. This creates a significant information and language barrier for global retail investors.

`sec-edgar-collector` was built to level the playing field. It transforms complex SEC filings into clean, structured JSON payloads optimized for analytics, AI applications, and multilingual financial research.

The mission is simple:

**Make institutional-grade SEC data accessible to everyone.**

## Optimized for LLMs & RAG Pipelines

This collector is not just another scraper.

The output format is intentionally designed for modern AI workflows, including:

* LLM-powered financial assistants
* RAG pipelines
* AI news summarization
* Automated market intelligence systems

By removing unnecessary HTML/XML structures and exposing normalized JSON schemas, the collector minimizes token consumption while maximizing information density.

## Key Features

* **Blazing Fast Parsing** — Hybrid Python/Rust architecture optimized for speed and efficiency.
* **Form 4 Native Support** — Extracts insider trading transactions into structured datasets.
* **LLM-Optimized Output** — Clean JSON designed for OpenAI, Anthropic, and RAG workflows.
* **Developer Friendly** — Lightweight architecture with minimal dependencies.
* **Production Ready** — Easy integration into data pipelines and backend services.

## Project Structure

```text
sec-edgar-collector/
├── .env                  # Local environment variables (not committed)
├── .env.example          # Environment variable template
├── .github/
│   └── workflows/
│       └── etl_pipeline.yml
├── .gitignore
├── requirements.txt
├── main.py               # Pipeline orchestrator
├── README.md
└── src/
    ├── __init__.py
    ├── ai_analyzer.py    # analyze logic with AI
    ├── collector.py      # SEC collection & parsing logic
    └── db_manager.py     # Database loading layer
```

## Quick Start

```bash
# Clone the repository
git clone https://github.com/whale-brief/sec-edgar-collector.git

cd sec-edgar-collector

# Install dependencies
pip install -r requirements.txt

# Run pipeline
python main.py
```

## Output Example

```json
[
  {
    "ticker": "AAPL",
    "form_type": "4",
    "transaction_date": "2026-06-16",
    "insider_title": "Chief Executive Officer",
    "shares_traded": 15000,
    "transaction_type": "Buy",
    "raw_link": "https://www.sec.gov/..."
  }
]
```

## Contributing

Contributions are welcome.

If you share the vision of making SEC data more accessible for retail investors worldwide, feel free to open an issue or submit a pull request.

## License

This project is licensed under the MIT License.
