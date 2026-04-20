import json
import asyncio
import os
import sys
import traceback
from fastapi import APIRouter, HTTPException, Request, Response
from qstash import Receiver
from upstash_workflow.fastapi import Serve
from upstash_workflow import AsyncWorkflowContext
import httpx

# Import services
from services.config import QSTASH_CURRENT_SIGNING_KEY, QSTASH_NEXT_SIGNING_KEY
from services.pipeline import sync_anime_episodes
from services.cleanup import cleanup_expired_cache, vacuum_old_episodes
from services.prefetch import smart_prefetch_episodes
from db.connection import database

# Inisialisasi Router (Hapus prefix ganda)
router = APIRouter()

# Inisialisasi Upstash Workflow Serve
serve = Serve(router)

# Import ingestion engine gracefully
try:
    from services.ingestion.main import IngestionEngine
except Exception as e:
    print(f"[Webhook Init] IngestionEngine import failed: {e}")
    IngestionEngine = None

# Instantiate QStash Receiver if keys are provided
receiver = None
if QSTASH_CURRENT_SIGNING_KEY and QSTASH_NEXT_SIGNING_KEY:
    receiver = Receiver(
        current_signing_key=QSTASH_CURRENT_SIGNING_KEY,
        next_signing_key=QSTASH_NEXT_SIGNING_KEY,
    )

async def _verify_qstash(request: Request):
    if not receiver:
        raise HTTPException(status_code=500, detail="QStash keys not configured on server")

    body = await request.body()
    signature = request.headers.get("Upstash-Signature")

    if not signature:
        raise HTTPException(status_code=400, detail="Missing Upstash-Signature header")

    try:
        api_public_url = os.getenv("API_PUBLIC_URL", "https://jonyyyyyyyu-anime-scraper-api.hf.space").rstrip("/")
        public_url = f"{api_public_url}{request.url.path}"
        
        receiver.verify(
            body=body.decode("utf-8"),
            signature=signature,
            url=public_url
        )
    except Exception as e:
        print(f"[QStash] Invalid Signature: {e}")
        raise HTTPException(status_code=401, detail="Invalid signature")
    
    return body

# --- 🍿 STANDAR WEBHOOKS ---

@router.post("/webhook/sync")
async def sync_webhook(request: Request):
    body = await _verify_qstash(request)
    try:
        payload = json.loads(body)
        anilist_id = payload.get("anilistId")
        if not anilist_id:
            raise ValueError("anilistId missing in payload")
        await sync_anime_episodes(anilist_id)
        return Response(status_code=200, content="Sync Completed")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/webhook/cleanup")
async def cleanup_webhook(request: Request):
    await _verify_qstash(request)
    try:
        await cleanup_expired_cache()
        await vacuum_old_episodes()
        return Response(status_code=200, content="Cleanup Completed")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/webhook/prefetch")
