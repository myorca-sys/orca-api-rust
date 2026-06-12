import postgres from "postgres";

const sql = postgres(process.env.DATABASE_URL);
const HF_API_URL = "https://orcanime-orcanime-api-rust.hf.space/api/v1";

async function multiProviderSync() {
  console.log("🚀 STARTING MULTI-PROVIDER PRODUCTION SYNC...");
  
  try {
    const animeList = await sql`
      SELECT id, title_main FROM media_metadata 
      WHERE media_type = 'ANIME'
    `;

    console.log(`📊 Processing ${animeList.length} anime for dual-source sync.`);

    for (const anime of animeList) {
      console.log(`\nAnime: ${anime.title_main}`);
      const providers = ['samehadaku', 'kuronime'];
      
      for (const provider of providers) {
        console.log(`   -> Syncing from ${provider.toUpperCase()}...`);
        try {
          // 1. Search (Smart Search logic already in HF API)
          const searchUrl = `${HF_API_URL}/anime/search/${encodeURIComponent(anime.title_main)}?provider=${provider}`;
          const searchRes = await fetch(searchUrl);
          const searchJson = await searchRes.json();

          if (searchJson.success && searchJson.results.length > 0) {
            const target = searchJson.results[0];
            
            // 2. Fetch Episode List
            const epUrl = `${HF_API_URL}/anime/episodes?provider=${provider}&url=${encodeURIComponent(target.url)}`;
            const epRes = await fetch(epUrl);
            const epJson = await epRes.json();

            if (epJson.success && epJson.episodes.length > 0) {
              const contentValues = epJson.episodes.map(ep => ({
                media_id: anime.id,
                content_type: 'EPISODE',
                number: ep.number.toString(),
                title: ep.title,
                provider_id: provider
              }));

              // 3. Upsert (Delete old for this provider, Insert new)
              await sql`DELETE FROM media_content WHERE media_id = ${anime.id} AND provider_id = ${provider}`;
              await sql`INSERT INTO media_content ${sql(contentValues)}`;
              console.log(`      ✅ Added ${contentValues.length} episodes.`);
            }
          } else {
             console.log(`      ⚠️ No results found on ${provider}.`);
          }
        } catch (e) {
          console.error(`      ❌ Provider Error: ${e.message}`);
        }
      }
      // Anti-rate limit
      await new Promise(r => setTimeout(r, 1000));
    }

    console.log("\n✅ ALL PROVIDERS SYNCED SUCCESSFULLY.");
  } catch (err) {
    console.error("❌ Pipeline Error:", err.message);
  } finally {
    await sql.end();
    process.exit(0);
  }
}

multiProviderSync();
