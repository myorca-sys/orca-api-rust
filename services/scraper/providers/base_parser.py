from abc import ABC, abstractmethod
from typing import TypedDict

class EpisodeItem(TypedDict):
    number: float
    title: str
    url: str
    thumbnail: str | None

class AnimeDetail(TypedDict):
    episodes: list[EpisodeItem]
    poster: str | None
    synopsis: str
    air_day: str | None
    genres_local: list[str]
    score_local: float | None
    views_local: int | None
    total_episodes: int | None
    studio: str | None
    status_local: str | None

class EpisodeSource(TypedDict):
    provider: str
    quality: str
    url: str
    type: str

class BaseParser(ABC):
    """Pure DOM logic — zero HTTP calls."""

    @abstractmethod
    def parse_episode_list(self, html: str, base_url: str) -> AnimeDetail:
        ...

    @abstractmethod
    def parse_episode_sources(self, html: str) -> list[EpisodeSource]:
        ...