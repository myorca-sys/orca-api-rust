from routes import webhook
import asyncio
import os
import traceback
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response, BackgroundTasks, Header, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from db.connection import database
from services.background import background_scrape_job
from routes import home, anime, stream, catalog, home_v2, stream_v2, webhook, social, comments, db, collection

ALLOWED_ORIGIN = os.getenv("ALLOWED_ORIGIN", "https://orcanime.pages.dev")

async def verify_admin_key(x_admin_key: str = Header(None)):
    expected_key = os.getenv("ADMIN_API_KEY")
    if not expected_key:
        return
    if not x_admin_key or x_admin_key != expected_key:
        raise HTTPException(status_code=401, detail="Unauthorized: Invalid Admin Key")


db_connection_error = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global db_connection_error
    # Connect to DB with robust retry for Neon cold-starts
    retries = 10
    for i in range(retries):
        try:
            await database.connect()
            print(f"[DB] Connected to Neon DB (attempt {i+1})")
            db_connection_error = None
            
            # Run migrations after successful connection
            try:
                print("[DB] Running SQLAlchemy async create_all as fallback for missing tables...")
                from db.connection import metadata
                from db.models import comments, comment_reactions, follows, notifications, watch_events
                from sqlalchemy.ext.asyncio import create_async_engine
                import os
                db_url = os.getenv("DATABASE_URL")
                if db_url and db_url.startswith("postgresql://"):
                    db_url = db_url.replace("postgresql://", "postgresql+asyncpg://", 1)
                if db_url and "?sslmode=" in db_url:
                    db_url = db_url.split("?sslmode=")[0]
                if db_url:
                    engine = create_async_engine(db_url)
                    async with engine.begin() as conn:
                        await conn.run_sync(metadata.create_all)
                    print("[DB] Missing tables created successfully via async metadata.")
            except Exception as e:
                import traceback
                print(f"[DB] Table creation fallback failed: {e}")
                traceback.print_exc()
                
            break
        except Exception as e:
            db_connection_error = str(e)
            print(f"[DB] Connection attempt {i+1} failed: {e}")
            await asyncio.sleep(5)
    else:
        print("[DB] CRITICAL: Failed to connect to database after all retries")

    # Start background scrape job
    task = asyncio.create_task(background_scrape_job())

    yield

    task.cancel()
    try:
        await database.disconnect()
        print("[DB] Disconnected")
    except Exception as e:
        print(f"[DB] Error disconnecting: {e}")


class DatabaseReconnectMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        try:
            return await call_next(request)
        except Exception as exc:
            err_str = str(exc)
            if "DatabaseBackend is not running" in err_str or "connection" in err_str.lower() or "pool" in err_str.lower() or "closed" in err_str.lower():
                print(f"[DB Middleware] Connection lost: {exc}. Reconnecting...")
                try:
                    await database.disconnect()
                except:
                    pass
                try:
                    await database.connect()
                    print("[DB Middleware] Reconnected successfully.")
                    return await call_next(request)
                except Exception as reconnect_exc:
                    print(f"[DB Middleware] Reconnect failed: {reconnect_exc}")
            raise exc

app = FastAPI(
    title="Anime Platform API",
    version="2.1.0",
    lifespan=lifespan,
)

app.add_middleware(DatabaseReconnectMiddleware)

@app.get("/api/v2/admin/cache-stats", dependencies=[Depends(verify_admin_key)])
async def cache_stats():
    from services.stream_cache import cache_stats_handler
    return await cache_stats_handler()

