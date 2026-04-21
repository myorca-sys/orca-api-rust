// app/watch/[id]/[episode]/page.tsx — Watch page (server-side fetch)

import WatchClient from "@/features/watch/WatchClient";
import { API } from "@/core/lib/api";

export const revalidate = 3600;
export const runtime = "edge";

export default async function WatchPage({ params }: { params: Promise<{ id: string; episode: string }> }) {
  const { id, episode } = await params;
  const anilistId = parseInt(id, 10);

  let allEpisodes: any[] = [];
  let recommendations: any[] = [];
  let title = `Episode ${episode}`;
  let poster = "";
  let animeDetails: any = null;

  // Hanya ambil detail dulu (metadata ringan)
  // Stream di-fetch CLIENT-SIDE setelah mount
  const detailRes = await fetch(`${API}/api/v2/anime/${anilistId}`, {
    next: { revalidate: 300 },
  });

  if (detailRes.ok) {
    const data = await detailRes.json();
    const anime = data.data;
    if (anime) {
      animeDetails = anime;
      title = anime.cleanTitle ?? anime.nativeTitle ?? title;
      poster = anime.bannerImage ?? anime.coverImage ?? "";
      recommendations = anime.recommendations ?? [];
      allEpisodes = (anime.episodes ?? []).map((e: any) => ({
        title: `Episode ${e.episodeNumber}`,
        url: `/watch/${id}/${e.episodeNumber}`,
        number: e.episodeNumber,
      }));
    }
  }

  return (
    <WatchClient 
      id={String(anilistId)} 
      episode={episode} 
      title={title} 
      poster={poster} 
      sources={[]} 
      allEpisodes={allEpisodes} 
      recommendations={recommendations} 
      animeDetails={animeDetails}
    />
  );
}
