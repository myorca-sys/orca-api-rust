/**
 * Cloudflare Worker: Video Host Reverse Proxy
 * 
 * Tujuan:
 * - Meneruskan request fetch dari browser klien (React) ke target video host
 * - Meneruskan IP asli klien via CF-Connecting-IP / X-Forwarded-For
 *   agar host yang strict IP-binding (seperti Mp4Upload) mengizinkan akses
 * - Menginjeksi CORS headers agar browser React bisa membaca response-nya
 *
 * Cara deploy:
 *   wrangler deploy (atau paste ke Cloudflare Workers dashboard)
 *
 * Endpoint:
 *   GET /proxy?url=<encoded_target_url>
 *   GET /proxy?url=<encoded_target_url>&extract=mp4  → langsung return JSON { videoUrl }
 */

const ALLOWED_ORIGINS = [
  "https://your-frontend-domain.com", // Ganti dengan domain frontend Anda
  "http://localhost:3000",             // Dev
  "http://localhost:5173",             // Vite Dev
];

const CORS_HEADERS = {
  "Access-Control-Allow-Origin": "*",           // Atau pakai ALLOWED_ORIGINS check di bawah
  "Access-Control-Allow-Methods": "GET, OPTIONS",
  "Access-Control-Allow-Headers": "Content-Type, X-Requested-With",
  "Access-Control-Max-Age": "86400",
};

// ─── Whitelist host yang diizinkan (keamanan) ─────────────────────────────────
const ALLOWED_HOSTS = [
  "mp4upload.com",
  "www.mp4upload.com",
  "doodstream.com",
  "dood.watch",
  "dsvplay.com",
  "krakenfiles.com",
  "pixeldrain.com"
  // Tambahkan host lain sesuai kebutuhan
];

function isAllowedHost(url) {
  try {
    const { hostname } = new URL(url);
    return ALLOWED_HOSTS.some(h => hostname === h || hostname.endsWith("." + h));
  } catch {
    return false;
  }
}

// ─── CORS Origin Check (opsional, lebih aman dari wildcard) ──────────────────
function getCorsOrigin(requestOrigin) {
  if (!requestOrigin) return "*";
  return ALLOWED_ORIGINS.includes(requestOrigin) ? requestOrigin : ALLOWED_ORIGINS[0];
}

