// ui/icons/index.tsx — Inline SVG icons. Zero library dependency.
// Each icon is ~200 bytes vs lucide-react's 40KB+ bundle impact.

import { memo } from "react";
import { Home, Compass, Library, User, Info, Bell } from "lucide-react";

type P = { className?: string };

export const IconBell = memo(({ className = "w-5 h-5", filled = false }: P & { filled?: boolean }) => (
  <Bell 
    className={className} 
    strokeWidth={1.5} 
    fill={filled ? "currentColor" : "none"} 
  />
));
IconBell.displayName = "IconBell";

export const IconPlay = memo(({ className = "w-5 h-5" }: P) => (
  <svg className={className} fill="currentColor" viewBox="0 0 24 24"><path d="M8 5v14l11-7z" /></svg>
));
IconPlay.displayName = "IconPlay";

export const IconPause = memo(({ className = "w-5 h-5" }: P) => (
  <svg className={className} fill="currentColor" viewBox="0 0 24 24"><path d="M6 19h4V5H6v14zm8-14v14h4V5h-4z" /></svg>
));
IconPause.displayName = "IconPause";

export const IconBack = memo(({ className = "w-5 h-5" }: P) => (
  <svg className={className} fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" d="M15.75 19.5L8.25 12l7.5-7.5" /></svg>
));
IconBack.displayName = "IconBack";

export const IconInfo = memo(({ className = "w-5 h-5" }: P) => (
  <Info className={className} strokeWidth={2} />
));
IconInfo.displayName = "IconInfo";

export const IconSearch = memo(({ className = "w-5 h-5" }: P) => (
  <svg className={className} fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" d="M21 21l-5.197-5.197m0 0A7.5 7.5 0 105.196 5.196a7.5 7.5 0 0010.607 10.607z" /></svg>
));
IconSearch.displayName = "IconSearch";

export const IconHome = memo(({ className = "w-5 h-5", filled = false }: P & { filled?: boolean }) => (
  <Home 
    className={className} 
    strokeWidth={1.5} 
    fill={filled ? "currentColor" : "none"} 
  />
));
IconHome.displayName = "IconHome";

export const IconExplore = memo(({ className = "w-5 h-5", filled = false }: P & { filled?: boolean }) => (
  <Compass 
    className={className} 
    strokeWidth={1.5} 
    fill={filled ? "currentColor" : "none"} 
  />
));
IconExplore.displayName = "IconExplore";

export const IconCollection = memo(({ className = "w-5 h-5", filled = false }: P & { filled?: boolean }) => (
  <Library 
    className={className} 
    strokeWidth={1.5} 
    fill={filled ? "currentColor" : "none"} 
  />
));
IconCollection.displayName = "IconCollection";

export const IconUser = memo(({ className = "w-5 h-5", filled = false }: P & { filled?: boolean }) => (
  <User 
    className={className} 
    strokeWidth={1.5} 
    fill={filled ? "currentColor" : "none"} 
  />
));
IconUser.displayName = "IconUser";

export const IconStar = memo(({ className = "w-4 h-4" }: P) => (
  <svg className={className} fill="currentColor" viewBox="0 0 24 24"><path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z" /></svg>
));
IconStar.displayName = "IconStar";

export const IconBookmark = memo(({ className = "w-5 h-5", filled = false }: P & { filled?: boolean }) => (
  <svg className={className} fill={filled ? "currentColor" : "none"} stroke="currentColor" strokeWidth={1.5} viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" d="M17.593 3.322c1.1.128 1.907 1.077 1.907 2.185V21L12 17.25 4.5 21V5.507c0-1.108.806-2.057 1.907-2.185a48.507 48.507 0 0111.186 0z" /></svg>
));
IconBookmark.displayName = "IconBookmark";

export const IconShare = memo(({ className = "w-5 h-5" }: P) => (
  <svg className={className} fill="none" stroke="currentColor" strokeWidth={1.5} viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" d="M7.217 10.907a2.25 2.25 0 100 2.186m0-2.186c.18.324.283.696.283 1.093s-.103.77-.283 1.093m0-2.186l9.566-5.314m-9.566 7.5l9.566 5.314m0 0a2.25 2.25 0 103.935 2.186 2.25 2.25 0 00-3.935-2.186zm0-12.814a2.25 2.25 0 103.933-2.185 2.25 2.25 0 00-3.933 2.185z" /></svg>
));
IconShare.displayName = "IconShare";

export const IconCheck = memo(({ className = "w-4 h-4" }: P) => (
  <svg className={className} fill="none" stroke="currentColor" strokeWidth={2.5} viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" d="M4.5 12.75l6 6 9-13.5" /></svg>
));
IconCheck.displayName = "IconCheck";

export const IconClose = memo(({ className = "w-4 h-4" }: P) => (
  <svg className={className} fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" /></svg>
));
IconClose.displayName = "IconClose";

