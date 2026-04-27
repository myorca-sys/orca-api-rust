"use client";

import { useState, useEffect, useRef } from "react";
import { HomeSearchBar } from "./HomeSearchBar";
import { ContinueWatching } from "./ContinueWatching";
import { LatestGrid } from "@/ui/cards/LatestGrid";
import { authClient } from "@/core/lib/auth-client";
import { OrcaLogo } from "@/ui/icons/OrcaLogo";

const greet = () => {
  const h = new Date().getHours();
  if (h < 5) return "Konbanwa";
  if (h < 12) return "Ohayou";
  if (h < 17) return "Konnichiwa";
  return "Konbanwa";
};

// Lazy rendering wrapper untuk performa 0ms dan meringankan DOM HP
function LazySection({ children, minHeight = "400px" }: { children: React.ReactNode, minHeight?: string }) {
  const [inView, setInView] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const observer = new IntersectionObserver(([entry]) => {
      if (entry.isIntersecting) {
        setInView(true);
        observer.disconnect();
      }
    }, { rootMargin: "300px" }); // Render lebih awal sebelum user sampai

    if (ref.current) observer.observe(ref.current);
    return () => observer.disconnect();
  }, []);

  return (
    <div ref={ref} style={{ minHeight: inView ? "auto" : minHeight }}>
      {inView ? children : null}
    </div>
  );
}

export default function HomeView({ 
  initialHero = [], 
  initialAiring = [],
  initialLatest = [], 
  initialPopular = [],
  initialCompleted = [],
  initialTopRated = [],
  initialMovies = [],
}: { 
  initialHero?: any[]; 
  initialAiring?: any[];
  initialLatest?: any[]; 
  initialPopular?: any[]; 
  initialCompleted?: any[];
  initialTopRated?: any[];
  initialMovies?: any[];
  initialIsekai?: any[]; // Keep for prop compatibility with server page
  initialTrending?: any[]; // Keep for prop compatibility
}) {
  const { data: session } = authClient.useSession();
  const user = session?.user;

  // 1. Gabungkan Tayangan Terbaru + Airing (Deduplikasi)
  const ongoingMap = new Map();
  [...initialLatest, ...initialAiring].forEach(i => {
    const id = String(i.anilistId || i.id);
    if (!ongoingMap.has(id)) ongoingMap.set(id, i);
  });
  const ongoingItems = Array.from(ongoingMap.values());

  // 2. Gabungkan Populer + Skor Tertinggi + Tamat (Deduplikasi)
  const bestMap = new Map();
  [...initialPopular, ...initialTopRated, ...initialCompleted].forEach(i => {
    const id = String(i.anilistId || i.id);
    if (!bestMap.has(id)) bestMap.set(id, i);
  });
  const bestItems = Array.from(bestMap.values());

  return (
    <div className="w-full pb-24 bg-black min-h-screen text-white selection:bg-[#0A84FF]/30">
      {/* Static Orca Logo */}
      <div className="px-6 md:px-10 pt-8 pb-2">
        <h1 className="text-[28px] font-black text-white tracking-tight flex items-center gap-2">
          <OrcaLogo className="w-8 h-8 text-white" animated={false} />
          Orca<span className="text-[#0A84FF]">.</span>
        </h1>
      </div>

      {/* Top Header Section — Minimalist */}
      <div className="pt-4 pb-8 anim-fade">
        <div className="px-6 md:px-10 flex items-center gap-2 mb-6">
          <div className="w-2 h-2 rounded-full bg-[#32D74B] shadow-[0_0_8px_#32D74B]" />
          <p className="text-[#8e8e93] text-[11px] font-bold tracking-[0.2em] uppercase">
            {greet()}, {user?.name || "Guest"}
          </p>
        </div>

        {/* Continue Watching Section */}
        <ContinueWatching userId={user?.id} />
      </div>

      {/* Search Bar Section */}
      <div className="sticky top-0 z-50 bg-black/80 backdrop-blur-2xl border-b border-white/5 py-3 px-5 md:px-10 mb-8 w-full transition-all">
        <div className="max-w-4xl mx-auto">
          <HomeSearchBar />
        </div>
      </div>

      {/* Section 1: Ongoing (Render immediately as it's above the fold) */}
      {ongoingItems.length > 0 && (
        <LatestGrid title="Sedang Tayang & Terbaru" items={ongoingItems} badge="NEW" />
      )}

      {/* Lazy Sections for heavy components below the fold */}
      <div className="space-y-4">
        {/* Section 2: Best Completed */}
        {bestItems.length > 0 && (
          <LazySection>
            <LatestGrid title="Anime Tamat Terbaik" items={bestItems} badge="BEST" />
          </LazySection>
        )}
        
        {/* Section 3: Movies */}
        {initialMovies.length > 0 && (
          <LazySection>
            <LatestGrid title="Film Anime (Movies)" items={initialMovies} badge="MOVIE" />
          </LazySection>
        )}
      </div>
      
      {/* Decorative Gradient */}
      <div className="fixed bottom-0 left-0 w-full h-[150px] pointer-events-none bg-gradient-to-t from-black to-transparent opacity-60 z-10" />
    </div>
  );
}
