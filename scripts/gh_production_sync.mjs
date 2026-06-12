import postgres from "postgres";

const query = process.env.TARGET_QUERY || "Classroom of the Elite Season 4";
const sql = postgres(process.env.DATABASE_URL);

async function syncAnime() {
  console.log(`🚀 STARTING PRODUCTION SYNC FOR: ${query}`);
  
  try {
    // 1. Resolve & Search via HF API
    const searchUrl = `https://orcanime-orcanime-api-rust.hf.space/api/v1/anime/search/${encodeURIComponent(query)}?provider=samehadaku`;
    const searchRes = await fetch(searchUrl);
    const searchJson = await searchRes.json();
    
    if (!searchJson.success || searchJson.results.length === 0) {
      console.log("❌ No results found on HF API");
      return;
    }

    const target = searchJson.results[0];
    console.log(`✅ Found on Provider: ${target.title}`);

    // 2. Fetch Episodes via HF API
    const epUrl = `https://orcanime-orcanime-api-rust.hf.space/api/v1/anime/episodes?provider=samehadaku&url=${encodeURIComponent(target.url)}`;
    const epRes = await fetch(epUrl);
    const epJson = await epRes.json();
    
    if (!epJson.success || epJson.episodes.length === 0) {
      console.log("❌ No episodes extracted from HF API");
      return;
    }

    console.log(`✅ Extracted ${epJson.episodes.length} episodes from remote scraper.`);

    // 3. Database Sync
    // Find the media_id in Supabase
    const media = await sql`
      SELECT id FROM media_metadata 
      WHERE title_main ILIKE '%Classroom of the Elite 4th Season%' 
         OR title_main ILIKE '%Youkoso Jitsuryoku%4th%'
      LIMIT 1
    `;

    if (media.length === 0) {
      console.log("❌ Media Metadata not found in DB. Ingest metadata first.");
      return;
    }

    const mediaId = media[0].id;
    console.log(`🔗 Mapping to Media ID: ${mediaId}`);

    // Insert episodes
    const contentValues = epJson.episodes.map(ep => ({
      media_id: mediaId,
      content_type: 'EPISODE',
      number: ep.number.toString(),
      title: ep.title,
      provider_id: 'samehadaku'
    }));

    // Use simple conflict handling or delete existing first for this PoC
    await sql`DELETE FROM media_content WHERE media_id = ${mediaId} AND provider_id = 'samehadaku'`;
    await sql`INSERT INTO media_content ${sql(contentValues)}`;
    
    console.log(`🎉 SUCCESS! Synchronized ${contentValues.length} episodes to Supabase.`);

  } catch (err) {
    console.error("❌ Sync Error:", err.message);
  } finally {
    await sql.end();
    process.exit(0);
  }
}

syncAnime();