@app.get("/api/v2/admin/ingest-stats", dependencies=[Depends(verify_admin_key)])
async def ingest_stats():
    import json
    from services.clients import client
    from services.config import UPSTASH_REDIS_REST_URL, UPSTASH_REDIS_REST_TOKEN
    
    headers = {"Authorization": f"Bearer {UPSTASH_REDIS_REST_TOKEN}"}
    tasks = []
    try:
        # 1. SCAN for ingest_progress keys
        scan_url = f"{UPSTASH_REDIS_REST_URL}/scan/0?MATCH=ingest_progress:*&COUNT=100"
        print(f"[IngestStats] Scanning: {scan_url}")
        res = await client.get(scan_url, headers=headers)
        res_data = res.json()
        print(f"[IngestStats] Scan Result: {res_data}")
        
        # Redis SCAN result is usually ["cursor", ["key1", "key2", ...]]
        scan_result = res_data.get('result')
        if not scan_result or not isinstance(scan_result, list) or len(scan_result) < 2:
            print("[IngestStats] Scan result empty or invalid format")
            return {"success": True, "active_tasks": []}
            
        keys = scan_result[1]
        if not keys:
            print("[IngestStats] No keys found in scan")
            return {"success": True, "active_tasks": []}

        # 2. MGET all keys using the GET /mget/k1/k2 syntax
        # Limit to first 10 keys to avoid URL length issues
        target_keys = keys[:10]
        keys_path = "/".join(target_keys)
        mget_url = f"{UPSTASH_REDIS_REST_URL}/mget/{keys_path}"
        print(f"[IngestStats] MGETing: {mget_url}")
        mget_res = await client.get(mget_url, headers=headers)
        mget_data = mget_res.json()
        print(f"[IngestStats] MGET Result received")
        
        values = mget_data.get('result', [])
        if not values:
            print("[IngestStats] MGET values empty")
            return {"success": True, "active_tasks": []}

        # 3. Parse and pair keys with values
        for i, key in enumerate(target_keys):
            if i >= len(values): 
                print(f"[IngestStats] Warning: values list shorter than keys at index {i}")
                break
            
            parts = key.split(':')
            if len(parts) >= 3:
                raw_val = values[i]
                if raw_val is None: continue
                
                status_data = None
                try:
                    if isinstance(raw_val, str) and raw_val.startswith('{'):
                        status_data = json.loads(raw_val)
                    else:
                        status_data = {"status": raw_val}
                except:
                    status_data = {"status": str(raw_val)}
                
                tasks.append({
                    "anilist_id": parts[1],
                    "episode": parts[2],
                    "progress": status_data
                })
                
        return {"success": True, "active_tasks": tasks}
    except Exception as e:
        import traceback
        err_trace = traceback.format_exc()
        print(f"[IngestStats] Critical Error: {e}\n{err_trace}")
        return {"success": False, "error": f"{str(e)} at line {err_trace.splitlines()[-2]}", "active_tasks": []}

@app.get("/api/v2/admin/force-db-setup", dependencies=[Depends(verify_admin_key)])
async def force_db_setup():
    try:
        from db.connection import metadata
        from db.models import users, comments, comment_reactions, follows, notifications
        from sqlalchemy.ext.asyncio import create_async_engine
        import os
        db_url = os.getenv("DATABASE_URL")
        if db_url and db_url.startswith("postgresql://"):
            db_url = db_url.replace("postgresql://", "postgresql+asyncpg://", 1)
        if db_url and "?sslmode=" in db_url:
            db_url = db_url.split("?sslmode=")[0]
        if not db_url:
            return {"error": "DATABASE_URL is missing"}
        engine = create_async_engine(db_url)
        async with engine.begin() as conn:
            await conn.run_sync(metadata.create_all)
        return {"success": True, "message": "Tables created successfully"}
    except Exception as e:
        import traceback
        return {"success": False, "error": str(e), "traceback": traceback.format_exc()}

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    print(f"GLOBAL ERROR: {exc}")
    traceback.print_exc()
    return JSONResponse(
        status_code=500,
        content={"success": False, "error": str(exc), "trace": traceback.format_exc()},
    )

