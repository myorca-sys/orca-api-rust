// features/explore/ExploreView.tsx — Search-first explore using our own DB
"use client";

import { useState, useEffect, useRef, Suspense } from "react";
import { useSearchParams } from "next/navigation";
import { api } from "@/core/lib/api";
import { AnimeCard } from "@/ui/cards/AnimeCard";
import { IconSearch, IconClose, IconClock } from "@/ui/icons";

const GENRES = [
  { name: "Action", gradient: "from-[#FF3B30] to-[#FF2D55]", image: "https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/nx21-6895.jpg" },
  { name: "Romance", gradient: "from-[#FF2D55] to-[#FF375F]", image: "https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx124080-mFmDofO0KkE3.jpg" },
  { name: "Fantasy", gradient: "from-[#5856D6] to-[#AF52DE]", image: "https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx154587-p2v7VSt9Xp4G.jpg" },
  { name: "Sci-Fi", gradient: "from-[#007AFF] to-[#5AC8FA]", image: "https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx16498-739Z7ot7i1uC.jpg" },
  { name: "Comedy", gradient: "from-[#FFCC00] to-[#FFD60A]", image: "https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx114129-9vH0X9667C26.jpg" },
  { name: "Drama", gradient: "from-[#FF9500] to-[#FFAC33]", image: "https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx101759-S9uV53YOfm96.jpg" },
  { name: "Horror", gradient: "from-[#1C1C1E] to-[#2C2C2E]", image: "https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx101922-W9SeY9v9vVv9.jpg" },
  { name: "Sports", gradient: "from-[#34C759] to-[#30D158]", image: "https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx20992-9vH0X9667C26.jpg" },
  { name: "Mecha", gradient: "from-[#64D2FF] to-[#5AC8FA]", image: "https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx21051-9vH0X9667C26.jpg" },
  { name: "Slice of Life", gradient: "from-[#FF9500] to-[#FFD60A]", image: "https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx100166-mFmDofO0KkE3.jpg" },
  { name: "Mystery", gradient: "from-[#AF52DE] to-[#BF5AF2]", image: "https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx11061-9vH0X9667C26.jpg" },
  { name: "Psychological", gradient: "from-[#5E5CE6] to-[#66d2ff]", image: "https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx21519-9vH0X9667C26.jpg" },
];

function useDebounce(val: string, ms: number) {
  const [d, setD] = useState(val);
  useEffect(() => { const t = setTimeout(() => setD(val), ms); return () => clearTimeout(t); }, [val, ms]);
  return d;
}

function getSearchHist(): string[] {
  try { return JSON.parse(localStorage.getItem("ani-search-v2") || "[]"); } catch { return []; }
}
function saveSearchHist(terms: string[]) {
  localStorage.setItem("ani-search-v2", JSON.stringify(terms.slice(0, 10)));
}

