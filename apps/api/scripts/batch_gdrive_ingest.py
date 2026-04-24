import asyncio
import os
import sys
import re
import shutil
import patoolib
from pathlib import Path

sys.path.append('.')
from db.connection import database
from db.models import episodes
from services.ingestion.uploader.telegram import TelegramUploader
from scripts.resolve_desustream import resolve_desustream
from scripts.gdrive_downloader import download_gdrive
from services.cache import upstash_set

async def log_status(anilist_id, message):
    print(message)
    await upstash_set(f"batch_status:{anilist_id}", message)

async def process_batch(anilist_id: int, url: str):
    await log_status(anilist_id, f"🚀 Memulai Auto Batch Ingestion untuk Anilist ID: {anilist_id}")
    
    # 1. Resolve URL if it's Desustream
    if "desustream" in url:
        await log_status(anilist_id, "Resolving desustream url...")
        url = await resolve_desustream(url)
        await log_status(anilist_id, f"Resolved url: {url}")
        if not url:
            await log_status(anilist_id, "❌ Gagal meresolve Desustream URL.")
            return
            
    # 2. Download File
    os.makedirs("tmp_ingest/batch", exist_ok=True)
    file_ext = ".rar" if "rar" in url.lower() or "zip" not in url.lower() else ".zip"
    archive_path = f"tmp_ingest/batch/downloaded_batch_{anilist_id}{file_ext}"
    
    if not os.path.exists(archive_path):
        if "drive.google" in url or "drive.usercontent" in url:
            await log_status(anilist_id, f"Downloading from gdrive to {archive_path}...")
            try:
                await download_gdrive(url, archive_path)
            except Exception as e:
                await log_status(anilist_id, f"❌ Download error: {e}")
                return
        else:
            await log_status(anilist_id, "❌ URL bukan dari Google Drive/Desustream yang didukung.")
            return

    if not os.path.exists(archive_path) or os.path.getsize(archive_path) == 0:
        await log_status(anilist_id, "❌ File gagal diunduh atau kosong.")
        return

    # 3. Ekstrak Arsip
    extract_dir = f"tmp_ingest/batch/extracted_{anilist_id}"
    os.makedirs(extract_dir, exist_ok=True)
    
    await log_status(anilist_id, f"📦 Mengekstrak file arsip ke {extract_dir}...")
    try:
        import subprocess
        if file_ext == ".rar":
            # Extract RAR using official unrar binary
            cmd = f"/usr/local/bin/unrar x -y '{archive_path}' '{extract_dir}/'"
            process = await asyncio.create_subprocess_shell(
                cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await process.communicate()
            if process.returncode != 0:
                await log_status(anilist_id, f"❌ Gagal mengekstrak RAR dengan unrar: {stderr.decode()} | {stdout.decode()}")
                return
        else:
            # zip fallback
            await asyncio.to_thread(patoolib.extract_archive, archive_path, outdir=extract_dir)
    except Exception as e:
        await log_status(anilist_id, f"❌ Gagal mengekstrak: {e}")
        return

    # 4. Cari file .mp4 dan Upload ke Telegram
    from services.ingestion.core.slicer import VideoSlicer
    from services.cache import upstash_del

    uploader = TelegramUploader()
    slicer = VideoSlicer()
    await database.connect()
    
    mp4_files = list(Path(extract_dir).rglob("*.mp4"))
    mp4_files.extend(list(Path(extract_dir).rglob("*.mkv"))) # Support mkv as well
    await log_status(anilist_id, f"🎥 Ditemukan {len(mp4_files)} file video untuk di-ingest.")
    
    # Sort files alphanumerically
    mp4_files.sort(key=lambda x: x.name)
    
    for file_path in mp4_files:
        match = re.search(r'(\d+(?:\.\d+)?)(?:v\d+)?\.(?:mp4|mkv)$', file_path.name, re.IGNORECASE)
        if not match:
            match = re.search(r'(\d+)', file_path.name)
            
        ep_num = float(match.group(1)) if match else 0.0
        
        await log_status(anilist_id, f"✂️ Memotong video {file_path.name} menjadi HLS 5-detik...")
        m3u8_path = await slicer.slice(url=str(file_path), filename=file_path.name, provider_id="gdrive", segment_time=5)
        
        if not m3u8_path:
            await log_status(anilist_id, f"❌ Gagal memotong video {file_path.name}")
            continue
            
        await log_status(anilist_id, f"⏳ Mengunggah potongan HLS Episode {ep_num} ke Telegram Swarm...")
        progress_key = f"ingest_progress:{anilist_id}:{ep_num}"
        cloud_m3u8 = await uploader.process_hls_playlist_parallel(m3u8_path, progress_key=progress_key, max_workers=5)
        
        if not cloud_m3u8:
            await log_status(anilist_id, "❌ Gagal mengunggah playlist ke Telegram")
            continue
            
        f_res = await uploader.upload_file(cloud_m3u8)
        tg_url = f_res.get("url") if isinstance(f_res, dict) else None
        
        if tg_url:
            await log_status(anilist_id, f"✅ Berhasil diunggah: {tg_url}")
            await upstash_del(progress_key)
            
            try:
                existing = await database.fetch_one(
                    'SELECT id FROM episodes WHERE "anilistId" = :aid AND "episodeNumber" = :ep AND "providerId" = :pid',
                    values={"aid": anilist_id, "ep": ep_num, "pid": "telegram_swarm"}
                )
                
                if existing:
                    await database.execute(
                        'UPDATE episodes SET "episodeUrl" = :url, "updatedAt" = NOW() WHERE id = :id',
                        values={"url": tg_url, "id": existing["id"]}
                    )
                else:
                    await database.execute(
                        '''INSERT INTO episodes ("anilistId", "providerId", "episodeNumber", "episodeUrl", "createdAt", "updatedAt") 
                           VALUES (:aid, :pid, :ep, :url, NOW(), NOW())''',
                        values={"aid": anilist_id, "pid": "telegram_swarm", "ep": ep_num, "url": tg_url}
                    )
            except Exception as e:
                await log_status(anilist_id, f"❌ Gagal menyimpan ke DB: {e}")
        else:
            await log_status(anilist_id, f"❌ Gagal mengunggah master playlist {file_path.name}")
            
    await database.disconnect()
    
    await log_status(anilist_id, "🧹 Membersihkan file temporary...")
    try:
        shutil.rmtree(extract_dir)
        os.remove(archive_path)
    except:
        pass
        
    await log_status(anilist_id, f"🎉 Batch Ingestion Selesai!")

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Penggunaan: python scripts/batch_gdrive_ingest.py <Anilist_ID> <Google_Drive/Desustream_URL>")
        sys.exit(1)
        
    aid = int(sys.argv[1])
    url = sys.argv[2]
    asyncio.run(process_batch(aid, url))
