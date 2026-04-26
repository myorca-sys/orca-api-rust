import asyncio
import os
import time
import httpx
from db.connection import database
from services.pipeline import PROVIDERS, sync_anime_episodes
from services.reconciler import reconciler
from services.db import upsert_anime_db
from services.anilist import fetch_anilist_info_by_id
from utils.distributed_lock import DistributedLock
from services.cache import upstash_get, upstash_set, upstash_del, client, UPSTASH_REDIS_REST_URL, UPSTASH_REDIS_REST_TOKEN

TELEGRAM_BOT_TOKEN_2 = os.getenv("TELEGRAM_BOT_TOKEN_2")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

async def log_to_redis(message: str):
    try:
        url = f"{UPSTASH_REDIS_REST_URL}/lpush/hf_ingest_logs"
        headers = {"Authorization": f"Bearer {UPSTASH_REDIS_REST_TOKEN}", "Content-Type": "application/json"}
        await client.post(url, headers=headers, json=[message])
        await client.get(f"{UPSTASH_REDIS_REST_URL}/ltrim/hf_ingest_logs/0/49", headers=headers)
    except:
        pass

async def send_tele_alert(message: str):
    await log_to_redis(f"🔔 [TELEGRAM] {message}")
    if not TELEGRAM_BOT_TOKEN_2 or not TELEGRAM_CHAT_ID:
        await log_to_redis(f"❌ [TeleAlert] Token atau Chat ID kosong: {TELEGRAM_BOT_TOKEN_2} | {TELEGRAM_CHAT_ID}")
        return
        
    tg_proxy = os.getenv("TG_PROXY_BASE_URL", "https://api.telegram.org")
    url = f"{tg_proxy}/bot{TELEGRAM_BOT_TOKEN_2}/sendMessage"
    
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "HTML",
        "disable_web_page_preview": True
    }
    try:
        async with httpx.AsyncClient() as client_http:
            res = await client_http.post(url, json=payload, timeout=10)
            if res.status_code != 200:
                await log_to_redis(f"❌ [TeleAlert] API Error {res.status_code}: {res.text}")
    except Exception as e:
        await log_to_redis(f"❌ [TeleAlert] Gagal kirim pesan (Proxy/Network): {str(e) or repr(e)}")
        print(f"[TeleAlert] Gagal kirim pesan: {e}")

async def run_10_hours_sync():
    await set_state("run_10_hours_sync started")
    await log_to_redis("🚀 [10H-Sync] Task dipanggil!")
    await set_state("lock acquired")
    lock = DistributedLock(
        upstash_get_fn=upstash_get,
        upstash_set_fn=upstash_set,
        upstash_del_fn=upstash_del,
        key="sync_10_hours_lock"
    )
    try:
        async with lock:
            await set_state("lock block entered")
            await _run_sync_logic()
    except TimeoutError:
        await set_state("timeout error")
        print("[10H-Sync] Proses lain sedang berjalan. Membatalkan eksekusi ini.")
    except Exception as e:
        await set_state(f"exception: {str(e)}")
        import traceback
        err = traceback.format_exc()
        print(f"[10H-Sync] Error fatal: {e}\n{err}")
        await send_tele_alert(f"❌ <b>[10H-SYNC] ERROR FATAL:</b>\n<pre>{e}</pre>")

async def set_state(state: str):
    await upstash_set("10h_sync_status", {"state": state, "time": time.time()}, ex=3600)

