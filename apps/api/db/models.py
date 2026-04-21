from sqlalchemy import (
    Table, Column, Integer, Float, String, Text, Boolean,
    DateTime, JSON, MetaData, ForeignKey, UniqueConstraint, Index
)
from sqlalchemy.sql import func
from .connection import metadata

# ── existing tables ────────────────────────────────────────────────────────────

anime_metadata = Table(
    "anime_metadata",
    metadata,
    Column("anilistId",       Integer, primary_key=True),
    Column("cleanTitle",      Text,    nullable=False),
    Column("nativeTitle",     Text),
    Column("coverImage",      Text),
    Column("bannerImage",     Text),
    Column("synopsis",        Text),
    Column("score",           Integer),
    Column("status",          Text),
    Column("totalEpisodes",   Integer),
    Column("season",          Text),
    Column("year",            Integer),
    Column("studios",         JSON),
    Column("genres",          JSON),
    Column("recommendations", JSON),
    Column("nextAiringEpisode", JSON),
    Column("popularity",      Integer, default=0),
    Column("trending",        Integer, default=0),
    Column("updatedAt", DateTime, nullable=False, server_default=func.now(), onupdate=func.now()),
)

# ── NEW: Persistent Watch History for Cloud Sync ──────────────────────────────

watch_history = Table(
    "watch_history",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("userId", String, ForeignKey("user.id", ondelete="CASCADE"), nullable=False),
    Column("animeSlug", String, nullable=False),
    Column("episode", Integer, nullable=False),
    Column("timestampSec", Integer, default=0),
    Column("durationSec", Integer, default=0),
    Column("completed", Boolean, default=False),
    Column("updatedAt", DateTime, nullable=False, server_default=func.now(), onupdate=func.now()),
    UniqueConstraint("userId", "animeSlug", "episode", name="uq_user_anime_history_v2"),
)

anime_mappings = Table(
    "anime_mappings",
    metadata,
    Column("id",           Integer, primary_key=True, autoincrement=True),
    Column("anilistId",    Integer, ForeignKey("anime_metadata.anilistId", ondelete="CASCADE"), nullable=False),
    Column("providerId",   Text, nullable=False),   # "oploverz" | "otakudesu" | "samehadaku"
    Column("providerSlug", Text, nullable=False),   # slug on that provider's website
    Column("updatedAt",    DateTime, nullable=False, server_default=func.now(), onupdate=func.now()),
    UniqueConstraint("providerId", "providerSlug", name="anime_mappings_providerId_providerSlug_key"),
)

# ── NEW: structured episode list ───────────────────────────────────────────────
#
# One row = one episode on one provider.
# If an anime has 3 providers, episode 5 appears 3 times (one row per provider).
# The API picks the best provider using priority logic.

episodes = Table(
    "episodes",
    metadata,
    Column("id",            Integer, primary_key=True, autoincrement=True),
    Column("anilistId",     Integer, ForeignKey("anime_metadata.anilistId", ondelete="CASCADE"), nullable=False),
    Column("providerId",    Text,    nullable=False),
    Column("episodeNumber", Float,   nullable=False),   # float to handle ep 12.5, OVA etc
    Column("episodeTitle",  Text),
    Column("episodeUrl",    Text,    nullable=False),   # full URL on the provider site
    Column("thumbnailUrl",  Text),                      # optional cover per episode
    Column("updatedAt",     DateTime, nullable=False, server_default=func.now(), onupdate=func.now()),
    UniqueConstraint("anilistId", "providerId", "episodeNumber", name="uq_episode_provider_num"),
    # Fast lookup: all episodes for an anime
    Index("idx_episodes_anilist_num", "anilistId", "episodeNumber"),
    # Fast lookup: all episodes for a provider
    Index("idx_episodes_provider", "providerId", "anilistId"),
)

# ── NEW: cached resolved video sources ────────────────────────────────────────
#
# Key = episode page URL on the provider site.
# Value = resolved raw video sources (m3u8 / mp4 URLs) that expire after TTL.
# This prevents re-scraping the same episode every time someone presses play.

video_cache = Table(
    "video_cache",
    metadata,
    Column("id",          Integer, primary_key=True, autoincrement=True),
    Column("episodeUrl",  Text,    nullable=False, unique=True),
    Column("providerId",  Text,    nullable=False),
    # JSON shape: {"sources": [{provider, quality, url, type}], "downloads": [...]}
    Column("payload",     JSON,    nullable=False),
    Column("expiresAt",   DateTime, nullable=False),
    Column("updatedAt",   DateTime, nullable=False, server_default=func.now()),
    Index("idx_video_cache_url",     "episodeUrl"),
    Index("idx_video_cache_expires", "expiresAt"),
)

# ── NEW: social & watch behavior ──────────────────────────────────────────────

