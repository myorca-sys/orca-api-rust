# 🎯 Delegasi Tugas: Optimasi Auto-Mapper / Reconciler
**Kepada:** Claude (Senior Architect) & Agen 1 (Backend)
**Dari:** Agen 4 (Lead Assistant)

## 📌 Latar Belakang Masalah
Saat ini, *frontend* pengguna tidak bisa memutar *direct stream* dari `Kuronime` untuk anime besar seperti *One Piece* atau *Dan Da Dan*. Padahal, `KuronimeProvider` kita berhasil menarik data tersebut.

**Akar Masalah (Root Cause):**
Tabel `anime_mappings` di database gagal merekam ("menjodohkan") *slug* dari Kuronime.
Jika kita melihat `apps/api/services/reconciler.py`, alur *reconciliation* saat ini bekerja seperti ini:
```python
    async def reconcile(self, provider_id: str, provider_slug: str, raw_title: str):
        # ...
        anilist_data = await fetch_anilist_info(raw_title)
        if not anilist_data:
            return None # <--- GAGAL DI SINI
```
Kuronime mengembalikan *raw_title* yang aneh (terkadang berupa *slug* seperti `one-piece-op` atau `dan-da-dan`). Ketika `raw_title` ini dikirim langsung ke API AniList via `fetch_anilist_info()`, pencariannya gagal (mengembalikan `None`), sehingga fungsi `reconcile()` langsung berhenti (*return None*) sebelum sempat menggunakan `GeminiMatcher` (Arbiter Semantik) kita yang canggih!

## 🛠️ Tugas Anda (Eksekusi Solusi 2)
Harap perbaiki logika di `apps/api/services/reconciler.py` (dan jika perlu `services/anilist.py`):
1. **Sanitasi `raw_title`:** Sebelum dikirim ke `fetch_anilist_info`, bersihkan *string* tersebut. Ganti tanda hubung (`-`) dengan spasi, hilangkan kata-kata pengganggu seperti `op`, `episode`, dll.
2. **Pencarian Agresif (Fuzzy Search):** Jika pencarian pertama ke AniList menggunakan `raw_title` gagal, jangan langsung `return None`. Gunakan `GeminiMatcher` untuk menebak judul aslinya, KEMUDIAN panggil kembali `fetch_anilist_info()` dengan judul hasil tebakan Gemini.
3. **Trigger Manual Mapping:** Buat *script* kecil atau fungsi API baru untuk mem- *force trigger* sinkronisasi katalog Kuronime agar tabel `anime_mappings` terisi dengan *One Piece* dan *Dan Da Dan*.

Terapkan *First Principles Thinking* untuk memastikan sistem rekonsiliasi kita tahan banting terhadap nama judul sekotor apa pun dari *provider* bajakan.

**Status saat ini:** Harap segera dieksekusi.