async def _run_sync_logic():
    await set_state("Entering _run_sync_logic")
    print("🚀 [10H-Sync] Mengambil 2400 Anime (Prioritas ONGOING, lalu Terpopuler)...")
    await set_state("Sending tele alert 1")
    await send_tele_alert("🚀 <b>[10H-SYNC] STARTED:</b> Mencari maksimal 2400 anime tanpa episode dari Database...")
    
    query = """
        SELECT m."anilistId", m."cleanTitle", m."popularity", m."status"
        FROM anime_metadata m
        WHERE NOT EXISTS (
            SELECT 1 FROM episodes e WHERE e."anilistId" = m."anilistId"
        )
        AND m."popularity" IS NOT NULL
        ORDER BY 
            CASE WHEN m.status = 'RELEASING' THEN 0 ELSE 1 END,
            m.popularity DESC NULLS LAST
        LIMIT 2400
    """
    
    await set_state("Executing DB query")
    rows = await database.fetch_all(query)
    await set_state(f"DB query complete, rows: {len(rows)}")
    
    if not rows:
        msg = "✅ [10H-Sync] Tidak ada anime tanpa episode tersisa di Database."
        print(msg)
        await send_tele_alert(f"✅ <b>[10H-SYNC] SELESAI:</b> Tidak ada antrean tersisa.")
        return
        
    releasing_count = sum(1 for r in rows if r["status"] == 'RELEASING')
    
    msg_start = (
        f"🎯 <b>[10H-SYNC] TARGET DITEMUKAN:</b> {len(rows)} judul.\n"
        f"🔥 <i>ONGOING:</i> {releasing_count} judul.\n"
        f"🥶 <i>LAWAS:</i> {len(rows) - releasing_count} judul.\n"
        f"⏱ <i>Estimasi Waktu:</i> {(len(rows) * 15) // 3600} Jam."
    )
    print(msg_start.replace("<b>", "").replace("</b>", "").replace("<i>", "").replace("</i>", ""))
    await send_tele_alert(msg_start)
    
    search_providers = {name: p for name, p in PROVIDERS.items() if hasattr(p, 'search') and callable(getattr(p, 'search'))}
    
    async def process_anime(row):
        anilist_id = row["anilistId"]
        title = row["cleanTitle"]
        status = row["status"]
        
        anilist_data = await fetch_anilist_info_by_id(anilist_id)
        if not anilist_data: return
            
        await upsert_anime_db(anilist_data.copy(), "anilist_search", str(anilist_id))
            
        search_msg = f"🔍 <b>[SEARCHING]</b> {title} (ID: <code>{anilist_id}</code>)"
        print(f"[{time.strftime('%H:%M:%S')}] {search_msg.replace('<b>', '').replace('</b>', '').replace('<code>', '').replace('</code>', '')}")
        await send_tele_alert(search_msg)
        
        found = False
        for name, provider in search_providers.items():
            if found: break
            try:
                search_title = anilist_data.get("romajiTitle") or title
                results = await provider.search(search_title)
                if results and len(results) > 0:
                    for best_match in results[:3]:
                        provider_slug = best_match.get("slug") or best_match.get("url").strip("/").split("/")[-1]
                        
                        if provider_slug:
                            recon_res = await reconciler.reconcile(name, provider_slug, best_match.get('title', search_title))
                            
                            if recon_res and recon_res.canonical_anilist_id == anilist_id:
                                mapping_msg = f"🔗 <b>[MAPPED]</b> Ketemu di {name}!\nTitle: <i>{best_match.get('title')}</i>"
                                print(f"  [+] {mapping_msg.replace('<b>', '').replace('</b>', '').replace('<i>', '').replace('</i>', '')}")
                                await send_tele_alert(mapping_msg)
                                
                                anilist_data_copy = anilist_data.copy()
                                anilist_data_copy["anilistId"] = recon_res.canonical_anilist_id
                                anilist_data_copy["cleanTitle"] = recon_res.canonical_title
                                await upsert_anime_db(anilist_data_copy, name, provider_slug)
                                
                                found = True
                                break
            except Exception as e:
                err_str = str(e)
                if "429" in err_str or "Quota" in err_str:
                    print(f"  [!] Rate Limit Gemini di {name}.")
                elif "403" in err_str or "Forbidden" in err_str:
                    print(f"  [!] Blocked (403) oleh {name} Anti-Bot.")
                    await send_tele_alert(f"🛑 <b>[BLOCKED 403]</b> Akses ke {name} ditolak oleh Cloudflare/Anti-Bot!")
                else:
                    print(f"  [!] Error search {name}: {err_str}")
                pass 
                
        if found:
            print(f"🔄 Memulai sync episodes untuk {title}...")
            res = await sync_anime_episodes(anilist_id)
            sync_msg = f"✅ <b>[SYNCED]</b> {title}\nBerhasil menarik: <b>{res.get('added', 0)} eps baru</b> & {res.get('updated', 0)} eps update."
            print(sync_msg.replace("<b>", "").replace("</b>", ""))
            await send_tele_alert(sync_msg)
        else:
            fail_msg = f"⚠️ <b>[FAILED]</b> Tidak menemukan sumber episode valid untuk {title}."
            print(fail_msg.replace("<b>", "").replace("</b>", ""))
            await send_tele_alert(fail_msg)

    for i, r in enumerate(rows):
        await process_anime(r)
        if i < len(rows) - 1:
            await asyncio.sleep(15) 
        
    end_msg = "🎉 <b>[10H-SYNC] COMPLETE:</b> Selesai mencari 2400 anime."
    print(end_msg.replace("<b>", "").replace("</b>", ""))
    await send_tele_alert(end_msg)