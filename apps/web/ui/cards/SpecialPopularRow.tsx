"use client";

import { memo, useRef } from "react";
import Link from "next/link";
import { IconPlay } from "@/ui/icons";

interface Props {
  title: string;
  items: any[];
}

function SpecialPopularRowInner({ title, items }: Props) {
  const ref = useRef<HTMLDivElement>(null);

  if (!items || items.length === 0) return null;

  // Pastikan jumlah item adalah ganjil (1 Rank Utama + pasangan genap)
  // Maksimal 29 item. Jika 20 item, akan dipotong jadi 19 (1 + 18), sehingga tidak ada kartu yang sendirian.
  let safeLength = items.length;
  if (safeLength > 29) safeLength = 29;
  if (safeLength % 2 === 0) safeLength -= 1; 

  const displayItems = items.slice(0, safeLength);
  
  const rank1 = displayItems[0];
  const restItems = displayItems.slice(1);
  
  // Kelompokkan item sisanya menjadi pasangan (2,3), (4,5), dst.
  const pairedItems = [];
  for (let i = 0; i < restItems.length; i += 2) {
    pairedItems.push(restItems.slice(i, i + 2));
  }

  return (
    <section className="mb-12 w-full overflow-hidden relative py-14 bg-[#1c1c1e] text-white shadow-[inset_0_0_100px_rgba(0,0,0,0.4)]">
      {/* Abstract Texture Line Background (Topography style) */}
      <div 
        className="absolute inset-0 z-0 opacity-[0.05] pointer-events-none" 
        style={{ 
          backgroundImage: `url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='100' height='100' viewBox='0 0 100 100'%3E%3Cpath fill-rule='evenodd' d='M11 18c3.86 0 7-3.14 7-7s-3.14-7-7-7-7 3.14-7 7 3.14 7 7 7zm48 25c3.86 0 7-3.14 7-7s-3.14-7-7-7-7 3.14-7 7 3.14 7 7 7zm-43-7c1.657 0 3-1.343 3-3s-1.343-3-3-3-3 1.343-3 3 1.343 3 3 3zm63 31c1.657 0 3-1.343 3-3s-1.343-3-3-3-3 1.343-3 3 1.343 3 3 3zM34 90c1.657 0 3-1.343 3-3s-1.343-3-3-3-3 1.343-3 3 1.343 3 3 3zm56-76c1.657 0 3-1.343 3-3s-1.343-3-3-3-3 1.343-3 3 1.343 3 3 3zM12 86c2.21 0 4-1.79 4-4s-1.79-4-4-4-4 1.79-4 4 1.79 4 4 4zm28-65c2.21 0 4-1.79 4-4s-1.79-4-4-4-4 1.79-4 4 1.79 4 4 4zm23-11c2.76 0 5-2.24 5-5s-2.24-5-5-5-5 2.24-5 5 2.24 5 5 5zm-6 60c2.21 0 4-1.79 4-4s-1.79-4-4-4-4 1.79-4 4 1.79 4 4 4zm29 22c2.76 0 5-2.24 5-5s-2.24-5-5-5-5 2.24-5 5 2.24 5 5 5zM32 63c2.76 0 5-2.24 5-5s-2.24-5-5-5-5 2.24-5 5 2.24 5 5 5zm57-13c2.76 0 5-2.24 5-5s-2.24-5-5-5-5 2.24-5 5 2.24 5 5 5zm-9-21c1.105 0 2-.895 2-2s-.895-2-2-2-2 .895-2 2 .895 2 2 2zM60 91c1.105 0 2-.895 2-2s-.895-2-2-2-2 .895-2 2 .895 2 2 2zM35 41c1.105 0 2-.895 2-2s-.895-2-2-2-2 .895-2 2 .895 2 2 2zM12 60c1.105 0 2-.895 2-2s-.895-2-2-2-2 .895-2 2 .895 2 2 2z' fill='%23ffffff' fill-opacity='1'/%3E%3C/svg%3E")` 
        }} 
      />
      <div className="absolute inset-0 z-0 pointer-events-none bg-[radial-gradient(circle_at_top_right,_rgba(255,255,255,0.05),_transparent_50%)]" />

      <div className="flex items-center justify-between mb-10 px-5 md:px-8 relative z-10">
        <h2 className="text-3xl md:text-4xl font-sans font-black text-transparent bg-clip-text bg-gradient-to-r from-white via-gray-200 to-gray-500 tracking-[-0.04em] flex items-center gap-2 drop-shadow-lg">
          {title}
        </h2>
      </div>

      <div 
        ref={ref}
        className="flex items-start overflow-x-auto snap-x snap-mandatory no-scrollbar px-5 md:px-8 gap-4 md:gap-6 pb-8 relative z-10"
        style={{ WebkitOverflowScrolling: "touch" }}
      >
        {/* RANK 1 - Besar, Berdiri Sendiri, 9:16 */}
        {rank1 && (
          <div className="shrink-0 snap-center w-[65vw] sm:w-[45vw] md:w-[30vw] lg:w-[22vw]">
            <Rank1Card item={rank1} rank={1} />
          </div>
        )}

        {/* RANK 2 dst - Disandingkan Atas Bawah (Satu Kolom 9:16 yang berisi 2 kartu) */}
        {pairedItems.map((pair, index) => {
          const startingRank = index * 2 + 2;
          return (
            <div key={`pair-${index}`} className="shrink-0 snap-center w-[65vw] sm:w-[45vw] md:w-[30vw] lg:w-[22vw] aspect-[9/16] flex flex-col gap-3 md:gap-4">
              {pair.map((item, pIndex) => (
                <PairedCard key={item.id || pIndex} item={item} rank={startingRank + pIndex} />
              ))}
            </div>
          );
        })}
      </div>
    </section>
  );
}

