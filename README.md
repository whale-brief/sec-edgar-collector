# SEC EDGAR Collector🐋

![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)
![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)
![Rust](https://img.shields.io/badge/rust-latest-orange.svg)

> High-performance, ultra-lightweight SEC EDGAR filing and Form 4 (Insider Trading) parsing engine. 

## The Motivation

Navigating the SEC EDGAR database is notoriously painful. Existing parsing tools are often bloated, slow, and return deeply nested XMLs that are a nightmare for modern AI pipelines to process. 

More importantly, real-time financial data—especially insider trading signals (Form 4)—is typically locked behind expensive proprietary terminals or buried in dense legal English. This creates a massive information and language barrier for global retail investors. 

I built `sec-edgar-collector` to level the playing field. It strips away the noise, transforming heavy SEC feeds into clean, structured JSON payloads. The goal is simple: break down the language and technical barriers of the US stock market, giving retail investors anywhere in the world the exact same edge as institutional players.

## Optimized for LLMs & RAG Pipelines

This collector isn't just another web scraper. The data output is deliberately shaped for modern context windows. 

The resulting JSON format is highly optimized for prompt injection and Retrieval-Augmented Generation (RAG) pipelines. By eliminating redundant HTML/XML tags, it ensures you aren't wasting API tokens. Whether you are piping this data directly into GPT-4o for instant multilingual summarization or building an automated financial sentiment analysis tool, this engine delivers the context exactly how LLMs want to read it.

## Key Features

- **Blazing Fast Parsing:** Built with a hybrid Python/Rust approach for optimal speed and memory efficiency.
- **Form 4 Focused:** Natively extracts and structures Insider Trading metrics instantly.
- **Token-Efficient Output:** Outputs clean JSON, minimizing token usage for OpenAI API integrations.
- **Developer Friendly:** Zero heavy dependencies, drop-in ready for existing backend architectures.

## Quick Start

```bash
# Clone the repository
git clone [https://github.com/whale-brief/sec-edgar-collector.git](https://github.com/whale-brief/sec-edgar-collector.git)
cd sec-edgar-collector

# Run the parser
python collector.py

(Output Example optimized for LLM Context Windows)

# JSON
[
  {
    "ticker": "AAPL",
    "form_type": "4",
    "transaction_date": "2026-06-16",
    "insider_title": "Chief Executive Officer",
    "shares_traded": 15000,
    "transaction_type": "Buy",
    "raw_link": "[https://www.sec.gov/](https://www.sec.gov/)..."
  }
]

## Contributing
We welcome contributions. If you share the vision of empowering global retail investors through accessible data, feel free to open a PR.

## License
This project is licensed under the MIT License.
