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

async def process_batch(anilist_id: int, url: str):
    print(f"\n🚀 Memulai Auto Batch Ingestion untuk Anilist ID: {anilist_id}")
    
    # 1. Resolve URL if it's Desustream
    if "desustream" in url:
        url = await resolve_desustream(url)
        if not url:
            print("❌ Gagal meresolve Desustream URL.")
            return
            
    # 2. Download File
    os.makedirs("tmp_ingest/batch", exist_ok=True)
    file_ext = ".rar" if "rar" in url.lower() or "zip" not in url.lower() else ".zip"
    archive_path = f"tmp_ingest/batch/downloaded_batch_{anilist_id}{file_ext}"
    
    if not os.path.exists(archive_path):
        if "drive.google" in url or "drive.usercontent" in url:
            await download_gdrive(url, archive_path)
        else:
            print("❌ URL bukan dari Google Drive/Desustream yang didukung.")
            return

    if not os.path.exists(archive_path) or os.path.getsize(archive_path) == 0:
        print("❌ File gagal diunduh atau kosong.")
        return

    # 3. Ekstrak Arsip
    extract_dir = f"tmp_ingest/batch/extracted_{anilist_id}"
    os.makedirs(extract_dir, exist_ok=True)
    
    print(f"\n📦 Mengekstrak file arsip ke {extract_dir}...")
    try:
        # patoolib berjalan secara synchronous, kita masukkan ke thread
        await asyncio.to_thread(patoolib.extract_archive, archive_path, outdir=extract_dir)
    except Exception as e:
        print(f"❌ Gagal mengekstrak: {e}")
        return

    # 4. Cari file .mp4 dan Upload ke Telegram
    uploader = TelegramUploader()
    await database.connect()
    
    mp4_files = list(Path(extract_dir).rglob("*.mp4"))
    mp4_files.extend(list(Path(extract_dir).rglob("*.mkv"))) # Support mkv as well
    print(f"\n🎥 Ditemukan {len(mp4_files)} file video untuk di-ingest.")
    
    # Sort files alphanumerically
    mp4_files.sort(key=lambda x: x.name)
    
    for file_path in mp4_files:
        # Ekstrak nomor episode dari nama file (misal: "Death Note - 01.mp4" -> 1.0)
        # Regex mencari angka terakhir sebelum ekstensi
        match = re.search(r'(\d+(?:\.\d+)?)(?:v\d+)?\.(?:mp4|mkv)$', file_path.name, re.IGNORECASE)
        if not match:
            # Fallback cari angka apa saja
            match = re.search(r'(\d+)', file_path.name)
            
        ep_num = float(match.group(1)) if match else 0.0
        
        print(f"\n⏳ Mengunggah Episode {ep_num} ({file_path.name})...")
        result = await uploader.upload_file(str(file_path))
        
        if result and result.get("url"):
            tg_url = result["url"]
            print(f"✅ Berhasil diunggah: {tg_url}")
            
            # 5. Simpan ke Database
            try:
                # Cek apakah sudah ada
                existing = await database.fetch_one(
                    'SELECT id FROM episodes WHERE "anilistId" = :aid AND "episodeNumber" = :ep AND "providerId" = :pid',
                    values={"aid": anilist_id, "ep": ep_num, "pid": "telegram_swarm"}
                )
                
                if existing:
                    await database.execute(
                        'UPDATE episodes SET "episodeUrl" = :url, "updatedAt" = NOW() WHERE id = :id',
                        values={"url": tg_url, "id": existing["id"]}
                    )
                    print(f"💾 Diperbarui di DB: Episode {ep_num}")
                else:
                    await database.execute(
                        '''INSERT INTO episodes ("anilistId", "providerId", "episodeNumber", "episodeUrl", "createdAt", "updatedAt") 
                           VALUES (:aid, :pid, :ep, :url, NOW(), NOW())''',
                        values={"aid": anilist_id, "pid": "telegram_swarm", "ep": ep_num, "url": tg_url}
                    )
                    print(f"💾 Disimpan ke DB: Episode {ep_num}")
            except Exception as e:
                print(f"❌ Gagal menyimpan ke DB: {e}")
        else:
            print(f"❌ Gagal mengunggah {file_path.name}")
            
    await database.disconnect()
    
    # 6. Bersihkan file temp
    print("\n🧹 Membersihkan file temporary...")
    try:
        shutil.rmtree(extract_dir)
        os.remove(archive_path)
    except:
        pass
        
    print(f"\n🎉 Batch Ingestion untuk Anilist ID {anilist_id} Selesai!")

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Penggunaan: python scripts/batch_gdrive_ingest.py <Anilist_ID> <Google_Drive/Desustream_URL>")
        sys.exit(1)
        
    aid = int(sys.argv[1])
    url = sys.argv[2]
    asyncio.run(process_batch(aid, url))
