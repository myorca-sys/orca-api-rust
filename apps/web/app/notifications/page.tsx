"use client";

import { authClient } from "@/core/lib/auth-client";
import { redirect } from "next/navigation";
import { IconBell } from "@/ui/icons";
import { useMounted } from "@/core/hooks/use-mounted";
import { useState, useEffect } from "react";
import Link from "next/link";
import { API } from "@/core/lib/api";
import useSWR from "swr";

export const runtime = "edge";

const fetcher = (url: string) => fetch(url).then(res => res.json());

export default function NotificationsPage() {
  const mounted = useMounted();
  const { data: session, isPending } = authClient.useSession();
  const [pushStatus, setPushStatus] = useState<NotificationPermission>("default");

  const { data, isLoading } = useSWR(session?.user ? `${API}/api/v2/social/notifications` : null, fetcher, {
    refreshInterval: 60000, // Cek tiap menit
  });

  useEffect(() => {
    if (typeof window !== "undefined" && "Notification" in window) {
      setPushStatus(Notification.permission);
    }
  }, []);

  const requestPushPermission = async () => {
    if (typeof window !== "undefined" && "Notification" in window) {
      try {
        const permission = await Notification.requestPermission();
        setPushStatus(permission);
        if (permission === "granted") {
          alert("Notifikasi PWA berhasil diaktifkan! Anda akan menerima update episode baru.");
          new Notification("Orca Anime", {
            body: "Ini adalah tes notifikasi. Sistem PWA sudah siap!",
            icon: "/icon512_maskable.png"
          });
        }
      } catch (error) {
        console.error("Gagal mengaktifkan notifikasi", error);
      }
    } else {
      alert("Browser Anda tidak mendukung Web Push Notification.");
    }
  };

  if (!mounted || isPending) return null;

  if (!session?.user) {
    redirect("/?login=true");
  }

  const notifications = data?.data || [];

  return (
    <div className="w-full min-h-screen bg-black text-white p-5 md:px-8 pt-8 pb-32 max-w-4xl mx-auto">
      <div className="flex flex-col md:flex-row md:items-center justify-between mb-8 gap-4">
        <h1 className="text-2xl md:text-3xl font-black tracking-tight">Notifikasi</h1>
        
        <div className="flex gap-2 items-center">
          {pushStatus !== "granted" && (
            <button 
              onClick={requestPushPermission}
              className="text-[12px] font-bold text-[#FF9F0A] hover:text-white transition-colors bg-[#FF9F0A]/10 px-4 py-2 rounded-full"
            >
              Aktifkan Notifikasi PWA
            </button>
          )}
          <button className="text-[13px] font-bold text-[#0A84FF] hover:text-white transition-colors bg-[#0A84FF]/10 px-4 py-2 rounded-full whitespace-nowrap">
            Tandai semua dibaca
          </button>
        </div>
      </div>

      <div className="space-y-4">
        {isLoading ? (
          <div className="text-white/40 text-center py-10 font-bold">Memuat notifikasi terbaru...</div>
        ) : notifications.length === 0 ? (
          <div className="text-white/40 text-center py-10 font-bold">Belum ada notifikasi.</div>
        ) : (
          notifications.map((notif: any) => (
            <Link 
              key={notif.id} 
              href={notif.link || "#"}
              className={`block relative overflow-hidden p-5 rounded-[24px] border transition-all duration-300 group cursor-pointer ${
                notif.isUnread 
                  ? "bg-[#1c1c1e] border-white/10 hover:bg-[#2c2c2e]" 
                  : "bg-transparent border-transparent hover:bg-white/5"
              }`}
            >
              {notif.isUnread && (
                <div className="absolute top-5 left-5 w-2 h-2 rounded-full bg-[#0A84FF] shadow-[0_0_8px_#0A84FF]" />
              )}
              
              <div className={`flex gap-4 ${notif.isUnread ? 'pl-5' : ''}`}>
                <div className="w-12 h-12 rounded-full bg-white/5 flex items-center justify-center shrink-0 border border-white/5 group-hover:scale-105 transition-transform duration-300">
                  <IconBell className={`w-5 h-5 ${notif.isUnread ? 'text-[#0A84FF]' : 'text-white/40'}`} />
                </div>
                
                <div className="flex-1 min-w-0">
                  <h3 className={`text-[15px] leading-tight mb-1 ${notif.isUnread ? 'font-bold text-white' : 'font-medium text-white/70'}`}>
                    {notif.title}
                  </h3>
                  <p className="text-[#8e8e93] text-[13px] line-clamp-2 leading-relaxed">
                    {notif.message}
                  </p>
                  <p className="text-white/30 text-[11px] font-bold tracking-wider uppercase mt-3">
                    {notif.time}
                  </p>
                </div>
              </div>
            </Link>
          ))
        )}
      </div>
    </div>
  );
}
