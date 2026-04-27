"use client";

import { useState, useEffect } from "react";
import { useA2HS } from "@/core/hooks/use-a2hs";
import { X, Share, PlusSquare } from "lucide-react";
import { OrcaLogo } from "@/ui/icons/OrcaLogo";
import clsx from "clsx";

export function InstallPrompt() {
  const { isInstallable, isIOS, isStandalone, promptInstall } = useA2HS();
  const [show, setShow] = useState(false);

  useEffect(() => {
    // Jangan tampilkan jika sudah di-install
    if (isStandalone) return;

    // Beri delay 3 detik agar tidak terlalu intrusif (mengganggu) di awal render
    const timer = setTimeout(() => {
      const hasDismissed = localStorage.getItem("pwa_prompt_dismissed");
      if (!hasDismissed) {
        // Tampilkan jika Chrome bisa di-install ATAU jika perangkat adalah iOS (karena manual instruction)
        if (isInstallable || isIOS) {
          setShow(true);
        }
      }
    }, 3000);

    return () => clearTimeout(timer);
  }, [isInstallable, isIOS, isStandalone]);

  const handleDismiss = () => {
    setShow(false);
    // Simpan di local storage agar tidak muncul lagi untuk sementara
    localStorage.setItem("pwa_prompt_dismissed", "true");
  };

  if (!show) return null;

  return (
    <div className="fixed bottom-4 left-4 right-4 z-[9999] flex items-center justify-center pointer-events-none">
      <div className="pointer-events-auto max-w-sm w-full relative overflow-hidden rounded-2xl bg-black/60 backdrop-blur-xl border border-white/10 p-4 shadow-2xl transition-all duration-500 ease-out animate-in slide-in-from-bottom-8 fade-in">
        
        {/* Tombol Tutup */}
        <button
          onClick={handleDismiss}
          className="absolute right-3 top-3 p-1 rounded-full bg-white/10 hover:bg-white/20 transition-colors text-white/70"
          aria-label="Tutup"
        >
          <X className="w-4 h-4" />
        </button>

        <div className="flex gap-4 items-start pr-6">
          <div className="flex-shrink-0 w-12 h-12 bg-zinc-800 rounded-xl flex items-center justify-center border border-white/5">
            <OrcaLogo className="w-8 h-8 text-white" animated={false} />
          </div>
          
          <div className="flex flex-col gap-1">
            <h3 className="text-sm font-semibold text-white">Install Orca</h3>
            
            {isIOS ? (
              <div className="text-xs text-white/70 leading-relaxed space-y-2">
                <p>Pasang di layar utama untuk pengalaman tanpa batas.</p>
                <div className="flex items-center gap-2 bg-white/5 p-2 rounded-lg">
                  <span className="flex items-center gap-1">Ketuk <Share className="w-3 h-3 inline text-blue-400" /></span>
                  <span className="text-white/30">&rarr;</span>
                  <span className="flex items-center gap-1"><PlusSquare className="w-3 h-3 inline text-white" /> Tambah ke Layar Utama</span>
                </div>
              </div>
            ) : (
              <>
                <p className="text-xs text-white/70 leading-relaxed">
                  Pasang aplikasi ini untuk akses lebih cepat dan pengalaman layar penuh (0ms latency).
                </p>
                <button
                  onClick={() => {
                    promptInstall();
                    setShow(false);
                  }}
                  className="mt-2 bg-white text-black text-xs font-semibold px-4 py-2 rounded-full hover:bg-zinc-200 transition-colors self-start active:scale-95"
                >
                  Install Sekarang
                </button>
              </>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
