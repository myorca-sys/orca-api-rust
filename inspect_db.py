import asyncio
import asyncpg

async def run():
    conn = await asyncpg.connect("postgresql://neondb_owner:npg_0Kb4mhkYXIOd@ep-red-star-a19jjtnh-pooler.ap-southeast-1.aws.neon.tech/neondb?sslmode=require")
    # Get a real user id
    rows = await conn.fetch('SELECT id FROM "user" LIMIT 1')
    if not rows:
        print("No users found!")
    else:
        user_id = rows[0]["id"]
        print(f"Found user: {user_id}")
        # Try insert
        query = """
        INSERT INTO collections ("userId", "animeSlug", "status", "progress", "updatedAt")
        VALUES ($1, $2, $3, $4, CURRENT_TIMESTAMP)
        ON CONFLICT ("userId", "animeSlug") DO UPDATE
        SET status = $3, progress = $4, "updatedAt" = CURRENT_TIMESTAMP
        """
        try:
            await conn.execute(query, user_id, "123", "watching", 1.0)
            print("Success with real user")
        except Exception as e:
            print("Insert error with real user:", e)
            
    await conn.close()

asyncio.run(run())
