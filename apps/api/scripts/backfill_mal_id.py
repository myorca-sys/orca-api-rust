import asyncio
import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), "apps/api"))
from db.connection import database
from services.anilist import fetch_anilist_info_by_id

async def main():
    await database.connect()
    
    query = """
        SELECT c.id, c.anilist_id 
        FROM canonical_anime c
        JOIN anime_metadata m ON m."anilistId" = c.anilist_id
        WHERE c.mal_id IS NULL
        ORDER BY m.popularity DESC NULLS LAST
    """
    rows = await database.fetch_all(query)
    print(f"Found {len(rows)} canonical animes missing mal_id. Prioritizing popular ones first.")
    
    for row in rows:
        canonical_id = row["id"]
        anilist_id = row["anilist_id"]
        
        try:
            data = await fetch_anilist_info_by_id(anilist_id)
            if data and data.get("mal_id"):
                mal_id = data["mal_id"]
                await database.execute(
                    "UPDATE canonical_anime SET mal_id = :mal_id WHERE id = :cid",
                    {"mal_id": mal_id, "cid": canonical_id}
                )
                print(f"Updated anilist_id={anilist_id} with mal_id={mal_id}")
            else:
                print(f"No mal_id found for anilist_id={anilist_id}")
        except Exception as e:
            print(f"Error on anilist_id={anilist_id}: {e}")
            
        await asyncio.sleep(0.7) # Respect AniList 90 req/min limit
    
    print("Backfill mal_id completed.")
    await database.disconnect()

asyncio.run(main())
