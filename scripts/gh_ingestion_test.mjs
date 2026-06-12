const query = process.env.TARGET_QUERY || "Classroom of the Elite";

async function testProviderHF(providerName) {
  console.log(`\n--- Testing ${providerName.toUpperCase()} via HF Space for '${query}' ---`);
  const url = `https://orcanime-orcanime-api-rust.hf.space/api/v1/anime/search/${encodeURIComponent(query)}?provider=${providerName.toLowerCase()}`;
  
  try {
    const res = await fetch(url);
    const json = await res.json();
    
    console.log(`[${providerName}] HF HTTP Status: ${res.status}`);
    
    if (json.success) {
      console.log(`✅ [${providerName}] SUCCESS! Found ${json.results.length} results.`);
      for (let i = 0; i < Math.min(3, json.results.length); i++) {
        console.log(`   - ${json.results[i].title}`);
        console.log(`     URL: ${json.results[i].url}`);
      }
    } else {
      console.log(`❌ [${providerName}] API ERROR: ${json.error}`);
    }
  } catch (err) {
    console.error(`❌ [${providerName}] Request Error: ${err.message}`);
  }
}

async function main() {
  console.log(`Starting GitHub Actions Pipeline Test...`);
  console.log(`Target: Hugging Face API`);
  console.log(`Query: ${query}`);
  
  await testProviderHF("Samehadaku");
  await testProviderHF("Kuronime");
  
  console.log("\n--- TEST COMPLETED ---");
}

main();