function Rank1Card({ item, rank }: { item: any, rank: number }) {
  const id = String(item.anilistId || item.id || "");
  const href = `/anime/${id}`;
  
  const img = item.coverImage?.extraLarge || item.coverImage?.large || item.img;

  return (
    <Link href={href} prefetch={true} className="block relative w-full aspect-[9/16] rounded-[24px] overflow-hidden group shadow-[0_20px_50px_rgba(0,0,0,0.5)] border border-white/10 bg-[#1c1c1e] transition-all duration-500 hover:-translate-y-2 hover:shadow-[0_30px_60px_rgba(0,0,0,0.7)] hover:border-white/20">
      {img && (
        <img 
          src={img} 
          alt={item.title?.english || item.title?.romaji || item.title} 
          className="w-full h-full object-cover transition-transform duration-[1500ms] group-hover:scale-110" 
          loading="lazy" 
        />
      )}
      
      <div className="absolute inset-0 bg-gradient-to-t from-black/95 via-black/30 to-transparent pointer-events-none" />
      <div className="absolute inset-0 rounded-[24px] border border-white/5 pointer-events-none" />
      
      <div className="absolute top-4 left-4 z-10">
        <div className="bg-white/95 backdrop-blur-md text-black font-black text-2xl italic px-4 py-1 rounded-xl shadow-[0_8px_16px_rgba(0,0,0,0.3)] transform -skew-x-6 flex items-center gap-1 border-b-4 border-gray-300">
          <span className="text-[#FFD60A]">★</span> #{rank}
        </div>
      </div>

      <div className="absolute bottom-6 left-5 right-5 z-10">
        <h3 className="text-2xl md:text-3xl font-black text-white mb-3 line-clamp-2 leading-tight tracking-tight drop-shadow-lg group-hover:text-[#0A84FF] transition-colors duration-300">
          {item.title?.english || item.title?.romaji || item.title}
        </h3>
        
        <div className="flex flex-wrap items-center gap-2">
          {(item.score || item.averageScore) ? (
            <span className="text-xs font-bold text-[#FFD60A] flex items-center gap-1 drop-shadow-sm bg-black/60 backdrop-blur-xl px-3 py-2 rounded-full border border-white/10">
              ★ {((item.score || item.averageScore) / 10).toFixed(1)}
            </span>
          ) : null}
        </div>
      </div>
    </Link>
  );
}

function PairedCard({ item, rank }: { item: any, rank: number }) {
  const id = String(item.anilistId || item.id || "");
  const href = `/anime/${id}`;
  
  // Menggunakan cover image (poster) agar sesuai dengan proporsi potrait 9:16
  const img = item.coverImage?.extraLarge || item.coverImage?.large || item.img;

  return (
    <Link href={href} prefetch={true} className="block relative w-full h-[calc(50%-6px)] md:h-[calc(50%-8px)] rounded-[20px] overflow-hidden group shadow-[0_12px_24px_rgba(0,0,0,0.3)] bg-[#2c2c2e]">
      {img && (
        <img 
          src={img} 
          alt={item.title?.english || item.title?.romaji || item.title} 
          className="w-full h-full object-cover object-center transition-transform duration-[1500ms] group-hover:scale-105" 
          loading="lazy" 
        />
      )}
      
      <div className="absolute inset-0 bg-gradient-to-t from-black/90 via-black/20 to-transparent pointer-events-none" />
      
      <div className="absolute top-3 left-3 z-10">
        <div className="bg-white/90 backdrop-blur-md text-black font-black text-sm italic px-2.5 py-0.5 rounded-lg shadow-sm border border-white/20">
          #{rank}
        </div>
      </div>

      <div className="absolute bottom-4 left-3 right-3 z-10">
        <h3 className="text-sm font-bold text-white mb-2 line-clamp-2 leading-tight drop-shadow-md group-hover:text-[#0A84FF] transition-colors duration-300">
          {item.title?.english || item.title?.romaji || item.title}
        </h3>
        
        <div className="flex flex-wrap items-center gap-1.5">
          {(item.score || item.averageScore) ? (
            <span className="text-[10px] font-bold text-[#FFD60A] flex items-center gap-0.5 bg-black/50 backdrop-blur-md px-1.5 py-0.5 rounded border border-white/10">
              ★ {((item.score || item.averageScore) / 10).toFixed(1)}
            </span>
          ) : null}
          {item.views != null && item.views > 0 ? (
            <span className="text-[10px] font-bold text-[#8e8e93] flex items-center gap-0.5 bg-black/50 backdrop-blur-md px-1.5 py-0.5 rounded border border-white/10">
              <svg className="w-3 h-3" fill="none" stroke="currentColor" strokeWidth={1.5} viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" d="M2.036 12.322a1.012 1.012 0 010-.639C3.423 7.51 7.36 4.5 12 4.5c4.638 0 8.573 3.007 9.963 7.178.07.207.07.431 0 .639C20.577 16.49 16.64 19.5 12 19.5c-4.638 0-8.573-3.007-9.963-7.178z"/><path strokeLinecap="round" strokeLinejoin="round" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"/></svg>
              {item.views >= 1000000 ? (item.views / 1000000).toFixed(1) + "M" : item.views >= 1000 ? (item.views / 1000).toFixed(1) + "K" : item.views}
            </span>
          ) : null}
          {item.latestEpisode && (
            <span className="text-[10px] font-bold text-white bg-[#FF453A] px-1.5 py-0.5 rounded border border-red-500/20">
              EPS {item.latestEpisode}
            </span>
          )}
        </div>
      </div>
    </Link>
  );
}

export const SpecialPopularRow = memo(SpecialPopularRowInner);