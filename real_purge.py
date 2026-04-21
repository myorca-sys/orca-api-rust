import asyncio
import json
from apps.api.db.connection import database
from sqlalchemy import text

async def purge():
    await database.connect()
    try:
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
                    
        print(f"Remaining Hentai anime: {len(hentai_ids)}")
        if not hentai_ids:
            return
            
        for aid in hentai_ids:
            try:
                await database.execute(text(f"DELETE FROM episodes WHERE \"anilistId\" = {aid}"))
                await database.execute(text(f"DELETE FROM anime_mappings WHERE \"anilistId\" = {aid}"))
                await database.execute(text(f"DELETE FROM comments WHERE \"anilistId\" = {aid}"))
                await database.execute(text(f"DELETE FROM episode_likes WHERE \"anilistId\" = {aid}"))
                await database.execute(text(f"DELETE FROM watch_events WHERE \"anilistId\" = {aid}"))
                await database.execute(text(f"DELETE FROM anime_metadata WHERE \"anilistId\" = {aid}"))
                print(f"Deleted {aid}")
            except Exception as e:
                print(f"Failed {aid}: {e}")
                
        print("Done!")
    finally:
        await database.disconnect()

asyncio.run(purge())
