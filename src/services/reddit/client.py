from __future__ import annotations

"""Reddit API client placeholder.

Implement with asyncpraw or OAuth2 + httpx per docs/SPEC.md.
"""


class RedditClient:
    def __init__(self, client_id: str, client_secret: str, user_agent: str) -> None:
        self.client_id = client_id
        self.client_secret = client_secret
        self.user_agent = user_agent

    async def fetch_subreddit_posts(self, subreddit: str, sort: str, limit: int) -> list[dict]:
        raise NotImplementedError("Reddit ingest not wired yet — add asyncpraw in services/reddit/")
