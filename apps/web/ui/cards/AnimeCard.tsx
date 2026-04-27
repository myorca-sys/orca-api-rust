// ui/cards/AnimeCard.tsx — Zero-fetch card. Image comes from parent data.
// KEY FIX: No more individual AniList API calls per card.
// Backend v2/home already provides coverImage for all anime.

"use client";

import { memo, useRef, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { IconPlay, IconCheck } from "@/ui/icons";
import { useWatchHistory } from "@/core/hooks/use-watch-history";

interface Props {
  id: string;
  title: string;
  img: string | null;
  banner?: string | null;
  score?: number | null;
  color?: string | null;
  epId?: string;
  rank?: number;
  variant?: "vertical" | "horizontal";
  isNew?: boolean; // Deprecated in favor of badge
  badge?: "NEW" | "BEST" | "MOVIE";
  totalEps?: number | null;
  views?: number | null;
}

function formatViews(v: number): string {
  if (v >= 1000000) return (v / 1000000).toFixed(1) + "M";
  if (v >= 1000) return (v / 1000).toFixed(1) + "K";
  return v.toString();
}

function AnimeCardInner({ id, title, img, banner, score, color, epId, rank, variant = "vertical", isNew, badge, totalEps, views }: Props) {
  const accent = "#0A84FF";
  const { history } = useWatchHistory();
  const ref = useRef<HTMLDivElement>(null);
  const [visible, setVisible] = useState(false);
  const router = useRouter();

  const watched = history.find((h) => h.animeSlug === id);
  const pct = watched && watched.durationSec > 0 ? (watched.timestampSec / watched.durationSec) * 100 : 0;

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const obs = new IntersectionObserver(([e]) => { if (e.isIntersecting) { setVisible(true); obs.disconnect(); } }, { rootMargin: "200px" });
    obs.observe(el);
    return () => obs.disconnect();
  }, []);

  const handleMouseEnter = () => {
    const href = `/anime/${id}`;
    // Prefetch route Next.js
    router.prefetch(href);
  };

  const c = color || accent;
  const href = `/anime/${id}`;

  const aspectClass = variant === "horizontal" ? "aspect-video" : "aspect-[2/3]";
  const imageSrc = variant === "horizontal" ? (banner || img) : img;
  
  const currentBadge = badge || (isNew ? "NEW" : null);

  return (
    <div ref={ref} onMouseEnter={handleMouseEnter} onTouchStart={handleMouseEnter} className="flex flex-col h-full w-full group cursor-pointer anim-up" style={{ animationDelay: rank ? `${Math.min(rank * 40, 240)}ms` : "0ms" }}>
      <Link href={href} prefetch={true} className={`w-full ${aspectClass} rounded-2xl relative overflow-hidden mb-2 border border-white/5 bg-[#1c1c1e] block transition-shadow duration-300 group-hover:shadow-[0_8px_24px_rgba(0,0,0,0.5)] text-left focus:outline-none`}>
        {visible && imageSrc ? (
          <img src={imageSrc} alt={title} className="w-full h-full object-cover transition-transform duration-500 group-hover:scale-105" loading="lazy" decoding="async" onError={(e) => { e.currentTarget.src = img || "https://s4.anilist.co/file/anilistcdn/media/anime/cover/medium/default.jpg"; }} />
        ) : (
          <div className="w-full h-full bg-[#2c2c2e] flex items-center justify-center">
            {visible ? <div className="w-6 h-6 border-2 border-white/20 border-t-white/60 rounded-full anim-spin" /> : null}
          </div>
        )}

        <div className="absolute inset-0 bg-gradient-to-t from-black/80 via-transparent to-transparent pointer-events-none" />
        <div className="absolute inset-0 opacity-0 group-hover:opacity-100 transition-opacity duration-300 pointer-events-none" style={{ boxShadow: `inset 0 -30px 50px -15px ${c}60` }} />

        {rank && (
          <div className="absolute top-0 left-0 w-7 h-9 bg-black/60 rounded-br-xl flex items-center justify-center font-black text-sm text-white z-10">{rank}</div>
        )}

        {!rank && currentBadge === "NEW" && (
          <span className="absolute top-2 left-2 px-1.5 py-0.5 bg-gradient-to-r from-[#FFCC00] to-[#FF9500] text-black text-[9px] font-black uppercase tracking-wider rounded shadow-md z-10">NEW</span>
        )}
        {!rank && currentBadge === "BEST" && (
          <span className="absolute top-2 left-2 px-1.5 py-0.5 bg-gradient-to-r from-[#32D74B] to-[#30D158] text-black text-[9px] font-black uppercase tracking-wider rounded shadow-md z-10">BEST</span>
        )}
        {!rank && currentBadge === "MOVIE" && (
          <span className="absolute top-2 left-2 px-1.5 py-0.5 bg-gradient-to-r from-[#BF5AF2] to-[#AF52DE] text-white text-[9px] font-black uppercase tracking-wider rounded shadow-md z-10">MOVIE</span>
        )}

        {/* Dynamic Episode display based on badge */}
        <span className="absolute top-2 right-2 px-1.5 py-0.5 bg-[#FF453A]/90 text-[9px] font-bold uppercase tracking-wider rounded z-10 shadow-md">
          {currentBadge === "MOVIE" ? "HD" : 
           currentBadge === "BEST" ? `${totalEps || epId || '?'} EPS` :
           `EPS ${epId || totalEps || '?'}`}
        </span>

        <div className="absolute bottom-2 left-2 right-2 z-10 flex items-center justify-between opacity-0 group-hover:opacity-100 translate-y-3 group-hover:translate-y-0 transition-all duration-200">
          <span className="text-white/80 text-[10px] font-medium">{epId ? "Tonton" : "Detail"}</span>
          <div className="w-6 h-6 rounded-full bg-white/20 flex items-center justify-center"><IconPlay className="w-3 h-3 ml-0.5" /></div>
        </div>

        {watched && (
          <div className="absolute bottom-0 left-0 w-full h-1 bg-white/20 z-20">
            <div className="h-full transition-all" style={{ width: `${pct}%`, backgroundColor: accent }} />
          </div>
        )}
      </Link>
      <h3 className="text-[#f2f2f7] font-semibold text-[13px] line-clamp-2 leading-[1.3] px-0.5 group-hover:text-white transition-colors">{title}</h3>
      <div className="flex items-center gap-2 mt-1 px-0.5">
        {score ? (
          <span className="text-[10px] font-bold text-[#FFD60A] flex items-center gap-0.5">
            ★ {(score / 10).toFixed(1)}
          </span>
        ) : null}
        {views != null && views > 0 ? (
          <span className="text-[10px] font-bold text-[#8e8e93] flex items-center gap-0.5">
            <svg className="w-3 h-3" fill="none" stroke="currentColor" strokeWidth={1.5} viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" d="M2.036 12.322a1.012 1.012 0 010-.639C3.423 7.51 7.36 4.5 12 4.5c4.638 0 8.573 3.007 9.963 7.178.07.207.07.431 0 .639C20.577 16.49 16.64 19.5 12 19.5c-4.638 0-8.573-3.007-9.963-7.178z"/><path strokeLinecap="round" strokeLinejoin="round" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"/></svg>
            {formatViews(views)}
          </span>
        ) : null}
        {watched?.completed && (
          <span className="text-[10px] font-bold text-[#30D158] flex items-center gap-0.5"><IconCheck className="w-3 h-3" /> Selesai</span>
        )}
      </div>
    </div>
  );
}

export const AnimeCard = memo(AnimeCardInner);

