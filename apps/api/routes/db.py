import json
import os
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from typing import List, Optional
from db.connection import database
from sqlalchemy import text
from schemas.sync import SyncEpisodePayload

router = APIRouter()

@router.post("/sync-episode")
async def sync_episode_db(payload: SyncEpisodePayload):
    """
    Endpoint untuk menerima link Telegram (tg_urls) dari Ingestion Workflow
    dan memperbarui tabel 'episodes' di database Neon.
    """
    if not payload.tg_urls:
        return {"status": "ignored", "message": "Tidak ada URL Telegram yang diberikan"}

    print(f"[DB Sync] Menerima update untuk {payload.slug} Ep {payload.episode}")
    
    try:
        # 1. Cari anilistId dari anime_mappings berdasarkan slug
        mapping_query = text("""
            SELECT "anilistId" FROM anime_mappings 
            WHERE "anime_slug" = :slug OR "providerSlug" = :slug 
            LIMIT 1
        """)
        mapping = await database.fetch_one(mapping_query, {"slug": payload.slug})
        
        # Fallback jika slug berupa angka (anilistId langsung)
        anilist_id = None
        if mapping:
            anilist_id = mapping["anilistId"]
        elif payload.slug.isdigit():
            anilist_id = int(payload.slug)
            
        if not anilist_id:
            raise HTTPException(status_code=404, detail=f"Anime dengan slug {payload.slug} tidak ditemukan di mapping.")

        # 2. Update kolom episodeUrl dengan master playlist (cloud_index.m3u8) atau URL pertama
        # Di sini kita asumsikan tg_urls adalah string URL tunggal (playlist) atau list URL.
        # Jika IngestionEngine menghasilkan cloud_index.m3u8, biasanya kita hanya menyimpan 1 URL M3U8 utama.
        
        # Format URL Telegram Proxy
        final_url = payload.tg_urls[0] if isinstance(payload.tg_urls, list) else str(payload.tg_urls)
        
        update_query = text("""
            UPDATE episodes 
            SET "episodeUrl" = :url, "updatedAt" = NOW()
            WHERE "anilistId" = :anilist_id AND "episodeNumber" = :episode
            RETURNING id
        """)
        
        result = await database.execute(update_query, {
            "url": final_url,
            "anilist_id": anilist_id,
            "episode": payload.episode
        })
        
        if result:
            print(f"✅ [DB Sync] Sukses update Neon DB: {payload.slug} Ep {payload.episode} -> {final_url[:30]}...")
            return {"status": "success", "url": final_url}
        else:
            print(f"⚠️ [DB Sync] Episode tidak ditemukan di DB. Gagal update.")
            raise HTTPException(status_code=404, detail="Episode tidak ditemukan di database.")
            
    except Exception as e:
        print(f"🚨 [DB Sync] Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
