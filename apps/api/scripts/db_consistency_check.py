import asyncio
import os
import sys

# Add apps/api to sys.path so we can import from db
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from db.connection import database
from db.models import anime_metadata, anime_mappings, episodes
from sqlalchemy import select, func

async def check_db_consistency():
    print("Connecting to the database...")
    await database.connect()
    print("Connected.\n")
    try:
        # 1. Total anime in the database
        query_total_anime = select(func.count()).select_from(anime_metadata)
        total_anime = await database.execute(query_total_anime)
        print(f"Total anime in database: {total_anime}")

        # 2. Total episodes across all providers
        query_total_episodes = select(func.count()).select_from(episodes)
        total_episodes = await database.execute(query_total_episodes)
        print(f"Total episodes across all providers: {total_episodes}")

        # 3. Total unique anime that have at least one episode
        query_anime_with_eps = select(func.count(episodes.c.anilistId.distinct()))
        unique_anime_with_eps = await database.execute(query_anime_with_eps)
        print(f"Total unique anime with at least one episode: {unique_anime_with_eps}")

        # 4. Total anime with mappings
        query_anime_with_mappings = select(func.count(anime_mappings.c.anilistId.distinct()))
        unique_anime_with_mappings = await database.execute(query_anime_with_mappings)
        print(f"Total unique anime with mappings: {unique_anime_with_mappings}")

        print("\n--- Inconsistencies Checks ---")

        # A. Mappings without metadata (Should be 0 due to FK)
        query_mappings_no_meta = select(func.count()).select_from(anime_mappings).where(
            anime_mappings.c.anilistId.not_in(select(anime_metadata.c.anilistId))
        )
        mappings_no_meta = await database.execute(query_mappings_no_meta)
        print(f"Mappings without metadata (FK failure): {mappings_no_meta}")

        # B. Episodes without metadata (Should be 0 due to FK)
        query_eps_no_meta = select(func.count()).select_from(episodes).where(
            episodes.c.anilistId.not_in(select(anime_metadata.c.anilistId))
        )
        eps_no_meta = await database.execute(query_eps_no_meta)
        print(f"Episodes without metadata (FK failure): {eps_no_meta}")

        # C. Anime with episodes but no mappings
        query_eps_no_mappings = select(func.count(episodes.c.anilistId.distinct())).where(
            episodes.c.anilistId.not_in(select(anime_mappings.c.anilistId))
        )
        eps_no_mappings = await database.execute(query_eps_no_mappings)
        print(f"Unique anime with episodes but NO mappings: {eps_no_mappings}")
        
        # Detail of Anime with episodes but no mappings
        if eps_no_mappings > 0:
            query_eps_no_mappings_ids = select(episodes.c.anilistId.distinct()).where(
                episodes.c.anilistId.not_in(select(anime_mappings.c.anilistId))
            ).limit(10)
            eps_no_mappings_ids = await database.fetch_all(query_eps_no_mappings_ids)
            print(f"  Sample anilistIds with eps but no mappings: {[r[0] for r in eps_no_mappings_ids]}")

        # D. Anime with mappings but 0 episodes
        query_mappings_no_eps = select(func.count(anime_mappings.c.anilistId.distinct())).where(
            anime_mappings.c.anilistId.not_in(select(episodes.c.anilistId))
        )
        mappings_no_eps = await database.execute(query_mappings_no_eps)
        print(f"Unique anime with mappings but NO episodes: {mappings_no_eps}")

        # E. Anime in metadata with NO mappings AND NO episodes (Ghost metadata)
        query_meta_no_data = select(func.count(anime_metadata.c.anilistId)).where(
            anime_metadata.c.anilistId.not_in(select(anime_mappings.c.anilistId))
        ).where(
            anime_metadata.c.anilistId.not_in(select(episodes.c.anilistId))
        )
        meta_no_data = await database.execute(query_meta_no_data)
        print(f"Anime in metadata with NO mappings and NO episodes (Ghost metadata): {meta_no_data}")
        
    except Exception as e:
        print(f"Error during execution: {e}")
    finally:
        await database.disconnect()

if __name__ == "__main__":
    asyncio.run(check_db_consistency())
