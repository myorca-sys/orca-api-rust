# 📡 Provider Health & Direct Stream Status
*Catatan Proaktif Agen 4 (Lead Assistant) untuk memantau efektivitas Ekstraktor HLS/MP4.*

## 1. Status Resolusi *Direct Stream* Saat Ini

| Provider | Ekstraksi Direct Stream | Keterangan / Tantangan |
| :--- | :--- | :--- |
| **Kuronime** | 🟢 Sangat Baik | Menggunakan `kuroplayer` yang mudah dibongkar *token*-nya oleh `UniversalExtractor` untuk mendapatkan `.m3u8` murni. |
| **Oploverz** | 🟢 Baik (Hybrid) | Link *streaming* utama sering diblokir CORS/IP, namun kita punya sistem **Pixeldrain Auto-Hunter** yang mengambil tautan *download* dan mengubahnya menjadi `type: direct`. |
| **Samehadaku** | 🟢 Baik | Sering kali mengekspos link `.mp4` atau host yang bersahabat untuk dibongkar oleh `SmartExtractor`. |
| **Otakudesu** | 🟡 Menengah | Menggunakan *DesuStream/DesuDrive* yang di-obfuscate dengan AJAX. Sering lolos menjadi `iframe` jika *extractor* gagal mengurai JSON/HTML-nya dalam waktu 7 detik. |
| **Doronime** | 🔴 Buruk | Sering mengandalkan *video hosting* lapis ketiga yang anti-scraping, sehingga sering berakhir sebagai `iframe` murni (tidak bisa di- *ingest* ke Telegram). |

## 2. Mengapa "Iframe" Menjadi Masalah?
Sistem Ingestion kita (`ffmpeg`) membutuhkan file video mentah (berakhiran `.m3u8` atau `.mp4`). Jika sebuah tautan berstatus `iframe` (misalnya `https://doodstream.com/e/abcde`), FFmpeg tidak bisa memotongnya.

## 3. Rencana Optimasi (*The Roadmap*)
- **Peningkatan `UniversalExtractor`:** Memperbarui `apps/api/utils/extractor.py` untuk membongkar host-host keras kepala seperti *Doodstream* atau *DesuDrive* secara lebih agresif.
- **Pemanfaatan TLSSpoof:** Beberapa provider menolak *request* dari server *Cloud*. Kita akan meningkatkan penggunaan `curl_cffi` (TLSSpoof) agar ekstraktor kita terlihat seperti Browser Chrome asli.