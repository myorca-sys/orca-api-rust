// core/lib/api.ts — Centralized API client. All backend calls go through here.

const API = process.env.NEXT_PUBLIC_API_URL ?? "https://jonyyyyyyyu-anime-scraper-api.hf.space";

class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const isLocalNextRoute = path.startsWith("/api/anilist") || path.startsWith("/api/history");

  let url = path;
  if (path.startsWith("http")) {
    url = path;
  } else if (isLocalNextRoute) {
    // Di server komponen, kita tidak bisa ngefetch ke route relatif tanpa base URL
    const baseUrl = typeof window === 'undefined' 
      ? (process.env.VERCEL_URL ? `https://${process.env.VERCEL_URL}` : 'http://localhost:3000') 
      : '';
    url = `${baseUrl}${path}`;
  } else {
    url = `${API}${path}`;
  }

  const res = await fetch(url, {
    ...init,
    headers: { "Content-Type": "application/json", ...init?.headers },
  });

  if (!res.ok) throw new ApiError(res.status, `HTTP ${res.status}`);
  return res.json();
}

// ── Typed API methods ──────────────────────────────────────────────

export const api = {
  /** Homepage data from our DB (fast, verified) */
  homeV2: (init?: RequestInit) => request<{ success: boolean; data: { hero: any[]; airing?: any[]; latest: any[]; popular: any[]; completed?: any[]; top_rated?: any[]; isekai?: any[]; movies?: any[]; trending?: any[] } }>("/api/v2/home", init),

  /** Full anime detail + episodes */
  animeDetail: (id: number | string, init?: RequestInit) => request<{ success: boolean; syncing?: boolean; data: any }>(`/api/v2/anime/${id}`, init),

  /** Lightweight episode list only */
  episodes: (id: number | string, init?: RequestInit) => request<{ success: boolean; data: any[] }>(`/api/v2/anime/${id}/episodes`, init),

  /** Resolved video sources for an episode */
  stream: (id: number | string, ep: number | string, init?: RequestInit) => request<{ success: boolean; sources: any[]; downloads?: any[] }>(`/api/v2/anime/${id}/episodes/${ep}/stream?t=${Date.now()}`, init),

  /** Series list from provider (v1 — only used as fallback) */
  seriesList: (init?: RequestInit) => request<{ success: boolean; data: any[] }>("/api/series", init),

  /** Browse catalog from our DB */
  browse: (params: { page?: number; q?: string; genre?: string; sort?: string }, init?: RequestInit) => {
    const q = new URLSearchParams();
    if (params.page) q.set("page", String(params.page));
    if (params.q) q.set("q", params.q);
    if (params.genre) q.set("genre", params.genre);
    if (params.sort) q.set("sort", params.sort);
    return request<{ success: boolean; page: number; data: any[] }>(`/api/v2/browse?${q.toString()}`, init);
  },

  /** AniList GraphQL proxy or direct call */
  anilist: (query: string, variables?: Record<string, any>, init?: RequestInit) => {
    // Selalu hit langsung ke AniList untuk menghindari rate limit IP server Cloudflare
    const url = 'https://graphql.anilist.co';
    
    return request<any>(url, {
      method: "POST",
      body: JSON.stringify({ query, variables }),
      ...init
    });
  },
};

export { API, ApiError };
