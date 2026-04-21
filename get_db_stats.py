import asyncio
import json
from apps.api.db.connection import database
from sqlalchemy import text

async def get_stats():
    await database.connect()
    try:
        total_anime = await database.fetch_val(text("SELECT COUNT(*) FROM anime_metadata"))
        total_episodes = await database.fetch_val(text("SELECT COUNT(*) FROM episodes"))
        
        # Get genres
        genres_rows = await database.fetch_all(text("SELECT genres FROM anime_metadata"))
        unique_genres = set()
        for row in genres_rows:
            if row['genres']:
                try:
                    genres = json.loads(row['genres']) if isinstance(row['genres'], str) else row['genres']
                    unique_genres.update(genres)
                except:
                    pass
                    
        total_genres = len(unique_genres)
        
        # Get video cache to check streams and proxies
        video_caches = await database.fetch_all(text("SELECT payload FROM video_cache"))
        
        direct_stream_count = 0
        tg_proxy_count = 0
        
        for vc in video_caches:
            payload_str = vc['payload']
            try:
                payload = json.loads(payload_str) if isinstance(payload_str, str) else payload_str
                if not payload: continue
                
                sources = payload.get('sources', [])
                downloads = payload.get('downloads', [])
                
                has_direct = False
                has_tg = False
                
                for s in sources:
                    url = s.get('url', '')
                    if 'tg' in url.lower() or 'proxy' in url.lower() or 't.me' in url.lower():
                        has_tg = True
                    else:
                        has_direct = True
                        
                for d in downloads:
                    url = d.get('url', '')
                    if 'tg' in url.lower() or 'proxy' in url.lower() or 't.me' in url.lower():
                        has_tg = True
                        
                if has_direct: direct_stream_count += 1
                if has_tg: tg_proxy_count += 1
            except Exception as e:
                pass
                
        print("=== DATABASE STATS ===")
        print(f"Total Anime: {total_anime}")
        print(f"Total Episodes: {total_episodes}")
        print(f"Total Unique Genres: {total_genres}")
        print(f"Episodes with Direct Stream in Cache: {direct_stream_count}")
        print(f"Episodes with TG Proxy in Cache: {tg_proxy_count}")
        print(f"Genres List: {', '.join(sorted(unique_genres))}")
        
    finally:
        await database.disconnect()

if __name__ == "__main__":
    asyncio.run(get_stats())