async def prefetch_webhook(request: Request):
    await _verify_qstash(request)
    try:
        result = await smart_prefetch_episodes()
        return Response(status_code=200, content=json.dumps(result))
    except Exception as e:
        print(f"[Webhook] Error running prefetch: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# --- 🚀 LEGACY INGESTION (Needed by QStash) ---

async def _run_ingestion_bg(episode_id, anilist_id, provider_id, episode_number, direct_url):
    try:
        if IngestionEngine is None:
            print("[Webhook] IngestionEngine is not available.")
            return
        engine = IngestionEngine()
        success = await engine.process_episode(episode_id, anilist_id, provider_id, episode_number, direct_url)
        if not success:
             from services.cache import upstash_set
             await upstash_set(f"ingest_error:{anilist_id}:{episode_number}", "IngestionEngine returned False")
    except Exception as e:
        print(f"[Webhook] Background ingestion failed: {e}")
        try:
            from services.cache import upstash_set
            import traceback
            await upstash_set(f"ingest_error:{anilist_id}:{episode_number}", f"{str(e)}\n{traceback.format_exc()}")
        except:
            pass

@router.post("/webhook/ingest")
async def ingest_webhook(request: Request):
    body = await _verify_qstash(request)
    try:
        payload = json.loads(body)
        episode_id = payload.get("episode_id")
        anilist_id = payload.get("anilist_id")
        provider_id = payload.get("provider_id")
        episode_number = payload.get("episode_number")
        direct_url = payload.get("direct_url")
        
        print(f"[Webhook] Executing Ingestion for anilistId={anilist_id} Ep={episode_number}")
        
        # Jalankan di latar belakang agar QStash tidak timeout
        asyncio.create_task(_run_ingestion_bg(episode_id, anilist_id, provider_id, episode_number, direct_url))
        
        return Response(status_code=200, content="Ingestion Queued")
    except Exception as e:
        print(f"[Webhook] Error processing ingestion payload: {e}")
        raise HTTPException(status_code=500, detail=str(e))

async def _run_ingest_batch_bg():
    try:
        import os
        print("[Webhook] Running batch ingestion worker in background...")
        import asyncio.subprocess
        
        env = os.environ.copy()
        # Add apps/api to PYTHONPATH so absolute imports like `from db.connection...` resolve properly
        api_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        env["PYTHONPATH"] = f"{env.get('PYTHONPATH', '')}:{api_dir}".strip(":")
        
        script_path = os.path.join(api_dir, "scripts", "ingest_pending.py")
        
        process = await asyncio.create_subprocess_exec(
            "python", script_path, "--limit", "10",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env
        )
        stdout, stderr = await process.communicate()
        if process.returncode != 0:
            print(f"[Webhook] Batch ingestion worker failed with code {process.returncode}")
            if stderr:
                print(f"[Webhook] Error: {stderr.decode()}")
        else:
            print(f"[Webhook] Batch ingestion worker finished successfully.")
            if stdout:
                print(f"[Webhook] Output: {stdout.decode()}")
    except Exception as e:
        print(f"[Webhook] Batch ingestion worker crashed: {e}")

@router.post("/webhook/ingest-batch")
async def ingest_batch_webhook(request: Request):
    await _verify_qstash(request)
    try:
        print("[Webhook] Executing Batch Ingestion Trigger")
        asyncio.create_task(_run_ingest_batch_bg())
        return Response(status_code=200, content="Batch Ingestion Queued")
    except Exception as e:
        print(f"[Webhook] Error processing batch ingestion payload: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/webhook/triage")
async def triage_webhook(request: Request):
    await _verify_qstash(request)
    try:
        from services.cache import upstash_keys, upstash_get
        error_keys = await upstash_keys("ingest_error:*")
        if not error_keys:
            return Response(status_code=200, content="No errors found. All good.")
        
        # Limit to first 10 errors to avoid spam/OOM
        errors_found = len(error_keys)
        sample_keys = error_keys[:10]
        details = []
        for key in sample_keys:
            val = await upstash_get(key)
            if val:
                # Truncate value if too long
                val_str = str(val)[:100].replace('\n', ' ')
                details.append(f"- `{key}`: {val_str}...")
            else:
                details.append(f"- `{key}`: (No details)")
        
        message = (
            f"🚨 *Auto-Triage Alert: {errors_found} Ingestion Errors* 🚨\n\n"
            f"The system detected *{errors_found}* failed or rate-limited ingestion tasks.\n\n"
            "*Sample Errors:*\n" + "\n".join(details) + "\n\n"
            "⚠️ Please check Hugging Face logs or run the manual resume script."
        )
        
        # Send to Telegram
        bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
        chat_id = os.getenv("TELEGRAM_CHAT_ID")
        
        if bot_token and chat_id:
            async with httpx.AsyncClient() as client:
                res = await client.post(
                    f"https://api.telegram.org/bot{bot_token}/sendMessage",
                    json={
                        "chat_id": chat_id,
                        "text": message,
                        "parse_mode": "Markdown",
                        "reply_markup": {
                            "inline_keyboard": [
                                [
                                    {"text": "🔄 Retry Failed Episodes", "callback_data": "retry_all_errors"},
                                    {"text": "🗑️ Clear Errors", "callback_data": "clear_all_errors"}
                                ]
                            ]
                        }
                    }
                )
                if res.status_code >= 400:
                    print(f"[Triage] Failed to send Telegram alert: {res.text}")
        else:
            print("[Triage] Telegram credentials missing. Could not send alert.")
        
        return Response(status_code=200, content=f"Triage complete. {errors_found} errors reported.")
    except Exception as e:
        print(f"[Webhook] Triage error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/webhook/telegram")
async def telegram_webhook(request: Request):
    """ChatOps Webhook: Listens for button clicks from the Telegram Bot"""
    try:
        data = await request.json()
        
        if "callback_query" in data:
            callback = data["callback_query"]
            callback_id = callback["id"]
            action = callback.get("data")
            message = callback.get("message")
            chat_id = message["chat"]["id"]
            
            bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
            if not bot_token:
                return Response(status_code=200)

            async with httpx.AsyncClient() as client:
                # Answer callback to stop loading spinner on button
                await client.post(
                    f"https://api.telegram.org/bot{bot_token}/answerCallbackQuery", 
                    json={"callback_query_id": callback_id}
                )
                
                from services.cache import upstash_keys, upstash_del
                error_keys = await upstash_keys("ingest_error:*")
                
                if action == "clear_all_errors":
                    for key in error_keys:
                        await upstash_del(key)
                    await client.post(
                        f"https://api.telegram.org/bot{bot_token}/sendMessage",
                        json={"chat_id": chat_id, "text": f"🗑️ ✅ Cleared {len(error_keys)} error keys from Redis."}
                    )
                
                elif action == "retry_all_errors":
                    from services.queue import enqueue_sync
                    # Extract unique anilist ids from keys (e.g. ingest_error:<anilist_id>:<ep>)
                    anilist_ids = set()
                    for key in error_keys:
                        parts = key.split(":")
                        if len(parts) >= 3:
                            anilist_ids.add(parts[1])
                            
                        # Delete the error key so we don't trip triage again
                        await upstash_del(key)
                    
                    if anilist_ids:
                        for aid in anilist_ids:
                            # Re-syncing the anime will automatically find missing episodes and queue them
                            await enqueue_sync(int(aid))
                        
                        await client.post(
                            f"https://api.telegram.org/bot{bot_token}/sendMessage",
                            json={"chat_id": chat_id, "text": f"🔄 ✅ Queued Full Sync for {len(anilist_ids)} Anime.\nSelf-healing initiated. Errors cleared."}
                        )
                    else:
                        await client.post(
                            f"https://api.telegram.org/bot{bot_token}/sendMessage",
                            json={"chat_id": chat_id, "text": "⚠️ No specific Anilist IDs found in error logs to retry."}
                        )
                    
        return Response(status_code=200)
    except Exception as e:
        print(f"[Telegram Webhook] Error: {e}")
        return Response(status_code=200) # Always return 200 to prevent retries

# --- 🚀 ENTERPRISE WORKFLOW INGESTION ---

@serve.post("/webhook/ingest-workflow")
async def ingestion_workflow(context: AsyncWorkflowContext):
    payload = context.request_payload
    anime_slug = payload.get("anime_slug")
    episode = payload.get("episode")
    
    # Step 1: Resolve provider link
    source_url = await context.run(
        "resolve-provider",
        lambda: httpx.get(f"https://jonyyyyyyyu-anime-scraper-api.hf.space/api/v1/resolve/{anime_slug}/{episode}").json()
    )

    # Step 2: Trigger FFmpeg processing
    ingest_task = await context.run(
        "trigger-processing",
        lambda: httpx.post(
            "https://jonyyyyyyyu-anime-scraper-api.hf.space/api/v1/ingest",
            json={"url": source_url["direct_link"], "slug": anime_slug, "ep": episode}
        ).json()
    )

    # Step 3: Finalize DB sync
    await context.run(
        "finalize-db",
        lambda: httpx.post(
            "https://jonyyyyyyyu-anime-scraper-api.hf.space/api/v1/db/sync-episode",
            json={"slug": anime_slug, "episode": episode, "tg_urls": ingest_task["segments"]}
        ).json()
    )

    return {"status": "success", "slug": anime_slug, "ep": episode}
