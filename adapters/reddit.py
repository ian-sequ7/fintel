"""
Reddit adapter for sentiment analysis.

Sources:
- r/stocks
- r/wallstreetbets
- r/investing

Uses public JSON API (no auth required).
"""

import json
import urllib.request
import urllib.error
from dataclasses import dataclass
from datetime import datetime

from domain import Observation, Category
from ports import FetchError, RateLimitError
from config import get_settings

from .base import BaseAdapter


@dataclass
class RedditPost:
    """Typed Reddit post data."""
    title: str
    selftext: str
    score: int
    num_comments: int
    created_utc: datetime
    subreddit: str
    url: str
    author: str


# Subreddits for financial sentiment
FINANCE_SUBREDDITS = [
    "stocks",
    "wallstreetbets",
    "investing",
]


class RedditAdapter(BaseAdapter):
    """
    Reddit sentiment data adapter.

    Fetches posts from finance subreddits for sentiment analysis.
    """

    BASE_URL = "https://www.reddit.com"

    @property
    def source_name(self) -> str:
        return "reddit"

    @property
    def category(self) -> Category:
        return Category.SENTIMENT

    @property
    def reliability(self) -> float:
        return 0.6  # User-generated content, lower reliability

    def _request(self, url: str) -> dict:
        """Make HTTP request to Reddit API."""
        settings = get_settings()
        headers = {"User-Agent": settings.user_agent}
        req = urllib.request.Request(url, headers=headers)

        try:
            with urllib.request.urlopen(req, timeout=settings.request_timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            if e.code == 429:
                raise RateLimitError()
            raise FetchError(self.source_name, f"HTTP {e.code}: {e.reason}")
        except urllib.error.URLError as e:
            raise FetchError(self.source_name, f"Connection error: {e.reason}")

    def _fetch_impl(self, **kwargs) -> list[Observation]:
        """Fetch posts from finance subreddits."""
        subreddits = kwargs.get("subreddits", FINANCE_SUBREDDITS)
        limit = kwargs.get("limit", 25)
        sort = kwargs.get("sort", "hot")  # hot, new, top

        if isinstance(subreddits, str):
            subreddits = [subreddits]

        observations = []

        for subreddit in subreddits:
            url = f"{self.BASE_URL}/r/{subreddit}/{sort}.json?limit={limit}"

            try:
                data = self._request(url)
            except FetchError:
                continue  # Try other subreddits

            posts = data.get("data", {}).get("children", [])

            for post_data in posts:
                post = post_data.get("data", {})

                # Skip pinned/stickied posts
                if post.get("stickied"):
                    continue

                created = datetime.fromtimestamp(post.get("created_utc", 0))

                reddit_post = RedditPost(
                    title=post.get("title", ""),
                    selftext=post.get("selftext", "")[:500],  # Truncate
                    score=post.get("score", 0),
                    num_comments=post.get("num_comments", 0),
                    created_utc=created,
                    subreddit=subreddit,
                    url=f"https://reddit.com{post.get('permalink', '')}",
                    author=post.get("author", ""),
                )

                observations.append(Observation(
                    source=self.source_name,
                    timestamp=created,
                    category=Category.SENTIMENT,
                    data={
                        "title": reddit_post.title,
                        "text": reddit_post.selftext,
                        "score": reddit_post.score,
                        "comments": reddit_post.num_comments,
                        "subreddit": reddit_post.subreddit,
                        "url": reddit_post.url,
                    },
                    ticker=self._extract_ticker(reddit_post.title),
                    reliability=self.reliability,
                ))

        if not observations:
            raise FetchError(self.source_name, "No posts retrieved")

        return observations

    def _extract_ticker(self, text: str) -> str | None:
        """Extract potential ticker symbol from text (simple heuristic)."""
        import re

        # Look for $TICKER pattern
        match = re.search(r'\$([A-Z]{1,5})\b', text)
        if match:
            return match.group(1)

        # Look for standalone uppercase 2-5 letter words
        # (very rough heuristic, would need refinement)
        return None

    def get_wallstreetbets(self, limit: int = 25) -> list[Observation]:
        """Get posts from r/wallstreetbets."""
        return self.fetch(subreddits=["wallstreetbets"], limit=limit)

    def get_stocks(self, limit: int = 25) -> list[Observation]:
        """Get posts from r/stocks."""
        return self.fetch(subreddits=["stocks"], limit=limit)

    def get_all(self, limit: int = 25) -> list[Observation]:
        """Get posts from all finance subreddits."""
        return self.fetch(subreddits=FINANCE_SUBREDDITS, limit=limit)
