import base64
import json
import hashlib
import urllib.parse
from Crypto.Cipher import AES
from Crypto.Util.Padding import unpad
from services.transport import ProviderTransport
from providers.base_provider import BaseProvider
from providers.kuronime.parser import KuronimeParser
from providers.base_parser import AnimeDetail, EpisodeSource

BASE_URL = "https://kuronime.sbs"
API_URL = "https://animeku.org/api/v9/sources"
DECRYPT_KEY = "3&!Z0M,VIZ;dZW=="

class KuronimeProvider(BaseProvider):
    def __init__(self, transport: ProviderTransport):
        self._t = transport
        self._p = KuronimeParser()
        
    def _decrypt_cryptojs_aes(self, encrypted_text: str, password: str) -> str:
        try:
            data = json.loads(base64.b64decode(encrypted_text).decode("utf-8"))
            ct = base64.b64decode(data['ct'])
            salt = bytes.fromhex(data.get('s', ''))
        except Exception:
            return ""
            
        key_iv = b""
        prev = b""
        while len(key_iv) < 48:
            prev = hashlib.md5(prev + password.encode() + salt).digest()
            key_iv += prev
            
        key = key_iv[:32]
        iv = key_iv[32:48]
        
        cipher = AES.new(key, AES.MODE_CBC, iv)
        try:
            decrypted_data = unpad(cipher.decrypt(ct), AES.block_size)
            return decrypted_data.decode("utf-8")
        except Exception:
            return ""

    async def get_anime_detail(self, series_url: str) -> AnimeDetail:
        html = await self._t.get_html(series_url)
        return self._p.parse_episode_list(html, BASE_URL)

    async def get_episode_sources(self, episode_url: str) -> list[dict]:
        from utils.tls_spoof import TLSSpoofTransport
        try:
            # Gunakan TLSSpoof untuk mendapatkan HTML (bypass CF)
            html = await TLSSpoofTransport.get(episode_url)
        except Exception as e:
            print(f"[Kuronime] HTML fetch error via TLSSpoof: {e}")
            return []

        req_id = self._p.extract_req_id(html)
        
        sources = []
        if not req_id:
            return sources
            
        try:
            # Gunakan TLSSpoofTransport untuk bypass Cloudflare pada API Kuronime
            data = await TLSSpoofTransport.post(
                API_URL,
                json={"id": req_id},
                headers={"Referer": BASE_URL, "User-Agent": "Mozilla/5.0"}
            )
            print(f"[Kuronime Debug] API Response data keys: {list(data.keys()) if isinstance(data, dict) else 'Not a dict'}")
        except Exception as e:
            print(f"[Kuronime] API error via TLSSpoof: {e}")
            return sources
            
        # Parse src and src_sd (Direct streams)
        for q_key, quality in [("src", "1080p"), ("src_sd", "480p")]:
            encrypted_val = data.get(q_key)
            if encrypted_val:
                decrypted_str = self._decrypt_cryptojs_aes(encrypted_val, DECRYPT_KEY)
                print(f"[Kuronime Debug] Decrypted {q_key}: {decrypted_str}")
                try:
                    # Kadang kuronime mereturn string langsung (URL) bukannya JSON, mari kita handle
                    if decrypted_str.startswith("http"):
                        sources.append({
                            "provider": "KuroPlayer",
                            "quality": quality,
                            "url": decrypted_str,
                            "type": "hls (direct)"
                        })
                    else:
                        decrypted_json = json.loads(decrypted_str)
                        src_url = decrypted_json.get("src")
                        print(f"[Kuronime Debug] Found src_url: {src_url}")
                        if src_url:
                            sources.append({
                                "provider": "KuroPlayer",
                                "quality": quality,
                                "url": src_url,
                                "type": "hls (direct)"
                            })
                except Exception as e:
                    print(f"[Kuronime Debug] Parsing error for {q_key}: {e}")
                    pass
        
        # Parse mirror (Embeds)
        mirror_enc = data.get("mirror")
        if mirror_enc:
            decrypted_str = self._decrypt_cryptojs_aes(mirror_enc, DECRYPT_KEY)
            try:
                mirror_json = json.loads(decrypted_str)
                embeds = mirror_json.get("embed", {})
                for res_key, res_providers in embeds.items():
                    quality = res_key.replace("v", "")
                    
                    # Filter only 720p and 1080p
                    if quality not in ["720p", "1080p"]:
                        continue
                        
                    for provider_name, provider_url in res_providers.items():
                        if provider_url:
                            # Pixeldrain works directly like Wibufile
                            is_direct = "pixeldrain" in provider_url.lower()
                            sources.append({
                                "provider": provider_name.capitalize(),
                                "quality": quality,
                                "url": provider_url,
                                "type": "mp4 (direct)" if is_direct else "iframe"
                            })
            except Exception:
                pass
                            
        return sources

    async def search(self, query: str) -> list[dict]:
        try:
            url = f"{BASE_URL}/?s={urllib.parse.quote_plus(query)}"
            html = await self._t.get_html(url)
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html, "lxml")
            results = []
            for article in soup.select(".bsx"):
                a = article.select_one("a")
                if a:
                    results.append({"title": a.get("title", "").strip(), "url": a.get("href")})
            return results
        except Exception as e:
            print(f"[Kuronime] Search error: {e}")
            return []