function ExploreViewInner({ initialResults = [] }: { initialResults?: any[] }) {
  const searchParams = useSearchParams();
  const q = searchParams.get("q") || "";
  const initGenre = searchParams.get("genre") || "";
  const [query, setQuery] = useState(q);
  const [genre, setGenre] = useState(initGenre);
  const [sort, setSort] = useState("popularity");
  const [results, setResults] = useState<any[]>(initialResults);
  const [loading, setLoading] = useState(false);
  const [searchHist, setSearchHist] = useState<string[]>([]);
  const dq = useDebounce(query, 600);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => setSearchHist(getSearchHist()), []);

  useEffect(() => {
    // Focus the input immediately when the page loads, unless we came here via a genre click
    if (!initGenre && inputRef.current) {
      inputRef.current.focus();
    }
  }, [initGenre]);

  useEffect(() => {
    if (!dq && !genre && sort === "popularity") {
      setResults(initialResults);
      setLoading(false);
      return;
    }

    setLoading(true);
    
    // We use our own api.browse instead of AniList so we only get mapped anime
    const vars: any = { page: 1, sort: sort };
    if (dq) vars.q = dq;
    if (genre) vars.genre = genre;

    api.browse(vars)
      .then((res) => {
        if (res?.success && res.data) {
          setResults(res.data.map((m: any) => ({
            id: String(m.anilistId),
            title: m.cleanTitle || m.nativeTitle || "",
            img: m.coverImage,
            score: m.score,
            color: m.color,
            status: m.status,
            seasonYear: m.year,
          })));
          
          if (dq && res.data.length > 0) {
            const updated = [dq, ...getSearchHist().filter((t) => t.toLowerCase() !== dq.toLowerCase())].slice(0, 10);
            saveSearchHist(updated);
            setSearchHist(updated);
          }
        } else {
          setResults([]);
        }
      })
      .catch((err) => {
        console.error("Fetch DB Error:", err);
        setResults([]);
      })
      .finally(() => setLoading(false));

  }, [dq, genre, sort, initialResults]);

  return (
    <div className="w-full pb-32">
      <div className="sticky top-0 z-30 bg-black/80 backdrop-blur-2xl px-5 md:px-8 pt-4 pb-4 border-b border-white/5">
        <div className="relative max-w-2xl mx-auto">
          <div className="absolute left-4 top-1/2 -translate-y-1/2 text-white/40"><IconSearch className="w-5 h-5" /></div>
          <input 
            ref={inputRef}
            autoFocus
            value={query} 
            onChange={(e) => setQuery(e.target.value)} 
            className="w-full bg-[#1c1c1e] text-white rounded-[16px] py-3.5 pl-12 pr-10 outline-none text-[16px] placeholder-white/30 border border-white/10 focus:border-white/20 transition-all shadow-lg" 
            placeholder="Anime, genre, atau studio..." 
          />
          {(query || genre) && (
            <button 
              onClick={() => { setQuery(""); setGenre(""); setResults([]); }} 
              className="absolute right-4 top-1/2 -translate-y-1/2 w-6 h-6 bg-white/10 hover:bg-white/20 rounded-full flex items-center justify-center text-white/60 transition-colors"
            >
              <IconClose className="w-3.5 h-3.5" />
            </button>
          )}
        </div>
      </div>

      <div className="px-5 md:px-8 pt-6">
        {query || genre ? (
          loading ? (
            <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 gap-3 lg:gap-4">
              {Array.from({ length: 12 }).map((_, i) => <div key={i} className="w-full aspect-[2/3] bg-[#1c1c1e] rounded-2xl animate-pulse" />)}
            </div>
          ) : results.length > 0 ? (
            <div className="anim-fade">
              <div className="flex justify-between items-center mb-4">
                <h2 className="text-sm font-bold text-white/60 uppercase tracking-widest">{genre ? `Genre: ${genre}` : "Hasil Pencarian"}</h2>
                <span className="text-white/40 text-[11px] font-medium">{results.length} item</span>
              </div>
              <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 gap-3 lg:gap-4">
                {results.map((a) => <AnimeCard key={a.id} id={String(a.id)} title={a.title} img={a.img} score={a.score} color={a.color} />)}
              </div>
            </div>
          ) : (
            <div className="flex flex-col items-center pt-20 text-center anim-fade">
              <div className="w-16 h-16 bg-[#1c1c1e] rounded-full flex items-center justify-center mb-6">
                <IconSearch className="w-8 h-8 text-white/20" />
              </div>
              <h3 className="text-white font-bold text-xl">Tidak Ditemukan</h3>
              <p className="text-white/40 text-sm mt-2 max-w-[200px]">Coba kata kunci atau filter genre yang berbeda.</p>
            </div>
          )
        ) : (
          <div className="anim-up max-w-5xl mx-auto space-y-10">
            {searchHist.length > 0 && (
              <div className="px-5 md:px-0">
                <div className="flex justify-between items-center mb-4">
                  <h2 className="text-lg font-bold text-white">Terakhir dicari</h2>
                  <button onClick={() => { saveSearchHist([]); setSearchHist([]); }} className="text-[#0A84FF] text-[13px] font-medium active:opacity-50 transition-opacity">Hapus Semua</button>
                </div>
                <div className="flex flex-wrap gap-2.5">
                  {searchHist.map((t, i) => (
                    <button key={i} onClick={() => setQuery(t)} className="flex items-center gap-2 px-4 py-2 bg-[#1c1c1e] hover:bg-[#2c2c2e] rounded-full border border-white/5 text-white/80 text-[13px] transition-colors">
                      <IconClock className="w-3.5 h-3.5 text-white/30" /> {t}
                    </button>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

export default function ExploreView(props: { initialResults?: any[] }) {
  return (
    <Suspense fallback={<div className="w-full min-h-screen bg-black" />}>
      <ExploreViewInner {...props} />
    </Suspense>
  );
}