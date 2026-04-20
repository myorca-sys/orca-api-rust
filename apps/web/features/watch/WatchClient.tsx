"use client";

import { useState, useRef, useEffect } from "react";
import useSWR from "swr";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { VideoPlayer } from "@/ui/player/VideoPlayer";
import { AutoNextOverlay } from "@/ui/player/AutoNextOverlay";
import { IconBack, IconPlay, IconCheck, IconStar, IconShare, IconBookmark } from "@/ui/icons";
import { CommentSection } from "./CommentSection";
import { useCollection } from "@/core/hooks/use-collection";
import { authClient } from "@/core/lib/auth-client";
import { API } from "@/core/lib/api";

// Helper SVG icons for those missing in ui/icons
const HeartIcon = ({ size = 16, fill = "none" }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill={fill} stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round"><path d="M19 14c1.49-1.46 3-3.21 3-5.5A5.5 5.5 0 0 0 16.5 3c-1.76 0-3 .5-4.5 2-1.5-1.5-2.74-2-4.5-2A5.5 5.5 0 0 0 2 8.5c0 2.3 1.5 4.05 3 5.5l7 7Z"/></svg>
);
const DownloadIcon = ({ size = 16 }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" x2="12" y1="15" y2="3"/></svg>
);

interface Props {
  id: string;
  episode: string;
  title: string;
  poster: string;
  sources: any[];
  allEpisodes: any[];
  recommendations?: any[];
  animeDetails?: any;
}