users = Table(
    "user",
    metadata,
    Column("id", String, primary_key=True),
    Column("name", String, nullable=False),
    Column("email", String, unique=True, nullable=False),
    Column("emailVerified", Boolean, nullable=False, default=False),
    Column("image", Text),
    Column("tier", String, nullable=False, server_default="FREE"),
    Column("subscription_expiry", DateTime, nullable=True),
    Column("createdAt", DateTime, nullable=False, server_default=func.now()),
    Column("updatedAt", DateTime, nullable=False, server_default=func.now(), onupdate=func.now())
)

comments = Table(
    "comments",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("user_id", String, ForeignKey("user.id", ondelete="CASCADE"), nullable=False),
    Column("anilistId", Integer, nullable=False),
    Column("episodeNumber", Float, nullable=False),
    Column("parent_id", Integer, ForeignKey("comments.id", ondelete="CASCADE"), nullable=True),
    Column("text", Text, nullable=False),
    Column("timestamp_sec", Integer, nullable=True),
    Column("created_at", DateTime, nullable=False, server_default=func.now()),
    Index("idx_comments_episode", "anilistId", "episodeNumber"),
)

comment_reactions = Table(
    "comment_reactions",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("comment_id", Integer, ForeignKey("comments.id", ondelete="CASCADE"), nullable=False),
    Column("user_id", String, ForeignKey("user.id", ondelete="CASCADE"), nullable=False),
    Column("emoji", String, nullable=False),
    Column("created_at", DateTime, nullable=False, server_default=func.now()),
    UniqueConstraint("comment_id", "user_id", "emoji", name="uq_reaction_user"),
)

follows = Table(
    "follows",
    metadata,
    Column("follower_id", String, ForeignKey("user.id", ondelete="CASCADE"), primary_key=True),
    Column("following_id", String, ForeignKey("user.id", ondelete="CASCADE"), primary_key=True),
    Column("created_at", DateTime, nullable=False, server_default=func.now()),
)

notifications = Table(
    "notifications",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("user_id", String, ForeignKey("user.id", ondelete="CASCADE"), nullable=False),
    Column("type", String, nullable=False),
    Column("reference_id", String, nullable=False),
    Column("metadata", JSON, nullable=True),
    Column("is_read", Boolean, nullable=False, default=False),
    Column("created_at", DateTime, nullable=False, server_default=func.now()),
    Index("idx_notifications_user", "user_id"),
)

activity_feed = Table(
    "activity_feed",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("user_id", String, ForeignKey("user.id", ondelete="CASCADE"), nullable=False),
    Column("event_type", String, nullable=False),
    Column("metadata", JSON, nullable=False),
    Column("created_at", DateTime, nullable=False, server_default=func.now()),
    Index("idx_activity_feed_user", "user_id", "created_at"),
)

payment_logs = Table(
    "payment_logs",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("provider", String, nullable=False), # "trakteer" | "saweria"
    Column("external_id", String, unique=True),  # ID transaksi dari provider
    Column("amount", Float, nullable=False),
    Column("message", Text),
    Column("user_id", String, ForeignKey("user.id", ondelete="SET NULL"), nullable=True),
    Column("status", String, default="processed"),
    Column("raw_payload", JSON),
    Column("created_at", DateTime, nullable=False, server_default=func.now()),
)

episode_likes = Table(
    "episode_likes",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("user_id", String, ForeignKey("user.id", ondelete="CASCADE"), nullable=False),
    Column("anilistId", Integer, nullable=False),
    Column("episodeNumber", Float, nullable=False),
    Column("created_at", DateTime, nullable=False, server_default=func.now()),
    UniqueConstraint("user_id", "anilistId", "episodeNumber", name="uq_episode_like_user"),
)

watch_events = Table(
    "watch_events",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("user_id", String, ForeignKey("user.id", ondelete="CASCADE"), nullable=False),
    Column("anilistId", Integer, nullable=False),
    Column("episodeNumber", Float, nullable=False),
    Column("event_type", String, nullable=False),
    Column("timestamp_sec", Integer, nullable=True),
    Column("created_at", DateTime, nullable=False, server_default=func.now()),
    Index("idx_watch_events_episode", "anilistId", "episodeNumber"),
)

# ── NEW: Persistent Watch History for Progress Sync ───────────────────────────

collections = Table(
    "collections",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("userId", String, ForeignKey("user.id", ondelete="CASCADE"), nullable=False),
    Column("animeSlug", String, nullable=False),
    Column("status", String, nullable=False, default="plan_to_watch"), # watching, plan_to_watch, completed, dropped
    Column("progress", Float, nullable=False, default=0),
    Column("updatedAt", DateTime, nullable=False, server_default=func.now(), onupdate=func.now()),
    UniqueConstraint("userId", "animeSlug", name="uq_user_anime_collection"),
)
