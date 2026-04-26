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
from db.models import users, payment_logs
from datetime import datetime, timedelta
import sqlalchemy
import re

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
    finally:
        try:
            from services.cache import client as redis_client
            from services.config import UPSTASH_REDIS_REST_URL, UPSTASH_REDIS_REST_TOKEN
            await redis_client.get(f"{UPSTASH_REDIS_REST_URL}/del/global_ingest_lock", headers={"Authorization": f"Bearer {UPSTASH_REDIS_REST_TOKEN}"})
            print("[Webhook] Global ingestion lock released.")
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
        
        # --- GLOBAL LOCK CHECK ---
        try:
            from services.cache import client as redis_client
            from services.config import UPSTASH_REDIS_REST_URL, UPSTASH_REDIS_REST_TOKEN
            lock_url = f"{UPSTASH_REDIS_REST_URL}/set/global_ingest_lock/1?NX=true&EX=3600"
            res = await redis_client.get(lock_url, headers={"Authorization": f"Bearer {UPSTASH_REDIS_REST_TOKEN}"})
            if res.status_code == 200:
                if res.json().get("result") != "OK":
                    print(f"[Webhook] Concurrent ingestion blocked for Anime: {anilist_id} Ep: {episode_number}. Returning 429.")
                    raise HTTPException(status_code=429, detail="Another ingestion is in progress. QStash will retry later.")
        except HTTPException:
            raise
        except Exception as e:
            print(f"[Webhook] Failed to check global lock: {e}")
            
        print(f"[Webhook] Executing Ingestion for anilistId={anilist_id} Ep={episode_number}")
        
        # Jalankan di latar belakang agar QStash tidak timeout
        asyncio.create_task(_run_ingestion_bg(episode_id, anilist_id, provider_id, episode_number, direct_url))
        
        return Response(status_code=200, content="Ingestion Queued")
    except HTTPException:
        raise
    except Exception as e:
        print(f"[Webhook] Error processing ingestion payload: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/webhook/ingest-batch")
async def ingest_batch_webhook(request: Request):
    await _verify_qstash(request)
    try:
        print("[Webhook] Executing Batch Ingestion Trigger")
        from services.queue import QStashPublisher
        QStashPublisher.spawn_batch_worker()
        return Response(status_code=200, content="Batch Ingestion Scheduled")
    except Exception as e:
        print(f"[Webhook] Error processing batch ingestion: {e}")
        raise HTTPException(status_code=500, detail=str(e))

from fastapi import BackgroundTasks

@router.post("/admin/ingest-batch")
async def admin_ingest_batch(request: Request, background_tasks: BackgroundTasks):
    """Trigger auto batch ingestion on Hugging Face Spaces."""
    try:
        payload = await request.json()
        anilist_id = payload.get("anilist_id")
        url = payload.get("url")
        admin_key = request.headers.get("x-admin-key")
        
        if admin_key != os.environ.get("ADMIN_API_KEY"):
            raise HTTPException(status_code=403, detail="Unauthorized")
            
        if not anilist_id or not url:
            raise HTTPException(status_code=400, detail="Missing anilist_id or url")
            
        from scripts.batch_gdrive_ingest import process_batch
        background_tasks.add_task(process_batch, int(anilist_id), url)
        
        return Response(status_code=200, content=json.dumps({"message": f"Batch ingestion started for {anilist_id}"}))
    except Exception as e:
        print(f"[Admin] Error starting batch ingestion: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/admin/trigger-auto-ingest")
async def admin_trigger_auto_ingest(request: Request, shard_id: int = 0, total_shards: int = 1):
    """Trigger the sequential hard-stitch auto-ingestion natively with sharding support."""
    admin_key = request.headers.get("x-admin-key") or request.query_params.get("key")
    if admin_key != os.environ.get("ADMIN_API_KEY"):
        raise HTTPException(status_code=403, detail="Unauthorized")
    try:
        from services.queue import QStashPublisher
        QStashPublisher.spawn_batch_worker(shard_id, total_shards)
        return Response(status_code=200, content=f"Auto ingestion worker spawned successfully! Shard {shard_id}/{total_shards}")
    except Exception as e:
        print(f"[Admin] Error triggering auto ingest: {e}")
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

