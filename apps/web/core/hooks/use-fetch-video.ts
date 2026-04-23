import { useState, useEffect, useCallback, useRef } from "react";

// ── Konfigurasi ───────────────────────────────────────────────────────────────
const CF_WORKER_URL = process.env.NEXT_PUBLIC_CF_WORKER_URL || "https://video-proxy.moehamadhkl.workers.dev";
const DEFAULT_TIMEOUT_MS = 15_000; // 15 detik

/**
 * Hook untuk mengekstraksi URL video dari halaman embed video host
 * melalui Cloudflare Worker reverse proxy.
 *
 * @param {string|null} embedUrl  - URL halaman HTML yang mengandung tag <video> atau player.src
 * @param {Object}      options
 * @param {number}      [options.timeoutMs=15000]   - Timeout dalam milidetik
 * @param {boolean}     [options.enabled=true]      - Aktifkan/nonaktifkan fetch otomatis
 * @param {number}      [options.retryCount=2]      - Jumlah retry otomatis saat gagal
 * @returns {VideoUrlState}
 */
export function useFetchVideoUrl(embedUrl: string | null | undefined, options: any = {}) {
  const {
    timeoutMs = DEFAULT_TIMEOUT_MS,
    enabled = true,
    retryCount = 2,
  } = options;

  const [videoUrl, setVideoUrl]   = useState<string | null>(null);
  const [loading, setLoading]     = useState(false);
  const [error, setError]         = useState<string | null>(null);
  const [status, setStatus]       = useState("idle");

  // Ref untuk membatalkan request yang sedang berjalan
  const abortControllerRef = useRef<AbortController | null>(null);
  const retryRef            = useRef(0);

  const fetchVideoUrl = useCallback(async () => {
    if (!embedUrl) return;

    // Batalkan request sebelumnya jika ada
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }
    abortControllerRef.current = new AbortController();
    const { signal } = abortControllerRef.current;

    setLoading(true);
    setError(null);
    setStatus("loading");
    setVideoUrl(null);

    // Timeout via AbortController
    const timeoutId = setTimeout(() => {
      abortControllerRef.current?.abort();
    }, timeoutMs);

    try {
      // Encode URL target agar aman dikirim sebagai query param
      const workerUrl = `${CF_WORKER_URL}/proxy?url=${encodeURIComponent(embedUrl)}&extract=mp4`;

      const response = await fetch(workerUrl, {
        method: "GET",
        signal,
        headers: {
          Accept: "application/json",
        },
      });

      clearTimeout(timeoutId);

      if (!response.ok) {
        const errBody = await response.json().catch(() => ({}));
        throw new Error(errBody.error || `Worker responded with HTTP ${response.status}`);
      }

      const data = await response.json();

      if (!data.videoUrl) {
        throw new Error(data.error || "No video URL in response");
      }

      setVideoUrl(data.videoUrl);
      setStatus("success");
      retryRef.current = 0; // reset retry counter on success
    } catch (err: any) {
      clearTimeout(timeoutId);

      // Jangan treat abort sebagai error (user sengaja cancel)
      if (err.name === "AbortError") {
        setStatus("idle");
        setLoading(false);
        return;
      }

      // Retry otomatis
      if (retryRef.current < retryCount) {
        retryRef.current += 1;
        const delay = retryRef.current * 1000; // backoff: 1s, 2s, ...
        setTimeout(() => fetchVideoUrl(), delay);
        return;
      }

      setError(err.message);
      setStatus("error");
    } finally {
      setLoading(false);
    }
  }, [embedUrl, timeoutMs, retryCount]);

  // Refetch manual (reset retry counter)
  const refetch = useCallback(() => {
    retryRef.current = 0;
    fetchVideoUrl();
  }, [fetchVideoUrl]);

  // Auto-fetch saat embedUrl berubah
  useEffect(() => {
    if (!enabled || !embedUrl) return;
    retryRef.current = 0;
    fetchVideoUrl();

    return () => {
      abortControllerRef.current?.abort();
    };
  }, [embedUrl, enabled, fetchVideoUrl]);

  return { videoUrl, loading, error, status, refetch };
}
