// features/detail/EpisodeList.tsx — Episode list without images
"use client";

import { useState, memo, useEffect } from "react";
import Link from "next/link";
import { IconSort } from "@/ui/icons";
import { useWatchHistory } from "@/core/hooks/use-watch-history";

interface Episode { title: string; url: string; number: number; provider?: string; thumbnailUrl?: string | null; }

function EpisodeListInner({ episodes, animeId }: { episodes: Episode[]; animeId: string; cover?: string }) {
  const [reversed, setReversed] = useState(false);
  const [limit, setLimit] = useState(50);
  const [mounted, setMounted] = useState(false);
  
  useEffect(() => setMounted(true), []);
  const { history } = useWatchHistory();

  if (!episodes?.length) return (
    <div className="bg-[#1c1c1e] p-6 text-center rounded-2xl text-[#8e8e93] border border-white/5 text-sm font-medium">
      Belum ada episode.
    </div>
  );

  const sorted = reversed ? [...episodes].reverse() : episodes;
  const view = sorted.slice(0, limit);

  return (
    <div className="flex flex-col gap-4 anim-fade">
      <div className="flex justify-between items-center mb-2">
        <span className="text-[#8e8e93] text-sm font-bold">{episodes.length} Episode Total</span>
        <button onClick={() => setReversed(!reversed)} className="flex items-center gap-1.5 px-3 py-1.5 bg-[#1c1c1e] border border-white/10 rounded-lg text-[11px] font-bold text-white active:scale-95 transition-colors hover:bg-white/5">
          <IconSort /> {reversed ? "Baru → Lama" : "Lama → Baru"}
        </button>
      </div>

      {/* Grid of buttons for episodes */}
      <div className="grid grid-cols-4 sm:grid-cols-5 md:grid-cols-6 lg:grid-cols-8 gap-2.5">
        {view.map((ep, i) => {
          const epId = (ep.url || "").replace(/\/$/, "").split("/").pop() || String(ep.number);
          const w = mounted ? history.find((h) => h.animeSlug === animeId && h.episode.toString() === epId) : undefined;
          const pct = w && w.durationSec > 0 ? (w.timestampSec / w.durationSec) * 100 : 0;
          const isWatched = w?.completed;

          return (
            <Link 
              key={`${epId}-${i}`} 
              href={`/watch/${animeId}/${epId}`} 
              className={`relative overflow-hidden group flex items-center justify-center py-3 rounded-xl border transition-all duration-300 active:scale-95 ${
                isWatched 
                  ? "bg-[#1c1c1e]/80 border-white/5 text-white/50" 
                  : pct > 0 
                    ? "bg-[#1c1c1e] border-[#0A84FF]/30 text-white" 
                    : "bg-[#1c1c1e] border-white/10 text-white hover:bg-white/10 hover:border-white/20"
              }`}
            >
              <div className="flex flex-col items-center justify-center relative z-10">
                <span className="text-xs font-black">Eps {epId}</span>
              </div>

              {/* Progress bar at bottom of the button if partially watched */}
              {!isWatched && pct > 0 && (
                <div className="absolute bottom-0 left-0 w-full h-1 bg-white/10">
                  <div className="h-full bg-[#0A84FF]" style={{ width: `${pct}%` }} />
                </div>
              )}
            </Link>
          );
        })}
      </div>

      {limit < episodes.length && (
        <button onClick={() => setLimit((p) => p + 50)} className="w-full mt-2 py-3 bg-[#1c1c1e] hover:bg-white/10 border border-white/10 transition-colors text-white rounded-xl font-bold text-sm active:scale-95">
          Muat Lebih ({episodes.length - limit} tersisa)
        </button>
      )}
    </div>
  );
}

export const EpisodeList = memo(EpisodeListInner);