# --- 💰 BILLING WEBHOOK (Trakteer/Saweria) ---

@router.post("/webhook/billing")
async def billing_webhook(request: Request):
    """
    Handle incoming payments from Trakteer or Saweria.
    Users should include "Username: your_name" in their message.
    """
    try:
        data = await request.json()
        print(f"[Billing] Incoming Webhook: {json.dumps(data)}")

        provider = "unknown"
        amount = 0
        message = ""
        external_id = None
        
        # 1. Parse Trakteer
        if "supporter_message" in data:
            provider = "trakteer"
            amount = data.get("price", 0)
            message = data.get("supporter_message", "")
            external_id = data.get("tr_id")
        
        # 2. Parse Saweria
        elif "message" in data and "amount_raw" in data:
            provider = "saweria"
            amount = data.get("amount_raw", 0)
            message = data.get("message", "")
            external_id = data.get("id")

        if not external_id:
            return Response(status_code=200, content="No transaction ID found")

        # 3. Find User ID in message using Regex (Flexible: "User: name" or "Username: name")
        user_id_match = re.search(r"(?:user|username|id):\s*([a-zA-Z0-9_\-]+)", message, re.IGNORECASE)
        found_user_id = user_id_match.group(1) if user_id_match else None

        # 4. Persistence & Logic
        async with database.transaction():
            # Check if already processed
            query_check = sqlalchemy.select(payment_logs).where(payment_logs.c.external_id == str(external_id))
            existing = await database.fetch_one(query_check)
            if existing:
                return Response(status_code=200, content="Already processed")

            # Update User if found
            if found_user_id:
                # Calculate duration: Rp 15.000 = 30 days
                # You can adjust this pricing as needed
                days_to_add = int(amount / 500) 
                
                # Get current expiry or start from now
                query_user = sqlalchemy.select(users).where(users.c.id == found_user_id)
                user_data = await database.fetch_one(query_user)
                
                if user_data:
                    current_expiry = user_data.subscription_expiry
                    # current_expiry is a naive datetime or None from database
                    now = datetime.now()
                    start_date = current_expiry if (current_expiry and current_expiry > now) else now
                    new_expiry = start_date + timedelta(days=days_to_add)

                    update_query = sqlalchemy.update(users).where(users.c.id == found_user_id).values(
                        tier="PRO",
                        subscription_expiry=new_expiry
                    )
                    await database.execute(update_query)
                    print(f"[Billing] User {found_user_id} upgraded to PRO until {new_expiry}")
                else:
                    print(f"[Billing] User {found_user_id} not found in DB")
                    found_user_id = None # Reset so log knows it wasn't applied

            # Log payment
            insert_log = payment_logs.insert().values(
                provider=provider,
                external_id=str(external_id),
                amount=float(amount),
                message=message,
                user_id=found_user_id,
                status="processed" if found_user_id else "user_not_found",
                raw_payload=data
            )
            await database.execute(insert_log)

        # 5. Telegram Notification
        bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
        chat_id = os.getenv("TELEGRAM_CHAT_ID")
        if bot_token and chat_id:
            status_emoji = "✅" if found_user_id else "⚠️"
            tg_msg = (
                f"💰 *New Payment Received!* {status_emoji}\n\n"
                f"Provider: `{provider.upper()}`\n"
                f"Amount: `Rp {amount:,.0f}`\n"
                f"Message: `{message}`\n"
                f"User: `{found_user_id or 'NOT FOUND'}`\n"
                f"Status: `{'PRO Activated' if found_user_id else 'Manual Check Needed'}`"
            )
            async with httpx.AsyncClient() as client:
                await client.post(
                    f"https://api.telegram.org/bot{bot_token}/sendMessage",
                    json={"chat_id": chat_id, "text": tg_msg, "parse_mode": "Markdown"}
                )

        return Response(status_code=200, content="Payment Processed")
    except Exception as e:
        print(f"[Billing] Error: {e}")
        traceback.print_exc()
        return Response(status_code=200) # Always return 200 to prevent webhook retries

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
