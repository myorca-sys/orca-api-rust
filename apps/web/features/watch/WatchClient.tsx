"use client";

import { useState, useRef, useEffect } from "react";
import useSWR from "swr";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { VideoPlayer } from "@/ui/player/VideoPlayer";
import { AutoNextOverlay } from "@/ui/player/AutoNextOverlay";
import { IconBack, IconPlay, IconCheck, IconStar, IconShare, IconBookmark, IconFullscreen } from "@/ui/icons";
import { CommentSection } from "./CommentSection";
import { useCollection } from "@/core/hooks/use-collection";
import { authClient } from "@/core/lib/auth-client";
import { API } from "@/core/lib/api";
import DetailClient from "@/features/detail/DetailClient";

// Helper SVG icons for those missing in ui/icons
const HeartIcon = ({ size = 16, fill = "none" }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill={fill} stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round"><path d="M19 14c1.49-1.46 3-3.21 3-5.5A5.5 5.5 0 0 0 16.5 3c-1.76 0-3 .5-4.5 2-1.5-1.5-2.74-2-4.5-2A5.5 5.5 0 0 0 2 8.5c0 2.3 1.5 4.05 3 5.5l7 7Z"/></svg>
);
const DownloadIcon = ({ size = 16 }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" x2="12" y1="15" y2="3"/></svg>
);

const EyeIcon = ({ size = 16 }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round"><path d="M2 12s3-7 10-7 10 7 10 7-3 7-10 7-10-7-10-7Z"/><circle cx="12" cy="12" r="3"/></svg>
);

