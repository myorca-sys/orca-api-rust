import asyncio
import os
from dotenv import load_dotenv

load_dotenv("apps/api/.env")
db_url = os.getenv("DATABASE_URL")
if db_url and db_url.startswith("postgresql://"):
    db_url = db_url.replace("postgresql://", "postgresql+asyncpg://", 1)

from databases import Database

async def check_tensura():
    db = Database(db_url)
    await db.connect()
    
    print("\n--- Cari ID Anilist Tensura (Slime) ---")
    query_search = """
        SELECT "anilistId", "cleanTitle", "nativeTitle"
        FROM anime_metadata
        WHERE "cleanTitle" ILIKE '%slime%' OR "cleanTitle" ILIKE '%tensura%'
        LIMIT 10
    """
    try:
        rows = await db.fetch_all(query_search)
        if not rows:
            print("Tidak ada anime dengan judul slime/tensura di tabel 'anime_metadata'.")
        else:
            for row in rows:
                print(dict(row))
                
            # Cek episode untuk setiap anime yang ditemukan
            for row in rows:
                anilist_id = row['anilistId']
                print(f"\n--- Episode Mappings untuk {row['cleanTitle']} (ID: {anilist_id}) ---")
                
                # Check episode mappings
                query_eps = """
                    SELECT "providerId", "episodeNumber", "episodeUrl"
                    FROM episodes
                    WHERE "anilistId" = :anilist_id
                    ORDER BY "episodeNumber" ASC
                """
                eps = await db.fetch_all(query_eps, values={"anilist_id": anilist_id})
                if not eps:
                    print("Tidak ada episode tersimpan.")
                else:
                    for ep in eps:
                        url = ep['episodeUrl']
                        status = "✅ ADA URL" if url else "❌ KOSONG"
                        print(f"Ep {ep['episodeNumber']} ({ep['providerId']}): {status} -> {url[:50] if url else 'None'}...")
                        
                query_eps_count = """
                    SELECT COUNT(*) as total,
                           SUM(CASE WHEN "episodeUrl" IS NOT NULL AND "episodeUrl" != '' THEN 1 ELSE 0 END) as with_url
                    FROM episodes
                    WHERE "anilistId" = :anilist_id
                """
                stats = await db.fetch_one(query_eps_count, values={"anilist_id": anilist_id})
                print(f"Total Episode: {stats['total']} | Dengan URL: {stats['with_url']}")

    except Exception as e:
        print("Error:", e)
        
    await db.disconnect()

if __name__ == "__main__":
    asyncio.run(check_tensura())
