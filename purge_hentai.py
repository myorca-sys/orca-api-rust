import asyncio
import json
from apps.api.db.connection import database
from sqlalchemy import text

async def purge_hentai():
    await database.connect()
    try:
        # Find all anime with 'Hentai' in genres
        rows = await database.fetch_all(text("SELECT \"anilistId\", \"cleanTitle\", genres FROM anime_metadata"))
        
        hentai_ids = []
        for row in rows:
            if row['genres']:
                try:
                    genres = json.loads(row['genres']) if isinstance(row['genres'], str) else row['genres']
                    if 'Hentai' in genres:
                        hentai_ids.append(row['anilistId'])
                except:
                    pass
                    
        if not hentai_ids:
            print("No Hentai anime found in the database. It is clean.")
            return
            
        print(f"Found {len(hentai_ids)} Hentai anime. Proceeding to delete to the roots...")
        
        # PostgreSQL handles CASCADE deletion for foreign keys like anime_mappings, episodes, etc.
        # But we can also be explicit if we want.
        
        placeholders = ', '.join([str(id) for id in hentai_ids])
        
        # 1. Delete from episodes (and their video_caches if we could link them, but video_caches expire anyway or we can delete by providerId)
        # 2. Delete from anime_mappings
        # 3. Delete from anime_metadata
        
        # Delete video cache associated with these episodes
        episodes = await database.fetch_all(text(f"SELECT \"episodeUrl\" FROM episodes WHERE \"anilistId\" IN ({placeholders})"))
        ep_urls = [ep['episodeUrl'] for ep in episodes]
        
        if ep_urls:
            ep_placeholders = ', '.join([f"'{url}'" for url in ep_urls])
            await database.execute(text(f"DELETE FROM video_cache WHERE \"episodeUrl\" IN ({ep_placeholders})"))
            print(f"Deleted {len(ep_urls)} associated video cache entries.")
            
        # Execute deletions
        await database.execute(text(f"DELETE FROM episodes WHERE \"anilistId\" IN ({placeholders})"))
        print("Deleted episodes.")
        
        await database.execute(text(f"DELETE FROM anime_mappings WHERE \"anilistId\" IN ({placeholders})"))
        print("Deleted anime mappings.")
        
        await database.execute(text(f"DELETE FROM comments WHERE \"anilistId\" IN ({placeholders})"))
        print("Deleted comments.")
        
        await database.execute(text(f"DELETE FROM episode_likes WHERE \"anilistId\" IN ({placeholders})"))
        print("Deleted episode likes.")
        
        await database.execute(text(f"DELETE FROM watch_events WHERE \"anilistId\" IN ({placeholders})"))
        print("Deleted watch events.")
        
        # Finally delete metadata
        deleted_meta = await database.execute(text(f"DELETE FROM anime_metadata WHERE \"anilistId\" IN ({placeholders})"))
        print(f"Deleted {deleted_meta} anime metadata entries.")
        
        print("✅ Purge completed successfully. Roots removed.")
        
    finally:
        await database.disconnect()

if __name__ == "__main__":
    asyncio.run(purge_hentai())