const ShareArrowIcon = ({ size = 16 }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round"><path d="m15 5 6 6-6 6"/><path d="M21 11H9C4.029 11 2 14 2 18"/></svg>
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
  const [isMinimized, setIsMinimized] = useState(false);
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

  useEffect(() => {
    setMounted(true);
  }, []);

  // Native PiP when leaving browser
  useEffect(() => {
    const handleVisibilityChange = () => {
      const v = document.querySelector("video");
      if (document.hidden && v && !v.paused && document.pictureInPictureEnabled) {
        v.requestPictureInPicture().catch(() => {});
      }
    };
    document.addEventListener("visibilitychange", handleVisibilityChange);
    return () => document.removeEventListener("visibilitychange", handleVisibilityChange);
  }, []);

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

  const handleMinimize = () => {
    // Meminta PiP native pada browser/OS jika tersedia
    const v = document.querySelector("video");
    if (v && document.pictureInPictureEnabled) {
      v.requestPictureInPicture().catch(() => {});
    }
    setIsMinimized(true);
    window.history.pushState(null, '', `/anime/${id}`);
  };

  const handleMaximize = () => {
    if (document.pictureInPictureElement) {
      document.exitPictureInPicture().catch(() => {});
    }
    setIsMinimized(false);
    window.history.pushState(null, '', `/watch/${id}/${activeEpisode}`);
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
    mounted ? `${API}/api/v2/social/episode/${id}/${activeEpisode}/stats${session?.user?.id ? `?user_id=${session.user.id}` : ''}` : null,
    async (url) => {
      const res = await fetch(url);
      return res.json();
    },
    { revalidateOnFocus: false }
  );

  const { data: animeStats, mutate: mutateAnimeStats } = useSWR(
    mounted ? `${API}/api/v2/social/anime/${id}/stats` : null,
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
      // Optimistically update views after watching for 5 seconds
      mutateAnimeStats((prev: any) => ({
        ...prev,
        total_episode_views: (prev?.total_episode_views || 0) + 1
      }), false);
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
      await fetch(`${API}/api/v2/social/episode/like`, {
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
      const res = await fetch(`${API}/api/v2/anime/${id}/episodes/${activeEpisode}/stream?t=${Date.now()}`);
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
  const prevEp = currentIndex > 0 ? sortedEpisodes[currentIndex - 1] : null;

  const handleSeek = (time: number) => {
    const v = document.querySelector("video");
    if (v) v.currentTime = time;
  };

  return (
    <>
      {/* Background Anime Details when minimized */}
      {isMinimized && animeDetails && (
        <div className="fixed inset-0 z-[100] bg-black overflow-y-auto no-scrollbar">
          <DetailClient detail={animeDetails} id={id} />
        </div>
      )}

      <div className={isMinimized ? "fixed bottom-24 right-4 w-64 md:w-80 z-[600] rounded-xl overflow-hidden shadow-2xl ring-1 ring-white/20 transition-all duration-300 anim-fade" : "w-full min-h-[100dvh] bg-black flex flex-col anim-fade items-center"}>
        
        {/* Sticky/Fixed Player (Full Width or Mini) */}
        <div className={isMinimized ? "relative w-full aspect-video flex flex-col justify-center min-h-0 bg-black overflow-hidden group" : "fixed md:sticky top-0 z-[500] w-full bg-black shadow-xl border-b border-[#2c2c2e]/50 max-w-[1200px] mx-auto"}>
          
          {!isMinimized && (
            <button onClick={handleMinimize} className="absolute top-4 left-4 z-50 w-9 h-9 bg-black/40 rounded-full flex items-center justify-center text-white border border-white/10 active:scale-90 transition-transform">
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><polyline points="6 9 12 15 18 9"></polyline></svg>
            </button>
          )}

          {isMinimized && (
            <div onClick={handleMaximize} className="absolute inset-0 z-50 bg-black/60 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center cursor-pointer">
              <IconFullscreen className="w-8 h-8 text-white drop-shadow-lg" />
            </div>
          )}

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
              onNext={nextEp ? () => handleEpisodeChange(String(nextEp.number)) : undefined}
              onPrevious={prevEp ? () => handleEpisodeChange(String(prevEp.number)) : undefined}
              views={realViews}
              likes={realLikes}
              isLiked={isLiked}
              onLike={handleLike}
              commentsSlot={<CommentSection anilistId={id} episode={activeEpisode} currentTime={currentTime} onSeek={handleSeek} user={session?.user} mode="side" />}
              key={`player-${id}-${activeEpisode}`} // Force re-mount player for clean state
              userId={session?.user?.id}
            />
            
            {showAutoNext && nextEp && !isMinimized && (
              <AutoNextOverlay 
                nextEpisodeUrl={`/watch/${id}/${nextEp.number}`} 
                nextEpisodeTitle={`Episode ${nextEp.number} - ${nextEp.title || ''}`}
                nextThumbnail={nextEp.thumbnailUrl || poster}
                isLastEpisode={false}
                onCancel={() => setShowAutoNext(false)}
                onPlayNow={() => handleEpisodeChange(String(nextEp.number))}
              />
            )}
            {showAutoNext && !nextEp && !isMinimized && (
              <AutoNextOverlay 
                isLastEpisode={true} 
                onCancel={() => setShowAutoNext(false)} 
                nextEpisodeUrl="" 
                nextEpisodeTitle="" 
              />
            )}
          </div>
        </div>

        {!isMinimized && (
          <>
            {/* Mobile Spacer (because player is fixed on mobile) */}
            <div className="w-full aspect-video md:hidden shrink-0" />

            {/* Main Content Column */}
            <div className="w-full max-w-[1200px] p-4 lg:p-6 space-y-4 flex flex-col min-w-0 pb-10">
        
        {/* Title & Social Bar */}
        <div>
          <h1 className="text-white font-bold text-lg md:text-xl leading-tight line-clamp-2 pb-3">
            {title} <span className="text-white/50 font-medium ml-1 text-base">· Eps {activeEpisode}</span>
          </h1>
          
          {/* Scrollable Action Bar */}
          <div className="flex items-center gap-2 overflow-x-auto no-scrollbar pb-3 -mx-4 px-4 lg:mx-0 lg:px-0">
            <Link href={`/anime/${id}`} className="shrink-0 active:scale-95 transition-transform mr-1">
               <img src={poster} alt="poster" className="w-9 h-9 rounded-full object-cover border border-white/10" />
            </Link>
            
            <button 
              onClick={handleSave}
              className={`shrink-0 px-4 py-2 rounded-full font-bold text-sm transition-colors ${isSaved ? 'bg-white/10 text-white' : 'bg-white text-black hover:bg-gray-200'}`}
            >
              {isSaved ? 'Tersimpan' : 'Simpan'}
            </button>
            
            {/* Views */}
            <div className="flex items-center gap-1.5 px-4 py-2 bg-white/10 rounded-full text-white text-sm font-bold hover:bg-white/20 transition-colors cursor-default shrink-0">
              <EyeIcon size={16} />
              {realViews > 1000 ? (realViews/1000).toFixed(1) + 'K' : realViews}
            </div>

            {/* Likes */}
            <button 
              onClick={handleLike}
              className={`flex items-center gap-2 px-4 py-2 bg-white/10 rounded-full font-bold text-sm transition-colors hover:bg-white/20 shrink-0 ${isLiked ? 'text-[#ff453a]' : 'text-white'}`}
            >
              <HeartIcon size={16} fill={isLiked ? "currentColor" : "none"} />
              {realLikes}
            </button>
            
            <button 
              onClick={handleShare}
              className="flex items-center justify-center px-4 py-2 rounded-full bg-white/10 hover:bg-white/20 font-bold text-sm text-white transition-colors shrink-0"
            >
              <ShareArrowIcon size={18} />
            </button>

            <button 
              onClick={() => alert("Fitur dukungan/Thanks (Saweria) akan segera hadir!")}
              className="flex items-center gap-1.5 px-4 py-2 rounded-full bg-white/10 hover:bg-white/20 font-bold text-sm text-white transition-colors shrink-0"
            >
              <div className="relative flex items-center justify-center">
                <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="2.5"><path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z"></path></svg>
                <span className="font-black text-[10px] absolute leading-none mt-[1px]">$</span>
              </div>
              Thanks
            </button>
            
            <button 
              onClick={() => alert("Formulir Laporan (Tele Bot) akan segera hadir!")}
              className="flex items-center gap-1.5 px-4 py-2 rounded-full bg-white/10 hover:bg-white/20 font-bold text-sm text-white transition-colors shrink-0"
            >
              <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><path d="M4 15s1-1 4-1 5 2 8 2 4-1 4-1V3s-1 1-4 1-5-2-8-2-4 1-4 1z"></path><line x1="4" y1="22" x2="4" y2="15"></line></svg>
              Lapor
            </button>
          </div>
        </div>

        {/* Comments Section (YouTube Style) */}
        <div>
          <CommentSection anilistId={id} episode={activeEpisode} currentTime={currentTime} onSeek={handleSeek} user={session?.user} />
        </div>

        {/* Episode List */}
        <div className="pt-2 space-y-3">
          <div className="flex items-center justify-between">
            <h3 className="text-white font-bold text-base tracking-tight">
              {showAllEpisodes ? `Episode (${allEpisodes.length})` : 'Episode'}
            </h3>
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

        {/* Recommendations (Horizontal Scroll) */}
        <div className="pt-2 space-y-3">
          <h3 className="text-white font-bold text-base tracking-tight">Rekomendasi</h3>
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
          </>
        )}
      </div>
    </>
  );
}