export default function WatchClient({ id, episode: initialEpisode, title, poster, sources: initialSources, allEpisodes, recommendations = [], animeDetails }: Props) {
  const router = useRouter();
  const [activeEpisode, setActiveEpisode] = useState(initialEpisode);
  const [showAutoNext, setShowAutoNext] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [showAllEpisodes, setShowAllEpisodes] = useState(false);
  const [liked, setLiked] = useState(false);
  const [likes, setLikes] = useState(0);
  const [views] = useState(0);
  const epNum = parseFloat(activeEpisode) || 1;
  const [mounted, setMounted] = useState(false);
  const [showSynopsis, setShowSynopsis] = useState(false);

  const { data: session } = authClient.useSession();
  const { items, toggle } = useCollection(session?.user?.id);
  const isSaved = items.some(i => String(i.id) === id);

  const handleSave = () => {
    toggle({ id, title, img: poster, totalEps: allEpisodes.length });
  };

  const handleShare = () => {
    if (navigator.share) {
      navigator.share({
        title: `${title} - Episode ${activeEpisode}`,
        url: window.location.href
      }).catch(console.error);
    } else {
      navigator.clipboard.writeText(window.location.href);
      alert("Link disalin!");
    }
  };



  // Scroll current episode into view on mount
  const epsContainerRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!showAllEpisodes) {
      const activeEp = epsContainerRef.current?.querySelector('[data-active="true"]');
      if (activeEp) {
        activeEp.scrollIntoView({ behavior: 'smooth', inline: 'center', block: 'nearest' });
      }
    }
  }, [showAllEpisodes, activeEpisode]);

  // Sync state dengan prop (misal jika user klik back button)
  useEffect(() => {
    setActiveEpisode(initialEpisode);
  }, [initialEpisode]);

  const { data: epStats, mutate: mutateEpStats } = useSWR(
    mounted ? `https://jonyyyyyyyu-anime-scraper-api.hf.space/api/v2/social/episode/${id}/${activeEpisode}/stats${session?.user?.id ? `?user_id=${session.user.id}` : ''}` : null,
    async (url) => {
      const res = await fetch(url);
      return res.json();
    },
    { revalidateOnFocus: false }
  );

  const { data: animeStats, mutate: mutateAnimeStats } = useSWR(
    mounted ? `https://jonyyyyyyyu-anime-scraper-api.hf.space/api/v2/social/anime/${id}/stats` : null,
    async (url) => {
      const res = await fetch(url);
      return res.json();
    },
    { revalidateOnFocus: false }
  );

  const realLikes = epStats?.likes || 0;
  const isLiked = epStats?.user_liked || false;
  const realViews = animeStats?.total_episode_views || 0;

  useEffect(() => {
    if (!mounted || !session?.user?.id) return;

    const timer = setTimeout(() => {
      fetch('https://jonyyyyyyyu-anime-scraper-api.hf.space/api/v2/social/watch-event', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: session.user.id,
          anilistId: parseInt(id),
          episodeNumber: parseFloat(activeEpisode),
          event_type: 'complete',
          timestamp_sec: 0
        })
      }).then(() => {
        // Optimistically update views after watching for 5 seconds
        mutateAnimeStats((prev: any) => ({
          ...prev,
          total_episode_views: (prev?.total_episode_views || 0) + 1
        }), false);
      }).catch(console.error);
    }, 5000);

    return () => clearTimeout(timer);
  }, [activeEpisode, mounted, session?.user?.id, id, mutateAnimeStats]);
  const handleLike = async () => {
    if (!session?.user?.id) return alert("Silakan login untuk menyukai episode ini.");
    
    mutateEpStats((prev: any) => ({
      ...prev,
      likes: prev?.user_liked ? (prev.likes - 1) : (prev?.likes || 0) + 1,
      user_liked: !prev?.user_liked
    }), false);

    try {
      await fetch('https://jonyyyyyyyu-anime-scraper-api.hf.space/api/v2/social/episode/like', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: session.user.id,
          anilistId: parseInt(id),
          episodeNumber: parseFloat(activeEpisode)
        })
      });
      mutateEpStats();
    } catch (e) {
      console.error("Like failed", e);
      mutateEpStats();
    }
  };

  const handleEpisodeChange = (newEp: string) => {
    if (newEp === activeEpisode) return;
    
    // Update State (Instan)
    setActiveEpisode(newEp);
    setShowAutoNext(false);
    setCurrentTime(0);
    
    // Update URL secara silent (tanpa reload halaman/RSC fetch)
    const newPath = `/watch/${id}/${newEp}`;
    window.history.pushState({ ...window.history.state, as: newPath, url: newPath }, '', newPath);
  };

  // Fetch stream secara async berbasis activeEpisode
  const { data: streamData, isLoading: streamLoading, mutate } = useSWR(
    `stream-${id}-${activeEpisode}`,
    async () => {
      const res = await fetch(`${API}/api/v2/anime/${id}/episodes/${activeEpisode}/stream`);
      if (!res.ok) throw new Error('Failed to fetch');
      return res.json();
    },
    { revalidateOnFocus: false, dedupingInterval: 60000 }
  );

  const sources = streamData?.sources ?? (activeEpisode === initialEpisode ? initialSources : []);
  const downloads = streamData?.downloads ?? [];

  // Assuming episodes are sorted ascending by number
  const sortedEpisodes = [...allEpisodes].sort((a, b) => a.number - b.number);
  const currentIndex = sortedEpisodes.findIndex(e => e.number === epNum);
  const nextEp = currentIndex > -1 && currentIndex < sortedEpisodes.length - 1 ? sortedEpisodes[currentIndex + 1] : null;

  const handleSeek = (time: number) => {
    const v = document.querySelector("video");
    if (v) v.currentTime = time;
  };

  return (
    <div className="w-full min-h-[100dvh] bg-black flex flex-col anim-fade items-center">
      
      {/* Sticky Player (Full Width) */}
      <div className="sticky top-0 z-[100] w-full bg-black shadow-xl border-b border-[#2c2c2e]/50 max-w-[1200px] mx-auto">
        <button onClick={() => router.back()} className="absolute top-4 left-4 z-50 w-9 h-9 bg-black/40 rounded-full flex items-center justify-center text-white border border-white/10 active:scale-90 transition-transform"><IconBack /></button>
        <div className="relative w-full aspect-video flex flex-col justify-center min-h-0 bg-black overflow-hidden">
          <VideoPlayer 
            anilistId={parseInt(id, 10)}
            title={`${title} - Eps ${activeEpisode}`} 
            poster={poster} 
            sources={sources} 
            animeSlug={id} 
            episodeNum={epNum} 
            onRequireAutoNext={() => setShowAutoNext(true)} 
            onTimeUpdate={setCurrentTime}
            isLoadingSources={streamLoading && sources.length === 0}
            key={`player-${id}-${activeEpisode}`} // Force re-mount player for clean state
          />
          
          {showAutoNext && nextEp && (
            <AutoNextOverlay 
              nextEpisodeUrl={`/watch/${id}/${nextEp.number}`} 
              nextEpisodeTitle={`Episode ${nextEp.number} - ${nextEp.title || ''}`}
              nextThumbnail={nextEp.thumbnailUrl || poster}
              isLastEpisode={false}
              onCancel={() => setShowAutoNext(false)}
              onPlayNow={() => handleEpisodeChange(String(nextEp.number))}
            />
          )}
          {showAutoNext && !nextEp && (
            <AutoNextOverlay 
              isLastEpisode={true} 
              onCancel={() => setShowAutoNext(false)} 
              nextEpisodeUrl="" 
              nextEpisodeTitle="" 
            />
          )}
        </div>
      </div>

      {/* Main Content Column */}
      <div className="w-full max-w-[1200px] p-4 lg:p-6 space-y-6 lg:space-y-8 flex flex-col min-w-0 pb-10">
        
        {/* Title & Social Bar */}
        <div className="border-b border-white/10 pb-4">
          <h1 className="text-white font-black text-xl md:text-2xl leading-tight line-clamp-2">{title}</h1>
          <div className="flex flex-wrap items-center justify-between gap-4 mt-4">
            <div className="flex items-center gap-3">
              <span className="text-[#8e8e93] font-medium text-sm">{views}K views</span>
              <span className="w-1 h-1 rounded-full bg-[#8e8e93]" />
              <span className="text-[#0a84ff] font-bold text-sm bg-[#0a84ff]/10 px-2 py-0.5 rounded-md">Episode {activeEpisode}</span>
            </div>
            
            {/* Action Buttons (YouTube Style) */}
            <div className="flex items-center gap-2 overflow-x-auto no-scrollbar pb-1">
              <button 
                onClick={handleLike}
                className={`flex items-center gap-2 px-4 py-2 rounded-full font-bold text-sm transition-colors ${isLiked ? 'bg-[#ff453a]/20 text-[#ff453a]' : 'bg-white/10 text-white hover:bg-white/20'}`}
              >
                <HeartIcon size={16} fill={isLiked ? "currentColor" : "none"} />
                {realLikes}
              </button>
              
              <button 
                onClick={handleShare}
                className="flex items-center gap-2 px-4 py-2 rounded-full bg-white/10 hover:bg-white/20 font-bold text-sm text-white transition-colors"
              >
                <IconShare className="w-4 h-4" />
                Bagikan
              </button>
              
              <button 
                onClick={handleSave}
                className={`flex items-center gap-2 px-4 py-2 rounded-full font-bold text-sm transition-colors ${isSaved ? 'bg-[#30d158]/20 text-[#30d158]' : 'bg-white/10 text-white hover:bg-white/20'}`}
              >
                <IconBookmark className="w-4 h-4" filled={isSaved} />
                {isSaved ? 'Disimpan' : 'Simpan'}
              </button>

              {downloads.length > 0 && (
                <button 
                  onClick={() => document.getElementById('downloads-section')?.scrollIntoView({ behavior: 'smooth' })}
                  className="flex items-center gap-2 px-4 py-2 rounded-full bg-white/10 hover:bg-white/20 font-bold text-sm text-white transition-colors"
                >
                  <DownloadIcon size={16} />
                  Unduh
                </button>
              )}
            </div>
          </div>
        </div>

        {/* Episode List */}
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <h3 className="text-white font-bold text-base md:text-lg tracking-tight">Episode ({allEpisodes.length})</h3>
            <button 
              onClick={() => setShowAllEpisodes(!showAllEpisodes)}
              className="text-[#0a84ff] text-sm font-bold bg-[#0a84ff]/10 hover:bg-[#0a84ff]/20 px-3 py-1.5 rounded-lg transition-colors"
            >
              {showAllEpisodes ? "Tutup" : "Semua"}
            </button>
          </div>
          
          {showAllEpisodes ? (
            <div className="grid grid-cols-5 sm:grid-cols-8 md:grid-cols-10 lg:grid-cols-12 gap-2 anim-fade">
              {sortedEpisodes.map(ep => {
                const isActive = ep.number === epNum;
                return (
                  <button 
                    key={ep.number} 
                    onClick={() => handleEpisodeChange(String(ep.number))}
                    className={`flex items-center justify-center w-full aspect-square rounded-[10px] border text-[14px] font-bold transition-all ${
                      isActive 
                        ? "bg-white text-black border-white shadow-[0_0_12px_rgba(255,255,255,0.2)]" 
                        : "bg-[#1c1c1e] text-[#8e8e93] border-transparent hover:bg-white/10 hover:text-white"
                    }`}
                  >
                    {ep.number}
                  </button>
                )
              })}
            </div>
          ) : (
            <div ref={epsContainerRef} className="flex gap-2.5 overflow-x-auto no-scrollbar pb-2 pt-1 px-1 -mx-1 snap-x">
              {sortedEpisodes.map(ep => {
                const isActive = ep.number === epNum;
                return (
                  <button 
                    key={ep.number} 
                    onClick={() => handleEpisodeChange(String(ep.number))}
                    data-active={isActive}
                    className={`shrink-0 flex items-center justify-center min-w-[64px] px-4 h-12 rounded-[14px] border text-[15px] font-bold transition-all snap-start ${
                      isActive 
                        ? "bg-white text-black border-white shadow-[0_0_12px_rgba(255,255,255,0.2)]" 
                        : "bg-[#1c1c1e] text-[#8e8e93] border-transparent hover:bg-white/10 hover:text-white"
                    }`}
                  >
                    {isActive && <IconPlay className="w-4 h-4 text-black mr-1 -ml-1 fill-black" />}
                    {ep.number}
                  </button>
                )
              })}
            </div>
          )}
        </div>

        {/* Comments Section (YouTube Style) */}
        <div className="pt-4 border-t border-[#2c2c2e]/50">
          <h3 className="text-white font-bold text-base md:text-lg mb-4 tracking-tight">Komentar</h3>
          <CommentSection anilistId={id} episode={activeEpisode} currentTime={currentTime} onSeek={handleSeek} user={session?.user} />
        </div>

        {/* Recommendations (Horizontal Scroll) */}
        <div className="pt-4 border-t border-[#2c2c2e]/50 space-y-3">
          <h3 className="text-white font-bold text-base md:text-lg tracking-tight">Rekomendasi</h3>
          {recommendations && recommendations.length > 0 ? (
            <div className="flex gap-3 overflow-x-auto no-scrollbar pb-4 snap-x">
              {recommendations.slice(0, 10).map(rec => {
                const recImage = rec.cover || rec.image;
                const recTitle = typeof rec.title === 'string' ? rec.title : (rec.title?.userPreferred || rec.title?.english || "Anime");
                
                return (
                  <Link key={rec.id} href={`/anime/${rec.id}`} className="block group shrink-0 w-[140px] md:w-[160px] snap-start">
                    <div className="aspect-[3/4] bg-[#1c1c1e] rounded-xl overflow-hidden relative shadow-md">
                      {/* eslint-disable-next-line @next/next/no-img-element */}
                      {recImage ? (
                        <img 
                          src={recImage} 
                          alt={recTitle} 
                          className="w-full h-full object-cover transition-transform duration-500 group-hover:scale-110" 
                          loading="lazy"
                        />
                      ) : (
                        <div className="w-full h-full bg-[#2c2c2e] flex items-center justify-center text-[10px] text-[#8e8e93] p-4 text-center">
                          {recTitle}
                        </div>
                      )}
                      <div className="absolute inset-0 bg-gradient-to-t from-black/80 via-transparent to-transparent" />
                      <div className="absolute bottom-0 inset-x-0 p-2.5">
                        <p className="text-white font-bold text-[12px] leading-tight line-clamp-2">{recTitle}</p>
                      </div>
                    </div>
                  </Link>
                );
              })}
            </div>
          ) : (
            <div className="text-[#8e8e93] text-sm">Belum ada rekomendasi.</div>
          )}
        </div>

      </div>
    </div>
  );
}
