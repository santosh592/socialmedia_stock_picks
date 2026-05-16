from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class RedditPostData:
    id: str
    subreddit: str
    author: str
    created_utc: datetime
    title: str
    body: str | None
    url: str | None
    score: int
    num_comments: int
    flair: str | None
    permalink: str


@dataclass
class RedditCommentData:
    id: str
    post_id: str
    parent_id: str | None
    author: str
    created_utc: datetime
    body: str
    score: int
    permalink: str


@dataclass
class IngestStats:
    posts_fetched: int = 0
    comments_fetched: int = 0
    mentions_created: int = 0
    errors: list[str] = field(default_factory=list)
