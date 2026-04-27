"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { IconHome, IconCollection, IconUser, IconBell } from "@/ui/icons";
import { useMounted } from "@/core/hooks/use-mounted";
import { useKonami } from "@/core/hooks/use-konami";
import { useViewTransition } from "@/core/hooks/use-view-transition";
import { SnakeGame } from "@/ui/games/SnakeGame";
import { useState } from "react";
import { authClient } from "@/core/lib/auth-client";

const TABS = [
  { id: "/", label: "Beranda", icon: IconHome },
  { id: "/collection", label: "Koleksi", icon: IconCollection },
  { id: "/notifications", label: "Notifikasi", icon: IconBell },
  { id: "/profile", label: "Profil", icon: IconUser },
];

export function Navigation({ children }: { children: React.ReactNode }) {
  const pathname = usePathname() || "/";
  const router = useRouter();
  const navigate = useViewTransition();
  const mounted = useMounted();
  const [snakeActive, setSnakeActive] = useState(false);
  const { data: session } = authClient.useSession();

  useKonami(() => setSnakeActive(true));

  // Determine if current route is exactly one of the main tabs
  const isMainTab = TABS.some(t => pathname === t.id);

  return (
    <div className="w-full min-h-[100dvh] bg-[#121212] text-white flex flex-col relative select-none antialiased min-w-0 transition-colors duration-500">
      {/* Main content */}
      <div className="flex-1 w-full min-h-[100dvh] relative flex flex-col min-w-0">
        <main className={`flex-1 w-full min-w-0 ${mounted && isMainTab ? 'pb-[100px]' : 'pb-0'}`}>
          {children}
        </main>

        {/* Global Bottom Nav - Render when mounted and on a main tab */}
        {mounted && isMainTab && (
          <div className="fixed bottom-0 left-0 right-0 h-[72px] z-[90] flex flex-col justify-end items-center pb-2 pointer-events-auto" aria-hidden="true" title="Bottom Navigation Area">
            <nav className="relative w-[calc(100%-32px)] max-w-[320px] z-[100] bg-[#1c1c1e] border border-[#2c2c2e] shadow-[0_8px_32px_rgba(0,0,0,0.8)] rounded-[32px] overflow-hidden" aria-hidden="false">
              <div className="flex justify-around items-center px-2 h-[60px]">
                {TABS.map((t) => {
                  const active = pathname === t.id || (t.id !== "/" && pathname.startsWith(t.id));
                  const Icon = t.icon;
                  
                  const isProfileTab = t.id === "/profile";
                  const isLoggedIn = !!session?.user;
                  const avatarUrl = session?.user?.image || (isLoggedIn ? `https://api.dicebear.com/7.x/notionists/svg?seed=${session?.user?.id || 'orca'}&backgroundColor=0a84ff,bf5af2` : null);

                  return (
                    <Link key={t.id} href={t.id} prefetch={true} className="flex flex-col items-center justify-center h-full aspect-square group focus:outline-none">
                      <div className={`transition-all duration-300 ${active ? "scale-110" : "scale-100 opacity-60 group-hover:opacity-100 group-hover:scale-105"}`}>
                        {isProfileTab && avatarUrl ? (
                          <img src={avatarUrl} alt="Profile" className={`w-[22px] h-[22px] rounded-full object-cover border-2 ${active ? 'border-white' : 'border-transparent'}`} />
                        ) : (
                          <Icon className="w-[22px] h-[22px] text-white" filled={active} />
                        )}
                      </div>
                      <span className={`text-[9px] mt-1 transition-colors ${active ? "text-white font-bold" : "text-white/40 font-medium group-hover:text-white/70"}`}>{t.label}</span>
                    </Link>
                  );
                })}
              </div>
            </nav>
          </div>
        )}
      </div>

      {snakeActive && <SnakeGame onClose={() => setSnakeActive(false)} />}
    </div>
  );
}
