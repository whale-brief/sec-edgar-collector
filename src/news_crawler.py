import time
import requests
import logging
from typing import Set
from src.webhook_client import webhook_client

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')

class TickerTickCrawler:
    """
    A compliant crawler utilizing the TickerTick REST API.
    Strictly adheres to the rate limit: max 10 requests per minute.
    """
    def __init__(self):
        self.api_url = "https://api.tickertick.com/feed"
        self.seen_story_ids: Set[str] = set()
        
        # 🛡️ RATE LIMIT PROTECTION 🛡️
        # Polling every 30 seconds (2 requests per minute), well below the 10 req/min limit.
        self.polling_interval_seconds = 30 

    def poll_latest_news(self) -> None:
        """Fetches the latest general market feed and dispatches new items."""
        try:
            # Query the latest 30 stories across the market
            params = {"n": 30}
            response = requests.get(self.api_url, params=params, timeout=10)
            
            if response.status_code == 429:
                logging.warning("⚠️ TickerTick Rate limit hit (429). Backing off...")
                time.sleep(self.polling_interval_seconds * 2)
                return
                
            response.raise_for_status()
            data = response.json()
            
            stories = data.get("stories", [])
            new_stories_count = 0
            
            # Process from oldest to newest in the current batch
            for story in reversed(stories):
                story_id = story.get("id")
                
                if not story_id or story_id in self.seen_story_ids:
                    continue
                
                self.seen_story_ids.add(story_id)
                new_stories_count += 1
                
                # TickerTick provides a 'tags' array representing tickers (e.g., ['aapl', 'msft'])
                # Extract tickers, removing the 'tt:' prefix if present
                raw_tags = story.get("tags", [])
                clean_tickers = [tag.replace('tt:', '').upper() for tag in raw_tags if tag.startswith('tt:')]
                primary_ticker = clean_tickers[0] if clean_tickers else "MARKET"
                
                payload = {
                    "source": "TickerTick",
                    "story_id": story_id,
                    "ticker": primary_ticker,
                    "all_tickers": clean_tickers,
                    "title": story.get("title", "No Title"),
                    "news_link": story.get("url", ""),
                    "published_at": story.get("time", 0)
                }
                
                webhook_client.send("live-news", payload)
            
            if new_stories_count > 0:
                logging.info(f"📰 Dispatched {new_stories_count} new stories from TickerTick.")
                
            # Prevent memory overflow
            if len(self.seen_story_ids) > 2000:
                self.seen_story_ids.clear()

        except requests.exceptions.RequestException as e:
            logging.error(f"❌ Network error during TickerTick polling: {e}")

    def run_continuous_watcher(self) -> None:
        logging.info("🚀 Starting TickerTick News Crawler...")
        while True:
            self.poll_latest_news()
            time.sleep(self.polling_interval_seconds)

if __name__ == "__main__":
    crawler = TickerTickCrawler()
    crawler.run_continuous_watcher()