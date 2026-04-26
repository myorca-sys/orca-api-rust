"use client";

import { Megaphone } from "lucide-react";

export function RunningNotification() {
  // Anda bisa mengganti teks ini nanti dengan API call jika ingin dinamis
  const notificationText = "🌟 Anime baru The Angel Next Door S1 & S2 kualitas 1080p berhasil diupdate! 🚀 Tekan tombol 'Cek Pembaruan' di profil Anda untuk memastikan PWA berjalan lancar.";

  return (
    <div className="w-full bg-[#1c1c1e] border-b border-white/10 text-white overflow-hidden py-1.5 relative z-[60]">
      <div className="flex items-center">
        <div className="pl-4 pr-3 shrink-0 flex items-center justify-center bg-[#1c1c1e] z-10">
          <Megaphone className="w-3.5 h-3.5 text-[#0A84FF] mr-2" />
          <span className="text-[10px] font-black tracking-widest text-[#0A84FF] uppercase">INFO</span>
        </div>
        <div className="flex-1 overflow-hidden relative">
          <div className="whitespace-nowrap animate-marquee flex gap-8">
            <p className="text-[12px] font-medium leading-none text-white/90">
              {notificationText}
            </p>
            <p className="text-[12px] font-medium leading-none text-white/90" aria-hidden="true">
              {notificationText}
            </p>
          </div>
        </div>
      </div>
      <style jsx>{`
        .animate-marquee {
          animation: marquee 20s linear infinite;
        }
        @keyframes marquee {
          0% { transform: translateX(0%); }
          100% { transform: translateX(-50%); }
        }
      `}</style>
    </div>
  );
}
