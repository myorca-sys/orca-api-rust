"use client";

import { useState, useRef } from "react";
import { AnimeCard } from "./AnimeCard";

interface Props {
  title: string;
  items: any[];
  isNew?: boolean; // Deprecated
  badge?: "NEW" | "BEST" | "MOVIE";
}

export function LatestGrid({ title, items, isNew = false, badge }: Props) {
  const [visibleCount, setVisibleCount] = useState(12);
  const sectionRef = useRef<HTMLElement>(null);

  if (!items || items.length === 0) return null;

  const visibleItems = items.slice(0, visibleCount);
  const hasMore = visibleCount < items.length;

  return (
    <section ref={sectionRef} className="mb-12 px-5 md:px-8 max-w-7xl mx-auto w-full">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-xl md:text-2xl font-black text-white tracking-tight">{title}</h2>
      </div>
      
      <div className="grid grid-cols-3 sm:grid-cols-4 md:grid-cols-5 lg:grid-cols-6 gap-3 md:gap-4 anim-fade">
        {visibleItems.map((a, i) => {
          const id = String(a.anilistId || a.id || "");
          if (!id) return null;
          return (
            <div key={`${id}-${i}`} className="w-full">
              <AnimeCard
                id={id}
                title={a.title?.english || a.title?.romaji || a.title || ""}
                img={a.img || a.coverImage?.extraLarge || a.coverImage?.large || null}
                banner={a.banner || a.bannerImage || null}
                score={a.score || a.averageScore}
                views={a.views}
                color={a.color || a.coverImage?.color}
                epId={a.latestEpisode ? String(a.latestEpisode) : (a.episodes ? String(a.episodes) : undefined)}
                totalEps={a.episodes}
                variant="vertical"
                isNew={isNew}
                badge={badge}
              />
            </div>
          );
        })}
      </div>

      <div className="mt-8 flex justify-center gap-3">
        {hasMore && (
          <button 
            onClick={() => setVisibleCount(items.length)}
            className="px-6 py-2.5 bg-white/10 hover:bg-white/20 rounded-full text-sm font-bold text-white transition-all active:scale-95 border border-white/5"
          >
            Tampilkan Lebih Banyak
          </button>
        )}
        {visibleCount > 12 && (
          <button 
            onClick={() => {
              if (sectionRef.current) {
                const y = sectionRef.current.getBoundingClientRect().top + window.scrollY - 100;
                window.scrollTo({ top: y, behavior: 'smooth' });
              }
              // Set timeout is added so the scroll starts right before or during the element resizing
              setTimeout(() => setVisibleCount(12), 100);
            }}
            className="px-6 py-2.5 bg-white/5 hover:bg-white/10 rounded-full text-sm font-bold text-white/60 hover:text-white transition-all active:scale-95 border border-white/5"
          >
            Tampilkan Lebih Sedikit
          </button>
        )}
      </div>
    </section>
  );
}