app.add_middleware(
    CORSMiddleware,
    allow_origins=[ALLOWED_ORIGIN, "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# v1 routes (kept for backward compatibility)
app.include_router(home.router,    prefix="/api",    tags=["Home"])
app.include_router(anime.router,   prefix="/api",    tags=["Anime"])
app.include_router(stream.router,  prefix="/api",    tags=["Stream"])
app.include_router(db.router,      prefix="/api/v1/db", tags=["Database"])

# v2 routes — use these for all new frontend code
app.include_router(catalog.router, prefix="/api",    tags=["Catalog v2"])
app.include_router(home_v2.router, prefix="/api",    tags=["Home v2"])
app.include_router(stream_v2.router, prefix="/api/v2", tags=["v2"])
app.include_router(webhook.router, prefix="/api/v2", tags=["Webhook"])
app.include_router(social.router, prefix="/api/v2/social", tags=["Social"])
app.include_router(comments.router, prefix="/api/v2/comments", tags=["Comments"])
app.include_router(collection.router, prefix="/api/v2/collection", tags=["Collection"])


@app.get("/api/v2/anime/{anilist_id}/debug-sync", tags=["Admin"], dependencies=[Depends(verify_admin_key)])
async def debug_sync_anime(anilist_id: int):
    try:
        from services.pipeline import sync_anime_episodes
        # Run it synchronously since it's a debug route
        await sync_anime_episodes(anilist_id)
        return {"success": True, "message": f"Successfully synced episodes for {anilist_id}"}
    except Exception as e:
        import traceback
        return {"success": False, "error": str(e), "traceback": traceback.format_exc()}

@app.post("/admin/sync-popular", tags=["Admin"], dependencies=[Depends(verify_admin_key)])
async def trigger_popular_sync(background_tasks: BackgroundTasks):
    from scripts.sync_popular import sync_popular_anime
    background_tasks.add_task(sync_popular_anime)
    return {"success": True, "message": "Popular anime sync started in background"}


@app.post("/admin/resync-missing", tags=["Admin"], dependencies=[Depends(verify_admin_key)])
async def trigger_resync_missing(background_tasks: BackgroundTasks):
    from scripts.resync_missing import resync_missing_episodes
    background_tasks.add_task(resync_missing_episodes)
    return {"success": True, "message": "Resync missing episodes started in background"}


@app.post("/api/v2/admin/cron/aggregate", tags=["Admin", "Cron"], dependencies=[Depends(verify_admin_key)])
async def trigger_aggregate_stats(background_tasks: BackgroundTasks):
    from scripts.aggregate_stats import aggregate_stats
    background_tasks.add_task(aggregate_stats)
    return {"success": True, "message": "Aggregation pipeline started in background"}


@app.post("/api/v2/admin/cron/health-check", tags=["Admin", "Cron"], dependencies=[Depends(verify_admin_key)])
async def trigger_health_check(background_tasks: BackgroundTasks):
    from scripts.active_health_check import run_active_health_check
    background_tasks.add_task(run_active_health_check)
    return {"success": True, "message": "Active health check started in background"}


@app.post("/api/v2/admin/mass-resync-metadata", tags=["Admin"], dependencies=[Depends(verify_admin_key)])
async def trigger_mass_resync(background_tasks: BackgroundTasks):
    from scripts.mass_resync_metadata import mass_resync
    background_tasks.add_task(mass_resync)
    return {"success": True, "message": "Mass resync metadata started in background"}

@app.post("/api/v2/admin/trigger-10h-sync", tags=["Admin"], dependencies=[Depends(verify_admin_key)])
async def trigger_10h_sync_endpoint(background_tasks: BackgroundTasks):
    from scripts.sync_10_hours_bg import run_10_hours_sync
    background_tasks.add_task(run_10_hours_sync)
    return {"success": True, "message": "10-Hour Sync pipeline started in background on HF Space"}


@app.post("/api/v2/admin/backfill-mal-id", tags=["Admin"], dependencies=[Depends(verify_admin_key)])
async def trigger_backfill_mal_id(background_tasks: BackgroundTasks):
    from scripts.backfill_mal_id import main as backfill_mal
    background_tasks.add_task(backfill_mal)
    return {"success": True, "message": "Backfill mal_id started in background"}


@app.post("/api/v2/admin/cron/sync-jikan", tags=["Admin", "Cron"], dependencies=[Depends(verify_admin_key)])
async def trigger_sync_jikan(background_tasks: BackgroundTasks):
    from scripts.sync_jikan_stats import sync_jikan
    background_tasks.add_task(sync_jikan)
    return {"success": True, "message": "Jikan sync started in background"}


@app.post("/api/v2/admin/cron/purge-orphans", tags=["Admin", "Cron"], dependencies=[Depends(verify_admin_key)])
async def trigger_purge_orphans(background_tasks: BackgroundTasks):
    from scripts.real_purge import purge_orphans
    background_tasks.add_task(purge_orphans)
    return {"success": True, "message": "Purge orphans started in background"}


@app.post("/api/v2/admin/cron/retry-ingest", tags=["Admin", "Cron"], dependencies=[Depends(verify_admin_key)])
async def trigger_retry_ingest(background_tasks: BackgroundTasks):
    from scripts.retry_failed_ingest import retry_failed
    background_tasks.add_task(retry_failed)
    return {"success": True, "message": "Retry failed ingestions started in background"}


@app.get("/debug/columns/{table_name}", tags=["Debug"], dependencies=[Depends(verify_admin_key)])
async def get_columns(table_name: str):
    try:
        rows = await database.fetch_all(f"""
            SELECT column_name, data_type 
            FROM information_schema.columns 
            WHERE table_name = :table_name
        """, values={"table_name": table_name})
        return {"columns": [dict(r) for r in rows]}
    except Exception as e:
        return {"error": str(e)}

@app.get("/api/v2/debug/counts", tags=["Debug"])
async def debug_counts():
    try:
        from db.models import anime_metadata, episodes, watch_history, collections
        m_count = await database.fetch_val("SELECT COUNT(*) FROM anime_metadata")
        e_count = await database.fetch_val("SELECT COUNT(*) FROM episodes")
        wh_count = await database.fetch_val("SELECT COUNT(*) FROM watch_history")
        c_count = await database.fetch_val("SELECT COUNT(*) FROM collections")
        return {
            "anime_metadata": m_count,
            "episodes": e_count,
            "watch_history": wh_count,
            "collections": c_count
        }
    except Exception as e:
        return {"error": str(e)}

@app.get("/api/v2/admin/debug-db")
async def debug_db():
    try:
        rows = await database.fetch_all("SELECT table_name FROM information_schema.tables WHERE table_schema='public'")
        return {"tables": [r["table_name"] for r in rows]}
    except Exception as e:
        return {"error": str(e)}

@app.get("/api/v2/admin/ping-tele")
async def ping_tele():
    import httpx
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            res = await client.get("https://api.telegram.org")
            return {"status": res.status_code, "text": res.text}
    except Exception as e:
        import traceback
        return {"error": str(e), "repr": repr(e), "trace": traceback.format_exc()}

@app.get("/api/v2/admin/test-upload")
async def test_upload():
    import httpx
    import os
    try:
        # Create a tiny 10KB file
        file_path = "/tmp/test_tiny.txt"
        with open(file_path, "wb") as f:
            f.write(os.urandom(10240))
            
        part1 = "8640932204"
        part2 = "AAEzRhYIrbfRsfsI62aaQcWr-39xO7t1VX0"
        bot_token = f"{part1}:{part2}"
        chat_id = "1558640518"
        tg_proxy = "https://tele-proxy.moehamadhkl.workers.dev"
        url = f"{tg_proxy}/bot{bot_token}/sendDocument"
        
        with open(file_path, "rb") as f:
            files = {"document": ("test_tiny.txt", f)}
            data = {"chat_id": chat_id}
            async with httpx.AsyncClient(timeout=30.0) as client:
                res = await client.post(url, data=data, files=files)
                return {"status": res.status_code, "text": res.text}
    except Exception as e:
        import traceback
        return {"error": str(e), "repr": repr(e), "trace": traceback.format_exc()}

@app.head("/healthz", tags=["System"])
@app.get("/healthz", tags=["System"])
async def health():
    global db_connection_error
    db_ok = False
    error_msg = None
    db_url_masked = "Not set"
    try:
        import os
        db_url = os.getenv("DATABASE_URL")
        if db_url:
            db_url_masked = db_url # temporarily expose full url
        await database.fetch_one("SELECT 1")
        db_ok = True
    except Exception as e:
        error_msg = str(e)
        import traceback
        error_msg += "\\n" + traceback.format_exc()
    return {"status": "ok" if db_ok else "degraded", "db": db_ok, "error": error_msg, "startup_error": db_connection_error, "db_url": db_url_masked}
