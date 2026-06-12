const query = process.env.TARGET_QUERY || "Nippon Sangoku";

async function testProvider(name, baseUrl, isKuronime = false) {
  console.log(`\n--- Testing ${name} for '${query}' ---`);
  const url = `${baseUrl}?s=${encodeURIComponent(query)}`;
  
  try {
    const res = await fetch(url, {
      headers: {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36',
        'Referer': baseUrl,
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5'
      }
    });
    
    console.log(`[${name}] HTTP Status: ${res.status}`);
    const html = await res.text();
    
    if (html.includes("Just a moment...") || html.includes("challenges.cloudflare.com")) {
      console.log(`❌ [${name}] BLOCKED BY CLOUDFLARE (Challenge detected)`);
      console.log(`   Length: ${html.length} bytes`);
    } else {
      console.log(`✅ [${name}] CLOUDFLARE PASSED`);
      if (html.toLowerCase().includes(query.toLowerCase())) {
        console.log(`🔍 [${name}] Keyword found in HTML.`);
      } else {
         console.log(`⚠️ [${name}] Content loaded, but keyword not found.`);
      }
    }
  } catch (err) {
    console.error(`❌ [${name}] Request Error: ${err.message}`);
  }
}

async function main() {
  console.log(`Starting GitHub Actions Scraper Test from Datacenter IP...`);
  await testProvider("Samehadaku", "https://v2.samehadaku.how/");
  await testProvider("Kuronime", "https://kuronime.sbs/", true);
  console.log("\n--- TEST COMPLETED ---");
}

main();
