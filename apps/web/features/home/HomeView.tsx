// features/home/HomeView.tsx — Apple HIG Style

"use client";

import { HomeSearchBar } from "./HomeSearchBar";
import { HomeGenreGrid } from "./HomeGenreGrid";
import { ContinueWatching } from "./ContinueWatching";
import { AnimeRow } from "@/ui/cards/AnimeRow";
import { SpecialPopularRow } from "@/ui/cards/SpecialPopularRow";
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

export default function HomeView({ 
  initialHero = [], 
  initialAiring = [],
  initialLatest = [], 
  initialPopular = [],
  initialCompleted = [],
  initialTopRated = [],
  initialIsekai = [],
  initialMovies = [],
  initialTrending = []
}: { 
  initialHero?: any[]; 
  initialAiring?: any[];
  initialLatest?: any[]; 
  initialPopular?: any[]; 
  initialCompleted?: any[];
  initialTopRated?: any[];
  initialIsekai?: any[];
  initialMovies?: any[];
  initialTrending?: any[];
}) {
  const { data: session } = authClient.useSession();
  const user = session?.user;

  return (
    <div className="w-full pb-24 bg-black min-h-screen text-white selection:bg-[#0A84FF]/30">
      {/* Dynamic Orca Logo */}
      <div className="px-6 md:px-10 pt-8 pb-2">
        <h1 className="text-[28px] font-black text-white tracking-tight flex items-center gap-2">
          <OrcaLogo className="w-8 h-8 text-white" animated={true} />
          Orca<span className="text-[#0A84FF]">.</span>
        </h1>
      </div>

      {/* Top Header Section — HIG: Minimalist & Spaced */}
      <div className="pt-4 pb-8 anim-fade">
        <div className="px-6 md:px-10 flex items-center gap-2 mb-6">
          <div className="w-2 h-2 rounded-full bg-[#32D74B] shadow-[0_0_8px_#32D74B]" />
          <p className="text-[#8e8e93] text-[11px] font-bold tracking-[0.2em] uppercase">
            {greet()}, {user?.name || "Guest"}
          </p>
        </div>

        {/* Continue Watching Section — HIG: Utility First */}
        <ContinueWatching userId={user?.id} />

        <div className="px-6 md:px-10 mt-4">
          <h1 className="text-[34px] md:text-[42px] font-black tracking-[-0.03em] leading-[1.05]">
            Temukan anime<br />
            <span className="text-transparent bg-clip-text bg-gradient-to-r from-white to-[#8e8e93]">favorit barumu.</span>
          </h1>
        </div>
      </div>

      {/* Search Bar Section */}
      <div className="sticky top-0 z-50 bg-black/80 backdrop-blur-2xl border-b border-white/5 py-3 px-5 md:px-10 mb-8 w-full transition-all">
        <div className="max-w-4xl mx-auto">
          <HomeSearchBar />
        </div>
      </div>

      {/* Latest Airing (Vertical Grid) */}
      <LatestGrid title="Tayangan Terbaru" items={initialLatest} isNew={true} />

      <div className="space-y-12">
        {/* Rows — HIG: Content is King */}
        {initialAiring.length > 0 && <AnimeRow title="Sedang Tayang (Airing)" items={initialAiring} />}
        {initialTrending.length > 0 && <SpecialPopularRow title="Populer Saat Ini" items={initialTrending} />}
        
        <HomeGenreGrid />
        
        {initialPopular.length > 0 && <AnimeRow title="Terpopuler Sepanjang Masa" items={initialPopular} />}
        {initialTopRated.length > 0 && <AnimeRow title="Skor Tertinggi" items={initialTopRated} />}
        
        {initialCompleted.length > 0 && <LatestGrid title="Anime Tamat Terbaik" items={initialCompleted} />}
        {initialIsekai.length > 0 && <AnimeRow title="Dunia Fantasi & Isekai" items={initialIsekai} />}
        {initialMovies.length > 0 && <AnimeRow title="Film Anime (Movies)" items={initialMovies} />}
      </div>
      
      {/* Visual Explainer Placeholder / Decorative Gradient */}
      <div className="fixed bottom-0 left-0 w-full h-[150px] pointer-events-none bg-gradient-to-t from-black to-transparent opacity-60 z-10" />
    </div>
  );
}