// ─── Regex patterns untuk ekstraksi URL .mp4 langsung di Worker ──────────────
const MP4_PATTERNS = [
  // Mp4Upload style
  /player\.src\s*=\s*['"](https?:\/\/[^'"]+\.mp4[^'"]*)['"]/i,
  /file\s*:\s*['"](https?:\/\/[^'"]+\.mp4[^'"]*)['"]/i,
  /"src"\s*:\s*"(https?:\/\/[^"]+\.mp4[^"]*)"/i,
  // Generic
  /https?:\/\/[^\s"'<>]+\.mp4(?:\?[^\s"'<>]*)?/gi,
];

function extractMp4FromHtml(html) {
  for (const pattern of MP4_PATTERNS) {
    const globalPattern = new RegExp(pattern.source, pattern.flags.includes("g") ? pattern.flags : pattern.flags + "g");
    const matches = [...html.matchAll(globalPattern)];
    if (matches.length > 0) {
      // Kembalikan match group 1 jika ada (capturing group), atau match penuh
      return matches[0][1] || matches[0][0];
    }
  }
  return null;
}

// ─── Main Handler ─────────────────────────────────────────────────────────────
export default {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);
    const requestOrigin = request.headers.get("Origin");

    // Handle CORS preflight
    if (request.method === "OPTIONS") {
      return new Response(null, {
        status: 204,
        headers: {
          ...CORS_HEADERS,
          "Access-Control-Allow-Origin": getCorsOrigin(requestOrigin),
        },
      });
    }

    // Hanya izinkan GET
    if (request.method !== "GET") {
      return new Response(JSON.stringify({ error: "Method not allowed" }), {
        status: 405,
        headers: { "Content-Type": "application/json", ...CORS_HEADERS },
      });
    }

    // ── Parse parameter ────────────────────────────────────────────────────────
    const targetUrl = url.searchParams.get("url");
    const extractMode = url.searchParams.get("extract"); // "mp4" → return JSON

    if (!targetUrl) {
      return new Response(JSON.stringify({ error: "Missing 'url' parameter" }), {
        status: 400,
        headers: { "Content-Type": "application/json", ...CORS_HEADERS },
      });
    }

    // ── Validasi host ──────────────────────────────────────────────────────────
    try {
        if (!isAllowedHost(targetUrl)) {
          return new Response(JSON.stringify({ error: "Host not allowed", host: new URL(targetUrl).hostname }), {
            status: 403,
            headers: { "Content-Type": "application/json", ...CORS_HEADERS },
          });
        }
    } catch(e) {
        return new Response(JSON.stringify({ error: "Invalid URL" }), {
            status: 400,
            headers: { "Content-Type": "application/json", ...CORS_HEADERS },
        });
    }

    // ── Ambil IP asli klien ────────────────────────────────────────────────────
    // CF-Connecting-IP adalah IP visitor yang masuk ke Cloudflare (reliable)
    const clientIp =
      request.headers.get("CF-Connecting-IP") ||
      request.headers.get("X-Forwarded-For")?.split(",")[0].trim() ||
      "unknown";

    // ── Build headers untuk request ke target host ─────────────────────────────
    const forwardHeaders = new Headers({
      "User-Agent":
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
      Accept:
        "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
      "Accept-Language": "en-US,en;q=0.9",
      "Accept-Encoding": "gzip, deflate, br",
      Connection: "keep-alive",
      // ⬇ Meneruskan IP asli klien ke target host
      // PENTING: Ini membuat IP binding validation pada host pass dengan IP klien
      "X-Forwarded-For": clientIp,
      "X-Real-IP": clientIp,
      // Referer sesuai host target agar tidak ditolak
      Referer: new URL(targetUrl).origin + "/",
    });

    // ── Fetch ke target ────────────────────────────────────────────────────────
    let targetResponse;
    try {
      targetResponse = await fetch(targetUrl, {
        method: "GET",
        headers: forwardHeaders,
        redirect: "follow",
        // cf: { cacheTtl: 0 } // uncomment jika tidak ingin cache di Cloudflare edge
      });
    } catch (err) {
      return new Response(
        JSON.stringify({ error: "Failed to fetch target", detail: err.message }),
        {
          status: 502,
          headers: { "Content-Type": "application/json", ...CORS_HEADERS },
        }
      );
    }

    const contentType = targetResponse.headers.get("Content-Type") || "text/html";

    // ── Mode Ekstraksi: return JSON { videoUrl } ───────────────────────────────
    if (extractMode === "mp4") {
      const html = await targetResponse.text();
      const videoUrl = extractMp4FromHtml(html);

      if (!videoUrl) {
        return new Response(
          JSON.stringify({
            error: "No .mp4 URL found in page",
            hint: "Page might use JS obfuscation — use yt-dlp backend instead",
          }),
          {
            status: 404,
            headers: { "Content-Type": "application/json", ...CORS_HEADERS },
          }
        );
      }

      return new Response(JSON.stringify({ videoUrl, clientIp }), {
        status: 200,
        headers: {
          "Content-Type": "application/json",
          ...CORS_HEADERS,
          "Access-Control-Allow-Origin": getCorsOrigin(requestOrigin),
        },
      });
    }

    // ── Mode Proxy: teruskan HTML mentah dengan CORS headers ──────────────────
    // Salin response headers dari target, tambahkan CORS
    const responseHeaders = new Headers(targetResponse.headers);

    // Hapus header yang bisa menyebabkan masalah
    responseHeaders.delete("Content-Security-Policy");
    responseHeaders.delete("X-Frame-Options");
    responseHeaders.delete("Content-Encoding"); // Cloudflare sudah decompress

    // Injeksi CORS
    Object.entries(CORS_HEADERS).forEach(([k, v]) => responseHeaders.set(k, v));
    responseHeaders.set("Access-Control-Allow-Origin", getCorsOrigin(requestOrigin));
    responseHeaders.set("X-Proxied-By", "cf-video-proxy");
    responseHeaders.set("X-Client-IP", clientIp);

    return new Response(targetResponse.body, {
      status: targetResponse.status,
      headers: responseHeaders,
    });
  },
};