export const IconSettings = memo(({ className = "w-5 h-5" }: P) => (
  <svg className={className} fill="none" stroke="currentColor" strokeWidth={1.5} viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" d="M9.594 3.94c.09-.542.56-.94 1.11-.94h2.593c.55 0 1.02.398 1.11.94l.213 1.281c.063.374.313.686.645.87.074.04.147.083.22.127.325.196.72.257 1.075.124l1.217-.456a1.125 1.125 0 011.37.49l1.296 2.247a1.125 1.125 0 01-.26 1.431l-1.003.827c-.293.241-.438.613-.43.992a6.759 6.759 0 010 .255c-.007.378.138.75.43.99l1.004.828c.424.35.534.955.26 1.43l-1.298 2.247a1.125 1.125 0 01-1.369.491l-1.217-.456c-.355-.133-.75-.072-1.076.124a6.57 6.57 0 01-.22.128c-.331.183-.581.495-.644.869l-.213 1.28c-.09.543-.56.941-1.11.941h-2.594c-.55 0-1.02-.398-1.11-.94l-.213-1.281c-.062-.374-.312-.686-.644-.87a6.52 6.52 0 01-.22-.127c-.325-.196-.72-.257-1.076-.124l-1.217.456a1.125 1.125 0 01-1.369-.49l-1.297-2.247a1.125 1.125 0 01.26-1.431l1.004-.827c.292-.24.437-.613.43-.992a6.932 6.932 0 010-.255c.007-.378-.138-.75-.43-.99l-1.004-.828a1.125 1.125 0 01-.26-1.43l1.297-2.247a1.125 1.125 0 011.37-.491l1.216.456c.356.133.751.072 1.076-.124.072-.044.146-.087.22-.128.332-.183.582-.495.644-.869l.214-1.281z" /><path strokeLinecap="round" strokeLinejoin="round" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" /></svg>
));
IconSettings.displayName = "IconSettings";

export const IconSort = memo(({ className = "w-4 h-4" }: P) => (
  <svg className={className} fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" d="M3 7.5L7.5 3m0 0L12 7.5M7.5 3v13.5m13.5 0L16.5 21m0 0L12 16.5m4.5 4.5V7.5" /></svg>
));
IconSort.displayName = "IconSort";

export const IconTrash = memo(({ className = "w-4 h-4" }: P) => (
  <svg className={className} fill="none" stroke="currentColor" strokeWidth={1.5} viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" d="M14.74 9l-.346 9m-4.788 0L9.26 9m9.968-3.21c.342.052.682.107 1.022.166m-1.022-.165L18.16 19.673a2.25 2.25 0 01-2.244 2.077H8.084a2.25 2.25 0 01-2.244-2.077L4.772 5.79m14.456 0a48.108 48.108 0 00-3.478-.397m-12 .562c.34-.059.68-.114 1.022-.165m0 0a48.11 48.11 0 013.478-.397m7.5 0v-.916c0-1.18-.91-2.164-2.09-2.201a51.964 51.964 0 00-3.32 0c-1.18.037-2.09 1.022-2.09 2.201v.916m7.5 0a48.667 48.667 0 00-7.5 0" /></svg>
));
IconTrash.displayName = "IconTrash";

export const IconClock = memo(({ className = "w-4 h-4" }: P) => (
  <svg className={className} fill="none" stroke="currentColor" strokeWidth={1.5} viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" d="M12 6v6h4.5m4.5 0a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>
));
IconClock.displayName = "IconClock";

export const IconFullscreen = memo(({ className = "w-5 h-5" }: P) => (
  <svg className={className} fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" d="M3.75 3.75v4.5m0-4.5h4.5m-4.5 0L9 9M3.75 20.25v-4.5m0 4.5h4.5m-4.5 0L9 15M20.25 3.75h-4.5m4.5 0v4.5m0-4.5L15 9m5.25 11.25h-4.5m4.5 0v-4.5m0 4.5L15 15" /></svg>
));
IconFullscreen.displayName = "IconFullscreen";

export const IconVolume = memo(({ className = "w-5 h-5", muted = false }: P & { muted?: boolean }) => muted ? (
  <svg className={className} fill="none" stroke="currentColor" strokeWidth={1.5} viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" d="M17.25 9.75L19.5 12m0 0l2.25 2.25M19.5 12l2.25-2.25M19.5 12l-2.25 2.25m-10.5-6l4.72-4.72a.75.75 0 011.28.53v15.88a.75.75 0 01-1.28.53l-4.72-4.72H4.51c-.88 0-1.704-.507-1.938-1.354A9.01 9.01 0 012.25 12c0-.83.112-1.633.322-2.396C2.806 8.756 3.63 8.25 4.51 8.25h2.24z" /></svg>
) : (
  <svg className={className} fill="none" stroke="currentColor" strokeWidth={1.5} viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" d="M19.114 5.636a9 9 0 010 12.728M16.463 8.288a5.25 5.25 0 010 7.424M6.75 8.25l4.72-4.72a.75.75 0 011.28.53v15.88a.75.75 0 01-1.28.53l-4.72-4.72H4.51c-.88 0-1.704-.507-1.938-1.354A9.01 9.01 0 012.25 12c0-.83.112-1.633.322-2.396C2.806 8.756 3.63 8.25 4.51 8.25h2.24z" /></svg>
));
IconVolume.displayName = "IconVolume";
export * from './OrcaLogo';
