import { useState, useEffect, useMemo } from "react";

const API = "https://jonyyyyyyyu-anime-scraper-api.hf.space";

interface AnimeRow {
  anilistId: number;
  title: string;
  genres: string[] | string | null;
  status: string;
  year: number;
  cover: string;
  episode_count: number;
  tg_count: number;
  providerId: string | null;
}

interface EpisodeRow {
  id: number;
  episodeNumber: number;
  providerId: string;
  episodeUrl: string;
}

export default function App() {
  const [auth, setAuth] = useState(false);
  const [password, setPassword] = useState("");
  const [activeTab, setActiveTab] = useState("insights"); 
  
  const [logs, setLogs] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);
  
  const [stats, setStats] = useState<any>(null);
  const [ingestionStats, setIngestionStats] = useState<any>(null);
  const [cacheStats, setCacheStats] = useState<any>(null);
  const [ingestTasks, setIngestTasks] = useState<any[]>([]);

  // DB States
  const [dbData, setDbData] = useState<AnimeRow[]>([]);
  const [search, setSearch] = useState("");
  const [currentPage, setCurrentPage] = useState(1);
  const ITEMS_PER_PAGE = 50;

  // Modal States
  const [selectedAnime, setSelectedAnime] = useState<AnimeRow | null>(null);
  const [episodes, setEpisodes] = useState<EpisodeRow[]>([]);
  const [epLoading, setEpLoading] = useState(false);
  const [diagnostics, setDiagnostics] = useState<Record<number, any>>({});

  useEffect(() => {
    const savedAuth = localStorage.getItem("orcaSysAuth");
    const savedKey = localStorage.getItem("orcaSysKey");
    if (savedAuth === "true" && savedKey) {
      setPassword(savedKey);
      setAuth(true);
    }
  }, []);

  const addLog = (msg: string) => {
    setLogs((prev) => [`[${new Date().toLocaleTimeString()}] ${msg}`, ...prev].slice(0, 50));
  };

  const fetchData = () => {
    const key = localStorage.getItem("orcaSysKey") || password;
    const headers = { 'x-admin-key': key };

    fetch(`${API}/api/v2/admin/stats`, { headers })
      .then(res => res.ok ? res.json() : null)
      .then(data => {
        if (data?.success) {
          setStats({ total_anime: data.total_anime, total_episodes: data.total_episodes });
          setIngestionStats({ ingested: data.ingested_episodes || 0, pending: data.pending_episodes || 0 });
        }
      }).catch(console.error);

    fetch(`${API}/api/v2/admin/cache-stats`, { headers })
      .then(async res => {
        if (res.ok) setCacheStats(await res.json());
        else if (res.status === 401) setCacheStats({ error: "Invalid Admin Key / Unauthorized" });
      }).catch(console.error);

    fetch(`${API}/api/v2/admin/ingest-stats`, { headers })
      .then(res => res.ok ? res.json() : null)
      .then(data => {
        if (data?.success) setIngestTasks(data.active_tasks || []);
      }).catch(console.error);

    fetch(`${API}/api/v2/admin/database`, { headers })
      .then(res => res.ok ? res.json() : null)
      .then(data => {
        if (data?.success) setDbData(data.data);
      }).catch(console.error);
  };

  useEffect(() => {
    if (!auth) return;
    fetchData();
    const interval = setInterval(fetchData, 8000);
    return () => clearInterval(interval);
  }, [auth]);

  const handleLogin = (e: React.FormEvent) => {
    e.preventDefault();
    if (password === "26cd52813fbce8e25ccecea02540dd0d642b462f9f4cd1cb") {
      setAuth(true);
      localStorage.setItem("orcaSysAuth", "true");
      localStorage.setItem("orcaSysKey", password);
    } else {
      alert("❌ Akses Ditolak: Passcode tidak valid.");
      setPassword("");
    }
  };

  const handleLogout = () => {
    setAuth(false);
    setPassword("");
    localStorage.removeItem("orcaSysAuth");
    localStorage.removeItem("orcaSysKey");
  };

  const handleAction = async (endpoint: string, label: string) => {
    setLoading(true);
    addLog(`Initiating: ${label}...`);
    try {
      const key = localStorage.getItem("orcaSysKey") || password;
      const res = await fetch(`${API}${endpoint}`, { method: "POST", headers: { 'x-admin-key': key } });
      const data = await res.json();
      addLog(data.success ? `Success: ${data.message}` : `Failed: ${data.error || 'Unauthorized'}`);
    } catch (e: any) {
      addLog(`Network Error: ${e.message}`);
    }
    setLoading(false);
    fetchData();
  };

  const fetchAnimeEpisodes = async (anime: AnimeRow) => {
    setSelectedAnime(anime);
    setEpisodes([]);
    setDiagnostics({});
    setEpLoading(true);
    try {
      const key = localStorage.getItem("orcaSysKey") || password;
      const res = await fetch(`${API}/api/v2/admin/anime/${anime.anilistId}/episodes`, { headers: { 'x-admin-key': key } });
      const data = await res.json();
      if (data.success) {
        setEpisodes(data.data);
      } else {
        addLog(`Failed to fetch episodes: ${data.error}`);
      }
    } catch (e: any) {
      console.error(e);
    }
    setEpLoading(false);
  };

  const handleDiagnose = async (ep: EpisodeRow) => {
    setDiagnostics(prev => ({ ...prev, [ep.id]: { loading: true } }));
    try {
      const key = localStorage.getItem("orcaSysKey") || password;
      const res = await fetch(`${API}/api/v2/admin/episode/diagnose`, { 
        method: "POST", 
        headers: { 'x-admin-key': key, 'Content-Type': 'application/json' },
        body: JSON.stringify({ url: ep.episodeUrl })
      });
      const data = await res.json();
      setDiagnostics(prev => ({ ...prev, [ep.id]: { loading: false, result: data } }));
    } catch (e: any) {
      setDiagnostics(prev => ({ ...prev, [ep.id]: { loading: false, result: { success: false, status: "Network Error" } } }));
    }
  };

  const filteredData = useMemo(() => {
    return dbData.filter(item => item.title?.toLowerCase().includes(search.toLowerCase()) || String(item.anilistId).includes(search));
  }, [dbData, search]);

  const paginatedData = useMemo(() => {
    const start = (currentPage - 1) * ITEMS_PER_PAGE;
    return filteredData.slice(start, start + ITEMS_PER_PAGE);
  }, [filteredData, currentPage]);

  const totalPages = Math.ceil(filteredData.length / ITEMS_PER_PAGE);

  if (!auth) {
    return (
      <div className="min-h-[100dvh] bg-black flex flex-col items-center justify-center font-sans text-white p-6 antialiased">
        <div className="w-full max-w-xs space-y-8 animate-in slide-in-from-bottom-8 fade-in duration-700">
          <div className="flex flex-col items-center space-y-4">
             <div className="w-20 h-20 bg-gradient-to-br from-indigo-500 via-purple-500 to-pink-500 rounded-[1.5rem] shadow-[0_10px_40px_-10px_rgba(168,85,247,0.5)] flex items-center justify-center">
               <svg className="w-8 h-8 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
                 <path strokeLinecap="round" strokeLinejoin="round" d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
               </svg>
             </div>
             <div className="text-center">
               <h1 className="text-2xl font-bold tracking-tight">System Restricted</h1>
               <p className="text-sm text-gray-400 mt-1">Provide passcode to access telemetry.</p>
             </div>
          </div>
          <form onSubmit={handleLogin} className="space-y-4">
            <input 
              type="password" 
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="Passcode"
              autoFocus
              className="w-full bg-[#1C1C1E] border border-white/5 rounded-[1.2rem] px-5 py-4 text-center tracking-[0.5em] text-white focus:outline-none focus:ring-2 focus:ring-purple-500 font-mono text-lg transition-all shadow-inner"
            />
            <button type="submit" className="w-full bg-white text-black font-bold py-4 rounded-[1.2rem] hover:bg-gray-200 transition-transform active:scale-95 shadow-[0_5px_20px_-5px_rgba(255,255,255,0.3)]">
              Authenticate
            </button>
          </form>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-[100dvh] bg-black text-white font-sans pb-24 md:pb-0 md:flex antialiased selection:bg-purple-500/30">
      
      {/* Desktop Sidebar */}
      <aside className="hidden md:flex w-[280px] bg-[#1C1C1E]/50 border-r border-white/5 flex-col fixed inset-y-0 z-50 backdrop-blur-2xl">
        <div className="p-8 pb-6 flex flex-col gap-3 border-b border-white/5">
           <div className="w-12 h-12 bg-gradient-to-br from-indigo-500 to-purple-500 rounded-[1rem] flex items-center justify-center shadow-lg">
             <svg className="w-6 h-6 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
               <path strokeLinecap="round" strokeLinejoin="round" d="M19.428 15.428a2 2 0 00-1.022-.547l-2.387-.477a6 6 0 00-3.86.517l-.318.158a6 6 0 01-3.86.517L6.05 15.21a2 2 0 00-1.806.547M8 4h8l-1 1v5.172a2 2 0 00.586 1.414l5 5c1.26 1.26.367 3.414-1.415 3.414H4.828c-1.782 0-2.674-2.154-1.414-3.414l5-5A2 2 0 009 10.172V5L8 4z" />
             </svg>
           </div>
           <div>
             <h2 className="font-bold text-xl tracking-tight leading-none">Telemetry</h2>
             <span className="text-[10px] text-green-400 font-bold tracking-widest uppercase flex items-center gap-1.5 mt-1.5">
               <span className="w-1.5 h-1.5 rounded-full bg-green-400 animate-pulse" /> All Systems Nominal
             </span>
           </div>
        </div>
        
        <nav className="p-4 flex-1 space-y-1.5 overflow-y-auto">
          <SidebarItem active={activeTab === 'insights'} onClick={() => setActiveTab('insights')} icon="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" label="Insights" />
          <SidebarItem active={activeTab === 'database'} onClick={() => setActiveTab('database')} icon="M4 7v10c0 2.21 3.582 4 8 4s8-1.79 8-4V7M4 7c0 2.21 3.582 4 8 4s8-1.79 8-4M4 7c0-2.21 3.582-4 8-4s8 1.79 8 4m0 5c0 2.21-3.582 4-8 4s-8-1.79-8-4" label="Database" />
          <SidebarItem active={activeTab === 'cache'} onClick={() => setActiveTab('cache')} icon="M13 10V3L4 14h7v7l9-11h-7z" label="Edge Cache" />
          <SidebarItem active={activeTab === 'ecosystem'} onClick={() => setActiveTab('ecosystem')} icon="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" label="Ecosystem" />
        </nav>
      </aside>

      {/* Main Container */}
      <main className="flex-1 md:ml-[280px] min-h-[100dvh] bg-black max-w-5xl md:mx-auto relative">
        <div className="p-4 md:p-8 pt-10 pb-8 space-y-8 animate-in fade-in duration-500">
          
          <header className="mb-6 px-2">
            <h1 className="text-3xl md:text-4xl font-bold tracking-tight capitalize">{activeTab}</h1>
          </header>

          {/* --- TAB: INSIGHTS --- */}
          {activeTab === 'insights' && (
            <div className="space-y-8">
              <section>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                  <MetricBox label="Indexed Anime" value={stats?.total_anime || "--"} color="text-white" />
                  <MetricBox label="Total Episodes" value={stats?.total_episodes || "--"} color="text-indigo-400" />
                  <MetricBox label="Swarm Proxy" value={ingestionStats?.ingested || "--"} color="text-purple-400" />
                  <MetricBox label="Pending Sync" value={ingestionStats?.pending || "--"} color="text-orange-400" />
                </div>
              </section>

              <section className="bg-[#1C1C1E] rounded-[2rem] p-6 border border-white/5 space-y-6">
                <div className="flex items-center justify-between">
                  <h2 className="text-lg font-semibold tracking-tight">Mission Control</h2>
                </div>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <ListButton onClick={() => handleAction('/api/v2/admin/trigger-prefetch', 'Smart Pre-fetch')} title="Execute Smart Pre-fetch" subtitle="Ongoing anime -> Telegram Swarm" icon="M13 10V3L4 14h7v7l9-11h-7z" color="bg-indigo-500" loading={loading} />
                  <ListButton onClick={() => handleAction('/api/v2/admin/mass-sync', 'Mass Sync')} title="Force Mass Synchronization" subtitle="Deep sync for top 100 recent updates" icon="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" color="bg-purple-500" loading={loading} />
                  <ListButton onClick={() => handleAction('/api/v2/admin/sync-missing', 'Retry 0 Eps')} title="Retry Missing Episodes" subtitle="Re-evaluate anime with 0 episodes" icon="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" color="bg-orange-500" loading={loading} />
                  <ListButton onClick={() => {
                    const id = prompt("Target AniList ID:");
                    if(id) handleAction(`/api/v2/anime/${id}/debug-sync`, `Manual Scrape ID ${id}`);
                  }} title="Manual ID Scrape" subtitle="Force sync a specific AniList ID" icon="M15 15l-2 5L9 9l11 4-5 2zm0 0l5 5M7.188 2.239l.777 2.897M5.136 7.965l-2.898-.777M13.95 4.05l-2.122 2.122m-5.657 5.656l-2.12 2.122" color="bg-gray-500" loading={loading} />
                </div>
              </section>

              <section className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <div className="bg-[#1C1C1E] rounded-[2rem] border border-white/5 p-6 h-80 flex flex-col">
                  <h3 className="text-sm font-semibold text-gray-400 uppercase tracking-widest mb-4 flex items-center gap-2">
                    <span className="w-2 h-2 rounded-full bg-purple-500 animate-pulse" /> Active Ingestions
                  </h3>
                  <div className="flex-1 overflow-y-auto space-y-3 pr-2 custom-scrollbar">
                    {ingestTasks.length === 0 ? (
                      <p className="text-sm text-gray-500">No active tasks in Swarm.</p>
                    ) : (
                      ingestTasks.map((t: any, i) => (
                        <div key={i} className="flex flex-col gap-2 cursor-pointer" onClick={() => {
                          const anime = dbData.find(a => String(a.anilistId) === String(t.anilist_id));
                          if(anime) fetchAnimeEpisodes(anime);
                        }}>
                          <div className="flex justify-between items-center text-sm hover:text-purple-400 transition-colors">
                            <span className="font-semibold truncate">ID: {t.anilist_id} <span className="text-gray-500">| Ep {t.episode}</span></span>
                            <span className="text-[10px] text-purple-400 bg-purple-500/10 px-2 py-0.5 rounded font-bold uppercase">{t.progress?.status || 'RUNNING'}</span>
                          </div>
                          {t.progress?.progress && (
                            <div className="h-1.5 bg-black rounded-full overflow-hidden">
                              <div className="h-full bg-purple-500 transition-all duration-300" style={{ width: `${Math.min(100, Math.max(0, parseInt(t.progress.progress)))}%` }} />
                            </div>
                          )}
                        </div>
                      ))
                    )}
                  </div>
                </div>

                <div className="bg-black rounded-[2rem] border border-white/5 p-6 h-80 flex flex-col">
                  <h3 className="text-sm font-semibold text-gray-400 uppercase tracking-widest mb-4 flex items-center gap-2">
                    <span className="w-2 h-2 rounded-full bg-green-500" /> Terminal Feed
                  </h3>
                  <div className="flex-1 overflow-y-auto font-mono text-[11px] text-green-400 leading-relaxed flex flex-col-reverse custom-scrollbar">
                    {logs.length === 0 ? <span className="opacity-50">Awaiting telemetry...</span> : logs.map((log, i) => <div key={i} className="pb-1 opacity-80">{log}</div>)}
                  </div>
                </div>
              </section>
            </div>
          )}

          {/* --- TAB: DATABASE --- */}
          {activeTab === 'database' && (
            <div className="space-y-6">
              <div className="bg-[#1C1C1E] rounded-[2rem] border border-white/5 p-4 flex flex-col md:flex-row gap-3">
                <div className="flex-1 relative">
                  <svg className="w-5 h-5 absolute left-4 top-1/2 -translate-y-1/2 text-gray-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
                  </svg>
                  <input 
                    type="text" 
                    placeholder="Search Anime ID or Title..." 
                    value={search}
                    onChange={(e) => { setSearch(e.target.value); setCurrentPage(1); }}
                    className="w-full bg-black/50 border border-white/5 rounded-2xl pl-11 pr-4 py-3.5 text-sm focus:outline-none focus:ring-2 focus:ring-white/20 transition-all"
                  />
                </div>
              </div>

              <div className="bg-[#1C1C1E] rounded-[2rem] border border-white/5 overflow-hidden">
                <div className="max-h-[65vh] overflow-y-auto custom-scrollbar">
                  <div className="divide-y divide-white/5">
                    {paginatedData.length === 0 ? (
                      <div className="p-10 text-center text-gray-500 text-sm">No records matched your criteria.</div>
                    ) : (
                      paginatedData.map((item) => (
                        <div key={item.anilistId} onClick={() => fetchAnimeEpisodes(item)} className="flex items-center justify-between p-4 hover:bg-white/5 transition-colors cursor-pointer active:bg-white/10">
                          <div className="flex items-center gap-4 min-w-0">
                            <img src={item.cover} alt="" className="w-12 h-16 rounded-xl object-cover bg-black shrink-0 border border-white/5 shadow-sm" loading="lazy" />
                            <div className="min-w-0">
                              <h3 className="font-semibold text-[15px] truncate pr-4 text-white">{item.title}</h3>
                              <div className="flex items-center gap-2 mt-1">
                                <span className="text-[11px] text-gray-400 font-mono">ID: {item.anilistId}</span>
                                {item.providerId && <span className="text-[9px] font-bold uppercase tracking-wider text-indigo-400 bg-indigo-500/10 px-1.5 py-0.5 rounded">{item.providerId}</span>}
                              </div>
                            </div>
                          </div>
                          <div className="text-right shrink-0 ml-4">
                            {item.episode_count > 0 ? (
                              <div className="flex flex-col items-end">
                                <span className="text-xl font-bold text-white leading-none">{item.episode_count}</span>
                                <span className="text-[10px] text-gray-500 uppercase tracking-widest mt-1">Episodes</span>
                                {item.tg_count > 0 && <span className="text-[9px] text-purple-400 bg-purple-500/10 px-1.5 py-0.5 rounded font-bold uppercase tracking-wider mt-1">{item.tg_count} TG Proxy</span>}
                              </div>
                            ) : (
                              <span className="text-[11px] font-bold text-orange-400 bg-orange-500/10 px-3 py-1 rounded-lg uppercase tracking-wider">Empty</span>
                            )}
                          </div>
                        </div>
                      ))
                    )}
                  </div>
                </div>
                
                {/* Pagination */}
                {totalPages > 1 && (
                  <div className="bg-black/30 border-t border-white/5 p-4 flex justify-between items-center">
                    <button disabled={currentPage === 1} onClick={() => setCurrentPage(p => p - 1)} className="px-5 py-2.5 bg-[#1C1C1E] border border-white/5 hover:bg-white/10 rounded-xl text-sm font-semibold disabled:opacity-30 transition-all">Previous</button>
                    <span className="text-sm font-medium text-gray-400">{currentPage} of {totalPages}</span>
                    <button disabled={currentPage === totalPages} onClick={() => setCurrentPage(p => p + 1)} className="px-5 py-2.5 bg-[#1C1C1E] border border-white/5 hover:bg-white/10 rounded-xl text-sm font-semibold disabled:opacity-30 transition-all">Next</button>
                  </div>
                )}
              </div>
            </div>
          )}

          {/* --- TAB: EDGE CACHE --- */}
          {activeTab === 'cache' && (
            <div className="space-y-6">
              {!cacheStats ? (
                <div className="bg-[#1C1C1E] rounded-[2rem] border border-white/5 p-10 text-center text-gray-500">
                  <p>Awaiting cache telemetry from Edge node...</p>
                </div>
              ) : cacheStats.error ? (
                <div className="bg-red-500/10 rounded-[2rem] border border-red-500/20 p-10 text-center text-red-500">
                  <p className="font-bold mb-1">Access Denied</p>
                  <p className="text-sm">{cacheStats.error}. Please check your passcode and try logging in again.</p>
                  <button onClick={handleLogout} className="mt-4 px-4 py-2 bg-red-500 text-white rounded-xl text-xs font-bold hover:bg-red-600 transition-colors">
                    Re-Authenticate
                  </button>
                </div>
              ) : (
                <div className="space-y-6">
                  <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                    <DataWidget title="L0 Instance LRU" value={`${cacheStats.l0_entries} / ${cacheStats.l0_max}`} caption="~0ms Latency" color="border-yellow-500/30" />
                    <DataWidget title="L1 Global Edge Redis" value="Distributed" caption="~1-5ms Latency via Upstash" color="border-red-500/30" />
                    <DataWidget title="L2 Serverless DB" value={cacheStats.l2_pg_entries ?? 'Err'} caption="~10-30ms Cold Store" color="border-blue-500/30" />
                  </div>

                  <div className="bg-gradient-to-br from-[#1C1C1E] to-black rounded-[2rem] border border-white/5 p-6 md:p-8 flex flex-col md:flex-row items-center justify-between gap-6">
                    <div>
                      <h2 className="text-xl font-bold tracking-tight mb-2 text-white">Coalesced L3 Engine</h2>
                      <p className="text-sm text-gray-400 max-w-md leading-relaxed">Active in-flight scraper tasks. Duplicate requests to the same episode concurrently are coalesced to prevent redundant scraping, utilizing Stale-While-Revalidate pattern.</p>
                    </div>
                    <div className="text-6xl md:text-7xl font-black text-transparent bg-clip-text bg-gradient-to-b from-purple-400 to-indigo-600">
                      {cacheStats.inflight_scrapes}
                    </div>
                  </div>

                  <div className="bg-[#1C1C1E] rounded-[2rem] border border-white/5 p-6 md:p-8">
                    <h2 className="text-lg font-semibold tracking-tight mb-6">Provider Circuit Breakers</h2>
                    <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-4">
                      {Object.entries(cacheStats.circuit_breakers || {}).map(([provider, state]: [string, any]) => (
                        <div key={provider} className="bg-black/50 border border-white/5 p-4 rounded-2xl flex flex-col gap-2">
                          <span className="font-semibold text-sm capitalize text-white">{provider}</span>
                          <span className={`w-fit px-2.5 py-1 rounded text-[10px] font-black uppercase tracking-widest
                            ${state === 'closed' ? 'bg-green-500/10 text-green-500' : state === 'open' ? 'bg-red-500/10 text-red-500' : 'bg-orange-500/10 text-orange-500'}`}>
                            {state === 'closed' ? 'HEALTHY' : state === 'open' ? 'BLOCKED' : state}
                          </span>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              )}
            </div>
          )}

          {/* --- TAB: ECOSYSTEM --- */}
          {activeTab === 'ecosystem' && (
            <div className="space-y-6">
              <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
                <DataWidget title="Web Pages" value="11" caption="Next.js App Router" color="border-white/10" />
                <DataWidget title="Web Components" value="31" caption="React Server & Client" color="border-white/10" />
                <DataWidget title="API Endpoints" value="15+" caption="FastAPI Routes" color="border-white/10" />
              </div>

              <div className="bg-[#1C1C1E] rounded-[2rem] border border-white/5 overflow-hidden">
                <div className="p-6 border-b border-white/5">
                  <h2 className="text-lg font-semibold tracking-tight">Full Production Stack</h2>
                </div>
                <div className="divide-y divide-white/5">
                  <StackRow title="Frontend Web" desc="Next.js 15, TailwindCSS v4, React 19" />
                  <StackRow title="Backend API" desc="FastAPI (Python 3.10), Uvicorn, SQLAlchemy" />
                  <StackRow title="Database (L2)" desc="Neon Postgres (Serverless DB, connection pooler)" />
                  <StackRow title="Global Cache (L1)" desc="Upstash Redis & QStash (for background cron)" />
                  <StackRow title="Deployment" desc="Cloudflare Pages (Frontend) & Hugging Face Spaces (API)" />
                  <StackRow title="Video Storage Proxy" desc="Telegram Swarm Proxy via Cloudflare Workers" />
                  <StackRow title="Providers" desc="Oploverz, Samehadaku, Kuronime, Otakudesu" />
                </div>
              </div>
            </div>
          )}

        </div>

        {/* EPISODE DIAGNOSTIC MODAL */}
        {selectedAnime && (
          <div className="fixed inset-0 z-[100] flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm animate-in fade-in duration-200">
            <div className="bg-[#1C1C1E] border border-white/10 rounded-[2rem] w-full max-w-2xl max-h-[85vh] flex flex-col shadow-2xl overflow-hidden animate-in zoom-in-95 duration-300">
              
              <div className="p-6 border-b border-white/5 flex gap-4 items-center bg-black/20">
                <img src={selectedAnime.cover} alt="" className="w-16 h-24 object-cover rounded-xl shadow-lg border border-white/10" />
                <div className="flex-1 min-w-0">
                  <h2 className="text-xl font-bold text-white truncate">{selectedAnime.title}</h2>
                  <p className="text-sm text-gray-400 font-mono mt-1">ID: {selectedAnime.anilistId} • Episodes: {selectedAnime.episode_count}</p>
                  <button 
                    onClick={() => {
                      if(confirm("Force Re-Ingest anime ini?")) {
                        handleAction(`/api/v2/anime/${selectedAnime.anilistId}/debug-sync`, "Force Re-Ingest");
                      }
                    }}
                    className="mt-3 bg-white/10 hover:bg-white/20 text-white px-3 py-1.5 rounded-lg text-xs font-bold transition-colors"
                  >
                    Force Re-Ingest All
                  </button>
                </div>
                <button onClick={() => setSelectedAnime(null)} className="p-2 bg-white/5 hover:bg-red-500/20 hover:text-red-500 rounded-full transition-colors self-start">
                  <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
                  </svg>
                </button>
              </div>

              <div className="flex-1 overflow-y-auto p-2 bg-black/10 custom-scrollbar">
                {epLoading ? (
                  <div className="flex justify-center items-center h-40">
                    <div className="w-8 h-8 border-4 border-purple-500 border-t-transparent rounded-full animate-spin"></div>
                  </div>
                ) : episodes.length === 0 ? (
                  <div className="text-center p-10 text-gray-500 text-sm">Tidak ada episode tersimpan di database.</div>
                ) : (
                  <div className="space-y-2 p-2">
                    {episodes.map(ep => {
                      const diag = diagnostics[ep.id];
                      const isTg = ep.episodeUrl.includes('tg-proxy') || ep.episodeUrl.includes('workers.dev');
                      return (
                        <div key={ep.id} className="bg-[#1C1C1E] border border-white/5 p-4 rounded-2xl flex flex-col sm:flex-row sm:items-center gap-4 hover:bg-white/5 transition-colors">
                          <div className="w-12 h-12 rounded-xl bg-black flex flex-col items-center justify-center shrink-0 border border-white/5">
                            <span className="text-[10px] text-gray-500 font-bold uppercase">EP</span>
                            <span className="text-lg font-black text-white leading-none">{ep.episodeNumber}</span>
                          </div>
                          
                          <div className="flex-1 min-w-0">
                            <div className="flex items-center gap-2 mb-1">
                              <span className="text-xs font-bold uppercase tracking-wider text-indigo-400 bg-indigo-500/10 px-2 py-0.5 rounded">{ep.providerId}</span>
                              {isTg && <span className="text-[9px] font-bold uppercase tracking-wider text-purple-400 bg-purple-500/10 px-2 py-0.5 rounded">TG PROXY</span>}
                            </div>
                            <div className="text-[11px] text-gray-500 font-mono truncate w-full" title={ep.episodeUrl}>
                              {ep.episodeUrl}
                            </div>

                            {diag?.result && (
                              <div className={`mt-2 text-xs font-bold px-2 py-1 rounded w-fit ${diag.result.healthy ? 'bg-green-500/10 text-green-500' : 'bg-red-500/10 text-red-500'}`}>
                                {diag.result.healthy ? '✅ Healthy' : '❌ Error'} • {diag.result.status}
                              </div>
                            )}
                          </div>
                          
                          <div className="shrink-0 flex gap-2">
                            {isTg && (
                              <button 
                                onClick={() => handleDiagnose(ep)}
                                disabled={diag?.loading}
                                className="bg-white/5 hover:bg-white/10 text-white border border-white/10 px-4 py-2 rounded-xl text-xs font-bold disabled:opacity-50 transition-colors w-full sm:w-auto"
                              >
                                {diag?.loading ? 'Scanning...' : 'Diagnose'}
                              </button>
                            )}
                          </div>
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>
            </div>
          </div>
        )}

      </main>

      {/* Mobile Bottom Dock */}
      <nav className="md:hidden fixed bottom-6 inset-x-6 z-40">
         <div className="bg-[#1C1C1E]/80 backdrop-blur-3xl border border-white/10 rounded-3xl p-2 flex justify-between shadow-[0_20px_40px_-10px_rgba(0,0,0,0.8)]">
           <DockItem active={activeTab === 'insights'} onClick={() => setActiveTab('insights')} icon="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" label="Insights" />
           <DockItem active={activeTab === 'database'} onClick={() => setActiveTab('database')} icon="M4 7v10c0 2.21 3.582 4 8 4s8-1.79 8-4V7M4 7c0 2.21 3.582 4 8 4s8-1.79 8-4M4 7c0-2.21 3.582-4 8-4s8 1.79 8 4m0 5c0 2.21-3.582 4-8 4s-8-1.79-8-4" label="Database" />
           <DockItem active={activeTab === 'cache'} onClick={() => setActiveTab('cache')} icon="M13 10V3L4 14h7v7l9-11h-7z" label="Edge" />
           <DockItem active={activeTab === 'ecosystem'} onClick={() => setActiveTab('ecosystem')} icon="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" label="Stack" />
         </div>
      </nav>
      <style>{`
        .custom-scrollbar::-webkit-scrollbar { width: 6px; }
        .custom-scrollbar::-webkit-scrollbar-track { background: transparent; }
        .custom-scrollbar::-webkit-scrollbar-thumb { background: rgba(255,255,255,0.1); border-radius: 10px; }
      `}</style>
    </div>
  );
}

function SidebarItem({ active, onClick, icon, label }: any) {
  return (
    <button onClick={onClick} className={`w-full flex items-center gap-3 px-4 py-3 rounded-xl text-sm font-semibold transition-all duration-200 ${active ? 'bg-white/10 text-white shadow-sm' : 'text-gray-400 hover:text-white hover:bg-white/5'}`}>
      <svg className={`w-5 h-5 ${active ? 'text-white' : 'text-gray-500'}`} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={active?2.5:2}>
        <path strokeLinecap="round" strokeLinejoin="round" d={icon} />
      </svg>
      {label}
    </button>
  );
}

function DockItem({ active, onClick, icon, label }: any) {
  return (
    <button onClick={onClick} className={`flex flex-col items-center justify-center w-16 h-14 rounded-2xl transition-all duration-200 ${active ? 'bg-white/15' : 'hover:bg-white/5'}`}>
      <svg className={`w-6 h-6 mb-1 ${active ? 'text-white' : 'text-gray-400'}`} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={active?2.5:2}>
        <path strokeLinecap="round" strokeLinejoin="round" d={icon} />
      </svg>
      <span className={`text-[9px] tracking-wide ${active ? 'text-white font-bold' : 'text-gray-400 font-medium'}`}>{label}</span>
    </button>
  );
}

function MetricBox({ label, value, color }: any) {
  return (
    <div className={`bg-[#1C1C1E] border border-white/5 rounded-[2rem] p-5 flex flex-col justify-end min-h-[120px]`}>
      <div className={`text-4xl font-black tracking-tight mb-2 ${color}`}>{value}</div>
      <div className="text-[11px] uppercase tracking-widest font-semibold text-gray-500">{label}</div>
    </div>
  );
}

function ListButton({ onClick, title, subtitle, icon, color, loading }: any) {
  return (
    <button onClick={onClick} disabled={loading} className="w-full flex items-center gap-4 bg-black/50 border border-white/5 hover:border-white/20 p-4 rounded-2xl transition-all disabled:opacity-50 active:scale-[0.98] text-left group">
      <div className={`w-12 h-12 rounded-xl flex items-center justify-center text-white shadow-lg ${color}`}>
        <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
          <path strokeLinecap="round" strokeLinejoin="round" d={icon} />
        </svg>
      </div>
      <div className="flex-1 min-w-0">
        <h3 className="font-semibold text-white truncate">{title}</h3>
        <p className="text-[11px] text-gray-400 truncate mt-0.5">{subtitle}</p>
      </div>
      <svg className="w-5 h-5 text-gray-600 group-hover:text-white transition-colors" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" />
      </svg>
    </button>
  );
}

function DataWidget({ title, value, caption, color }: any) {
  return (
    <div className={`bg-[#1C1C1E] border-t-2 ${color} rounded-[2rem] p-6 border-x border-b border-white/5`}>
      <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-widest mb-4">{title}</h3>
      <p className="text-3xl font-black text-white mb-2 tracking-tight">{value}</p>
      <p className="text-sm text-gray-400">{caption}</p>
    </div>
  );
}

function StackRow({ title, desc }: any) {
  return (
    <div className="p-6 flex flex-col md:flex-row md:items-center gap-2 md:gap-6 hover:bg-white/5 transition-colors">
      <h3 className="w-48 font-semibold text-white text-sm">{title}</h3>
      <p className="flex-1 text-sm text-gray-400">{desc}</p>
    </div>
  );
}
