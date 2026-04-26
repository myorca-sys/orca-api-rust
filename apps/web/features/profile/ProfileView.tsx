"use client";

import { useMemo, useState } from "react";
import { useCollection } from "@/core/hooks/use-collection";
import { useWatchHistory } from "@/core/hooks/use-watch-history";
import { useMounted } from "@/core/hooks/use-mounted";
import { 
  LogOut, ChevronRight, Crown, Shield, FileText, 
  Copy, Mail, Hash, RefreshCw, Bell, Users, Settings, 
  MessageCircle, Activity, Share2
} from "lucide-react";
import { authClient } from "@/core/lib/auth-client";
import { AuthModal } from "@/ui/overlays/AuthModal";
import Link from "next/link";

export default function ProfileView() {
  const mounted = useMounted();
  const [isAuthModalOpen, setIsAuthModalOpen] = useState(false);
  const { data: session, isPending } = authClient.useSession();
  const { items: watchlist } = useCollection(session?.user?.id);
  const { history } = useWatchHistory();
  
  const [isUpdating, setIsUpdating] = useState(false);

  const stats = useMemo(() => {
    const completed = watchlist.filter((w) => w.status === "completed").length;
    const totalEps = history.length + watchlist.reduce((a, c) => a + (c.progress || 0), 0);
    const days = ((totalEps * 24) / 60 / 24).toFixed(1);
    return { completed, totalEps, days };
  }, [watchlist, history]);

  const handlePwaUpdate = async () => {
    setIsUpdating(true);
    if (typeof window !== 'undefined' && 'serviceWorker' in navigator) {
      try {
        const registrations = await navigator.serviceWorker.getRegistrations();
        for (let registration of registrations) {
          await registration.unregister();
        }
        setTimeout(() => {
          window.location.reload();
        }, 1000);
      } catch (e) {
        setTimeout(() => {
          window.location.reload();
        }, 1000);
      }
    } else {
      setTimeout(() => {
        window.location.reload();
      }, 1000);
    }
  };

  if (!mounted) return null;

  return (
    <div className="min-h-screen bg-black pb-32 pt-6 px-4 md:px-8 max-w-3xl mx-auto space-y-6">
      
      {/* Header Profile Section */}
      <section className="flex flex-col items-center justify-center pt-4 pb-6 border-b border-white/10 relative">
        <div className="relative mb-4 group">
          <div className="w-24 h-24 md:w-28 md:h-28 rounded-full overflow-hidden border-2 border-white/20 shadow-2xl relative z-10 bg-[#1c1c1e]">
            <img 
              src={session?.user?.image || "https://api.dicebear.com/7.x/notionists/svg?seed=OrcaUser"} 
              alt="avatar" 
              className="w-full h-full object-cover" 
              loading="lazy" 
            />
          </div>
          {session?.user && (
            <div className="absolute -bottom-2 -right-2 bg-[#0A84FF] text-white p-1.5 rounded-full border-2 border-black z-20">
              <Crown className="w-4 h-4" />
            </div>
          )}
        </div>

        {session?.user ? (
          <div className="text-center space-y-1">
            <h2 className="text-2xl font-black text-white tracking-tight">
              {session.user.name || "Orca User"}
            </h2>
            <p className="text-sm font-medium text-white/60">@{session.user.email?.split('@')[0]}</p>
            
            <div className="flex items-center justify-center gap-4 pt-3 mt-2">
              <div className="text-center cursor-pointer hover:bg-white/5 px-4 py-1.5 rounded-xl transition-colors">
                <p className="text-lg font-black text-white">0</p>
                <p className="text-[10px] text-white/50 font-bold uppercase tracking-wider">Pengikut</p>
              </div>
              <div className="w-[1px] h-8 bg-white/10"></div>
              <div className="text-center cursor-pointer hover:bg-white/5 px-4 py-1.5 rounded-xl transition-colors">
                <p className="text-lg font-black text-white">0</p>
                <p className="text-[10px] text-white/50 font-bold uppercase tracking-wider">Mengikuti</p>
              </div>
              <div className="w-[1px] h-8 bg-white/10"></div>
              <div className="text-center cursor-pointer hover:bg-white/5 px-4 py-1.5 rounded-xl transition-colors">
                <p className="text-lg font-black text-white">{stats.completed}</p>
                <p className="text-[10px] text-white/50 font-bold uppercase tracking-wider">Tamat</p>
              </div>
            </div>
          </div>
        ) : (
          <div className="text-center py-2">
            <h2 className="text-2xl font-black text-white mb-2">Guest Mode</h2>
            <p className="text-sm text-white/50 mb-4 max-w-xs mx-auto">Masuk untuk melacak riwayat tontonan, mengelola koleksi, dan berinteraksi dengan komunitas.</p>
            <button 
              onClick={() => setIsAuthModalOpen(true)}
              className="flex items-center justify-center gap-2 bg-white hover:bg-white/90 text-black px-6 py-2.5 rounded-full font-bold text-sm transition-transform active:scale-95 mx-auto"
            >
              <svg viewBox="0 0 24 24" width="18" height="18" xmlns="http://www.w3.org/2000/svg">
                <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" />
                <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" />
                <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" />
                <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" />
              </svg>
              Lanjutkan dengan Google
            </button>
          </div>
        )}
      </section>

      {/* Social / Action Buttons */}
      {session?.user && (
        <section className="grid grid-cols-2 gap-3 anim-fade">
          <Link href="/notifications" className="flex flex-col items-center justify-center p-4 bg-[#1c1c1e] hover:bg-[#2c2c2e] rounded-2xl border border-white/5 transition-colors group">
            <Bell className="w-6 h-6 text-white mb-2 group-hover:text-[#0A84FF] transition-colors" />
            <span className="text-xs font-bold text-white/80">Notifikasi</span>
          </Link>
          <div className="flex flex-col items-center justify-center p-4 bg-[#1c1c1e] hover:bg-[#2c2c2e] rounded-2xl border border-white/5 transition-colors cursor-pointer group" onClick={() => alert("Fitur Teman segera hadir!")}>
            <Users className="w-6 h-6 text-white mb-2 group-hover:text-[#32D74B] transition-colors" />
            <span className="text-xs font-bold text-white/80">Teman</span>
          </div>
        </section>
      )}

      {/* Watch Stats */}
      <section className="bg-[#1c1c1e] rounded-[24px] p-5 border border-white/5 anim-fade">
        <h3 className="text-[13px] font-black text-white/50 uppercase tracking-widest mb-4 flex items-center gap-2">
          <Activity className="w-4 h-4" />
          Aktivitas Menonton
        </h3>
        <div className="grid grid-cols-3 gap-2 divide-x divide-white/10">
          <div className="text-center">
            <p className="text-2xl font-black text-white tabular-nums">{stats.totalEps}</p>
            <p className="text-[10px] text-white/40 font-bold uppercase tracking-wider mt-1">Eps Ditonton</p>
          </div>
          <div className="text-center">
            <p className="text-2xl font-black text-[#FF9F0A] tabular-nums">{stats.days}</p>
            <p className="text-[10px] text-white/40 font-bold uppercase tracking-wider mt-1">Hari Dihabiskan</p>
          </div>
          <div className="text-center">
            <p className="text-2xl font-black text-[#32D74B] tabular-nums">{history.length}</p>
            <p className="text-[10px] text-white/40 font-bold uppercase tracking-wider mt-1">Sedang Aktif</p>
          </div>
        </div>
      </section>

      {/* Menu / Links */}
      <section className="space-y-3 anim-fade">
        <h3 className="text-[13px] font-black text-white/50 uppercase tracking-widest mb-3 flex items-center gap-2 ml-1 mt-6">
          <Settings className="w-4 h-4" />
          Sistem & Pengaturan
        </h3>
        
        <div className="bg-[#1c1c1e] rounded-[24px] border border-white/5 overflow-hidden flex flex-col">
          <Link href="/premium" className="flex items-center justify-between p-4 md:p-5 hover:bg-white/5 transition-colors border-b border-white/5">
            <div className="flex items-center gap-3">
              <div className="w-9 h-9 rounded-full flex items-center justify-center bg-[#FF9F0A]/10">
                <Crown className="w-4 h-4 text-[#FF9F0A]" />
              </div>
              <div>
                <p className="font-bold text-[14px] text-white">Orca Premium</p>
                <p className="text-[11px] text-white/40">Dukung kreator & hilangkan batasan</p>
              </div>
            </div>
            <ChevronRight className="w-5 h-5 text-white/20" />
          </Link>

          <button 
            onClick={handlePwaUpdate}
            disabled={isUpdating}
            className="w-full flex items-center justify-between p-4 md:p-5 hover:bg-white/5 transition-colors border-b border-white/5 text-left disabled:opacity-50"
          >
            <div className="flex items-center gap-3">
              <div className="w-9 h-9 rounded-full flex items-center justify-center bg-[#0A84FF]/10">
                <RefreshCw className={`w-4 h-4 text-[#0A84FF] ${isUpdating ? 'animate-spin' : ''}`} />
              </div>
              <div>
                <p className="font-bold text-[14px] text-white">
                  {isUpdating ? 'Membersihkan Cache PWA...' : 'Cek Pembaruan (PWA)'}
                </p>
                <p className="text-[11px] text-white/40">Perbaiki error loading & sinkronkan web</p>
              </div>
            </div>
            {!isUpdating && <ChevronRight className="w-5 h-5 text-white/20" />}
          </button>

          <Link href="/tos" className="flex items-center justify-between p-4 md:p-5 hover:bg-white/5 transition-colors border-b border-white/5">
            <div className="flex items-center gap-3">
              <div className="w-9 h-9 rounded-full flex items-center justify-center bg-white/5">
                <FileText className="w-4 h-4 text-white" />
              </div>
              <span className="font-bold text-[14px] text-white">Ketentuan Layanan</span>
            </div>
            <ChevronRight className="w-5 h-5 text-white/20" />
          </Link>

          <Link href="/privacy" className="flex items-center justify-between p-4 md:p-5 hover:bg-white/5 transition-colors">
            <div className="flex items-center gap-3">
              <div className="w-9 h-9 rounded-full flex items-center justify-center bg-white/5">
                <Shield className="w-4 h-4 text-white" />
              </div>
              <span className="font-bold text-[14px] text-white">Kebijakan Privasi</span>
            </div>
            <ChevronRight className="w-5 h-5 text-white/20" />
          </Link>
        </div>
      </section>

      {/* Danger Zone */}
      <section className="pt-4 anim-fade">
        <div className="bg-red-500/10 rounded-[24px] border border-red-500/20 overflow-hidden flex flex-col">
          {session?.user && (
            <button 
              onClick={() => authClient.signOut()} 
              className="w-full flex items-center gap-3 p-4 md:p-5 hover:bg-red-500/20 transition-colors border-b border-red-500/10 text-left"
            >
              <div className="w-9 h-9 rounded-full flex items-center justify-center bg-red-500/20">
                <LogOut className="w-4 h-4 text-[#FF453A]" />
              </div>
              <span className="font-bold text-[14px] text-[#FF453A]">Keluar Akun</span>
            </button>
          )}
          
          <button 
            onClick={() => { if(confirm("Hapus semua riwayat dan koleksi secara permanen?")) { localStorage.clear(); window.location.reload(); } }} 
            className="w-full flex items-center gap-3 p-4 md:p-5 hover:bg-red-500/20 transition-colors text-left"
          >
            <div className="w-9 h-9 rounded-full flex items-center justify-center bg-red-500/20">
              <Shield className="w-4 h-4 text-[#FF453A]" />
            </div>
            <div>
              <p className="font-bold text-[14px] text-[#FF453A]">Hapus Cache Lokal</p>
              <p className="text-[11px] text-[#FF453A]/60">Reset total data perangkat ini</p>
            </div>
          </button>
        </div>
      </section>

      <div className="text-center space-y-1 pt-6 pb-4">
        <p className="text-white/20 text-[10px] font-black tracking-widest uppercase">Orca v3.0.0 (Social Ready)</p>
        <p className="text-white/10 text-[9px] font-bold">Didesain untuk efisiensi maksimal </p>
      </div>
      
      <AuthModal isOpen={isAuthModalOpen} onClose={() => setIsAuthModalOpen(false)} />
    </div>
  );
}
