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

export default function App() {
  const [auth, setAuth] = useState(false);
  const [password, setPassword] = useState("");
  const [activeTab, setActiveTab] = useState("dashboard");
  
  const [targetId, setTargetId] = useState("");
  const [logs, setLogs] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);
  
  const [stats, setStats] = useState<any>(null);
  const [ingestionStats, setIngestionStats] = useState<any>(null);
  const [cacheStats, setCacheStats] = useState<any>(null);
  const [ingestTasks, setIngestTasks] = useState<any[]>([]);

  useEffect(() => {
    const savedAuth = localStorage.getItem("adminAuth");
    const savedKey = localStorage.getItem("adminKey");
    if (savedAuth === "true" && savedKey) {
      setPassword(savedKey);
      setAuth(true);
    }
  }, []);
  
  const [dbData, setDbData] = useState<AnimeRow[]>([]);
  const [filterGenre, setFilterGenre] = useState<string>("All");
  const [filterEps, setFilterEps] = useState<string>("All");
  const [search, setSearch] = useState("");

  const addLog = (msg: string) => {
    setLogs((prev) => {
      const newLogs = [`[${new Date().toLocaleTimeString()}] ${msg}`, ...prev].slice(0, 50);
      localStorage.setItem("adminLogs", JSON.stringify(newLogs));
      return newLogs;
    });
  };

  useEffect(() => {
    const savedLogs = localStorage.getItem("adminLogs");
    if (savedLogs) {
      try {
        setLogs(JSON.parse(savedLogs));
      } catch(e) {}
    }
  }, []);

  const fetchData = async () => {
    const key = localStorage.getItem("adminKey") || password;
    try {
      const resStats = await fetch(`${API}/api/v2/admin/stats`);
      if (resStats.ok) {
        const dataStats = await resStats.json();
        if (dataStats.success) {
          setStats({ total_anime: dataStats.total_anime, total_episodes: dataStats.total_episodes });
          setIngestionStats({
             ingested: dataStats.ingested_episodes || 0,
             pending: dataStats.pending_episodes || 0
          });
        }
      }

      const resDb = await fetch(`${API}/api/v2/admin/database`);
      if (resDb.ok) {
        const dataDb = await resDb.json();
        if (dataDb.success) setDbData(dataDb.data);
      }
      
      const resCache = await fetch(`${API}/api/v2/admin/cache-stats`, { 
        headers: { 'x-admin-key': key }
      });
      if (resCache.ok) {
        const dataCache = await resCache.json();
        setCacheStats(dataCache);
      }

      const resTasks = await fetch(`${API}/api/v2/admin/ingest-stats`, { 
        headers: { 'x-admin-key': key }
      });
      if (resTasks.ok) {
        const dataTasks = await resTasks.json();
        if (dataTasks.success) {
          setIngestTasks(dataTasks.active_tasks || []);
        }
      }
      
    } catch (e) {
      console.error("Failed to fetch data", e);
    }
  };

  useEffect(() => {
    if (!auth) return;
    
    fetchData();
    const interval = setInterval(() => {
      fetchData();
    }, 5000);
    
    return () => clearInterval(interval);
  }, [auth]);

  const handleLogin = (e: React.FormEvent) => {
    e.preventDefault();
    if (password.length > 0) {
      setAuth(true);
      localStorage.setItem("adminAuth", "true");
      localStorage.setItem("adminKey", password);
    }
  };

  const handleLogout = () => {
    setAuth(false);
    setPassword("");
    localStorage.removeItem("adminAuth");
    localStorage.removeItem("adminKey");
  };

  const handlePrefetch = async () => {
    setLoading(true);
    addLog(`🚀 Memicu Smart Pre-fetch (Ongoing Anime) di Background...`);
    try {
      const key = localStorage.getItem("adminKey") || password;
      const res = await fetch(`${API}/api/v2/admin/trigger-prefetch`, { 
        method: "POST",
        headers: { 'x-admin-key': key }
      });
      const data = await res.json();
      addLog(data.success ? `✅ Sukses: ${data.message}` : `❌ Gagal: ${data.error || 'Unauthorized'}`);
    } catch (e: any) {
      addLog(`❌ Error: ${e.message}`);
    }
    setLoading(false);
  };

  const handleSync = async (idToSync: string) => {
    if (!idToSync) return;
    setLoading(true);
    addLog(`🔍 Mengekstrak ID Anilist: ${idToSync}...`);
    
    try {
      const res = await fetch(`${API}/api/v2/anime/${idToSync}/debug-sync`);
      const data = await res.json();
      if (data.success) {
        addLog(`✅ Sukses [ID ${idToSync}]: ${data.result?.synced || 0} episode disinkronkan.`);
      } else {
        addLog(`❌ Gagal [ID ${idToSync}]: ${data.error || "Unknown Error"}`);
      }
    } catch (e: any) {
      addLog(`❌ Error koneksi: ${e.message}`);
    }
    
    setLoading(false);
    fetchData();
  };

  const handleMassSync = async () => {
    setLoading(true);
    addLog(`🚀 Mengirim 100 Anime Terbaru ke Sinkronisasi Massal...`);
    try {
      const key = localStorage.getItem("adminKey") || password;
      const res = await fetch(`${API}/api/v2/admin/mass-sync`, { 
        method: "POST",
        headers: { 'x-admin-key': key }
      });
      const data = await res.json();
      addLog(data.success ? `✅ Sukses: ${data.message}` : `❌ Gagal: ${data.error}`);
    } catch (e: any) {
      addLog(`❌ Error: ${e.message}`);
    }
    setLoading(false);
  };

  const handleSyncMissing = async () => {
    setLoading(true);
    addLog(`🔎 Memasukkan semua anime "0 Episode" ke antrean...`);
    try {
      const key = localStorage.getItem("adminKey") || password;
      const res = await fetch(`${API}/api/v2/admin/sync-missing`, { 
        method: "POST",
        headers: { 'x-admin-key': key }
      });
      const data = await res.json();
      addLog(data.success ? `✅ ${data.message}` : `❌ Gagal: ${data.error}`);
    } catch (e: any) {
      addLog(`❌ Error: ${e.message}`);
    }
    setLoading(false);
    fetchData();
  };

  const allGenres = useMemo(() => {
    const genres = new Set<string>();
    dbData.forEach(item => {
      if (Array.isArray(item.genres)) {
        item.genres.forEach(g => genres.add(g));
      }
    });
    return Array.from(genres).sort();
  }, [dbData]);

  const filteredData = useMemo(() => {
    return dbData.filter(item => {
      const matchSearch = item.title?.toLowerCase().includes(search.toLowerCase()) || String(item.anilistId).includes(search);
      let matchGenre = true;
      if (filterGenre !== "All") {
        matchGenre = Array.isArray(item.genres) ? item.genres.includes(filterGenre) : false;
      }
      let matchEps = true;
      if (filterEps === "Zero") matchEps = item.episode_count === 0;
      if (filterEps === "HasEps") matchEps = item.episode_count > 0;

      return matchSearch && matchGenre && matchEps;
    });
  }, [dbData, search, filterGenre, filterEps]);

  if (!auth) {
    return (
      <div className="min-h-screen bg-[#0a0c10] flex items-center justify-center font-sans">
        <div className="bg-[#1c1c1e] p-8 rounded-2xl border border-white/10 w-full max-w-sm">
          <div className="flex items-center justify-center mb-6">
            <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-[#0a84ff] to-[#30d158] flex items-center justify-center shadow-[0_0_20px_rgba(10,132,255,0.3)]">
               <span className="text-white font-black text-xl">A</span>
            </div>
          </div>
          <h1 className="text-2xl font-black text-white mb-2 text-center">Control Center</h1>
          <p className="text-[#8e8e93] text-sm text-center mb-6">Orca Administration</p>
          <form onSubmit={handleLogin}>
            <input 
              type="password" 
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="Admin API Key..." 
              className="w-full bg-black border border-white/10 rounded-xl px-4 py-3 text-white mb-4 focus:outline-none focus:border-[#0a84ff] font-mono text-sm"
            />
            <button type="submit" className="w-full bg-[#0a84ff] text-white font-bold py-3 rounded-xl hover:bg-blue-600 transition-colors shadow-[0_0_15px_rgba(10,132,255,0.4)]">
              Authenticate
            </button>
          </form>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-[#0a0c10] text-white flex flex-col md:flex-row font-sans">
      
      {/* Sidebar Navigation */}
      <aside className="w-full md:w-64 bg-[#1c1c1e] border-r border-white/10 flex flex-col">
        <div className="p-6 border-b border-white/10 flex items-center gap-3">
           <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-[#0a84ff] to-[#30d158] flex items-center justify-center">
              <span className="text-white font-black text-sm">PRO</span>
           </div>
           <div>
             <h2 className="font-black text-white tracking-tight leading-none">AnimeAdmin</h2>
             <span className="text-[10px] text-[#30d158] uppercase font-bold tracking-widest">System Online</span>
           </div>
        </div>
        
        <nav className="p-4 flex-1 space-y-2">
          <button 
            onClick={() => setActiveTab('dashboard')}
            className={`w-full text-left px-4 py-3 rounded-xl font-bold transition-all flex items-center gap-3 ${activeTab === 'dashboard' ? 'bg-[#0a84ff]/20 text-[#0a84ff]' : 'text-[#8e8e93] hover:bg-white/5 hover:text-white'}`}
          >
            📊 Dashboard
          </button>
          <button 
            onClick={() => setActiveTab('database')}
            className={`w-full text-left px-4 py-3 rounded-xl font-bold transition-all flex items-center gap-3 ${activeTab === 'database' ? 'bg-[#0a84ff]/20 text-[#0a84ff]' : 'text-[#8e8e93] hover:bg-white/5 hover:text-white'}`}
          >
            🗄️ Database Explorer
          </button>
          <button 
            onClick={() => setActiveTab('cache')}
            className={`w-full text-left px-4 py-3 rounded-xl font-bold transition-all flex items-center gap-3 ${activeTab === 'cache' ? 'bg-[#0a84ff]/20 text-[#0a84ff]' : 'text-[#8e8e93] hover:bg-white/5 hover:text-white'}`}
          >
            ⚡ Stream Cache Engine
          </button>
        </nav>

        <div className="p-4 border-t border-white/10">
           <button onClick={handleLogout} className="w-full py-2 text-sm text-[#ff453a] font-bold hover:bg-[#ff453a]/10 rounded-lg transition-colors">
              Disconnect
           </button>
        </div>
      </aside>

      {/* Main Content Area */}
      <main className="flex-1 overflow-y-auto p-4 md:p-8">
        
        {/* --- TAB: DASHBOARD --- */}
        {activeTab === 'dashboard' && (
          <div className="max-w-6xl mx-auto space-y-6">
            <h1 className="text-3xl font-black mb-6 tracking-tight">System Overview</h1>
            
            {/* Stats Grid */}
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
              <div className="bg-[#1c1c1e] border border-white/10 rounded-2xl p-5 relative overflow-hidden">
                <div className="absolute top-0 right-0 p-4 opacity-10 text-4xl">🎬</div>
                <p className="text-[10px] uppercase font-bold text-[#8e8e93] tracking-widest mb-1">Total Anime</p>
                <p className="text-4xl font-black text-white">{stats?.total_anime || 0}</p>
              </div>
              <div className="bg-[#1c1c1e] border border-white/10 rounded-2xl p-5 relative overflow-hidden">
                <div className="absolute top-0 right-0 p-4 opacity-10 text-4xl">📼</div>
                <p className="text-[10px] uppercase font-bold text-[#8e8e93] tracking-widest mb-1">Total Episodes</p>
                <p className="text-4xl font-black text-[#0a84ff]">{stats?.total_episodes || 0}</p>
              </div>
              <div className="bg-[#1c1c1e] border border-white/10 rounded-2xl p-5 relative overflow-hidden">
                <div className="absolute top-0 right-0 p-4 opacity-10 text-4xl">🚀</div>
                <p className="text-[10px] uppercase font-bold text-[#8e8e93] tracking-widest mb-1">Swarm Ingested</p>
                <p className="text-4xl font-black text-[#30d158]">{ingestionStats?.ingested || 0}</p>
              </div>
              <div className="bg-[#1c1c1e] border border-white/10 rounded-2xl p-5 relative overflow-hidden">
                <div className="absolute top-0 right-0 p-4 opacity-10 text-4xl">⏳</div>
                <p className="text-[10px] uppercase font-bold text-[#8e8e93] tracking-widest mb-1">Pending Ingest</p>
                <p className="text-4xl font-black text-[#ff9f0a]">{ingestionStats?.pending || 0}</p>
              </div>
            </div>

            {/* Action Center & Logs */}
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
              <div className="bg-[#1c1c1e] border border-white/10 rounded-2xl p-5 space-y-4">
                <h2 className="text-sm font-bold text-[#8e8e93] uppercase tracking-widest flex items-center gap-2">
                  🛠️ Mission Control
                </h2>
                <button onClick={handlePrefetch} disabled={loading} className="w-full bg-[#0a84ff]/20 hover:bg-[#0a84ff]/30 text-[#0a84ff] font-bold p-3 rounded-xl border border-[#0a84ff]/50 disabled:opacity-50 transition-all text-xs">
                  🚀 Trigger Smart Pre-fetch (Ongoing Anime to Telegram)
                </button>
                <div className="grid grid-cols-2 gap-3">
                  <button onClick={handleMassSync} disabled={loading} className="bg-[#30d158]/20 hover:bg-[#30d158]/30 text-[#30d158] font-bold p-3 rounded-xl border border-[#30d158]/50 disabled:opacity-50 transition-all text-xs">
                    1. Sinkronisasi Massal
                  </button>
                  <button onClick={handleSyncMissing} disabled={loading} className="bg-[#ff453a]/20 hover:bg-[#ff453a]/30 text-[#ff453a] font-bold p-3 rounded-xl border border-[#ff453a]/50 disabled:opacity-50 transition-all text-xs">
                    2. Retry 0 Episode
                  </button>
                </div>
                <div className="flex gap-3">
                  <input
                    type="text"
                    value={targetId}
                    onChange={(e) => setTargetId(e.target.value)}
                    placeholder="Target ID Spesifik (Cth: 182205)"
                    className="flex-1 bg-black border border-white/10 rounded-xl px-4 py-2 text-sm focus:outline-none focus:border-[#0a84ff] text-white"
                  />
                  <button onClick={() => handleSync(targetId)} disabled={loading || !targetId} className="bg-[#0a84ff] hover:bg-blue-600 text-white font-bold px-6 py-2 rounded-xl disabled:opacity-50 text-sm">
                    Scrape Manual
                  </button>
                </div>
              </div>
              
              <div className="bg-[#1c1c1e] border border-white/10 rounded-2xl p-5 h-[240px] flex flex-col shadow-[inset_0_0_20px_rgba(0,0,0,0.5)]">
                <h2 className="text-sm font-bold text-[#8e8e93] uppercase tracking-widest mb-3 flex items-center gap-2">
                  <div className="w-2 h-2 rounded-full bg-[#ff9f0a] animate-pulse" /> Live Ingestion Tasks
                </h2>
                <div className="flex-1 overflow-y-auto font-mono text-[11px] text-white space-y-2">
                  {ingestTasks.length === 0 ? (
                    <span className="text-white/30">Tidak ada task ingestion yang aktif...</span>
                  ) : (
                    ingestTasks.map((t: any, i) => (
                      <div key={i} className="flex flex-col bg-black border border-white/10 p-2 rounded-lg">
                        <div className="flex justify-between items-center mb-1">
                          <span className="font-bold text-[#0a84ff]">ID: {t.anilist_id} | Ep: {t.episode}</span>
                          <span className={`px-2 py-0.5 rounded text-[9px] font-black tracking-widest uppercase ${
                            t.progress?.status === 'processing' ? 'bg-[#ff9f0a]/20 text-[#ff9f0a]' : 
                            t.progress === 'DONE' ? 'bg-[#30d158]/20 text-[#30d158]' : 
                            'bg-[#8e8e93]/20 text-[#8e8e93]'
                          }`}>
                            {t.progress?.status || (typeof t.progress === 'string' ? t.progress : 'UNKNOWN')}
                          </span>
                        </div>
                        {t.progress?.progress && (
                          <div className="w-full bg-white/10 rounded-full h-1.5 mt-1">
                            <div className="bg-[#0a84ff] h-1.5 rounded-full" style={{ width: `${Math.min(100, Math.max(0, parseInt(t.progress.progress)))}%` }}></div>
                          </div>
                        )}
                        {t.progress?.progress && <span className="text-[9px] text-[#8e8e93] mt-1 text-right">{t.progress.progress}%</span>}
                      </div>
                    ))
                  )}
                </div>
              </div>

              <div className="bg-black border border-white/10 rounded-2xl p-5 h-[240px] flex flex-col shadow-[inset_0_0_20px_rgba(0,0,0,0.5)]">
                <h2 className="text-sm font-bold text-[#8e8e93] uppercase tracking-widest mb-3 flex items-center gap-2">
                  <div className="w-2 h-2 rounded-full bg-[#30d158] animate-pulse" /> Terminal Logs
                </h2>
                <div className="flex-1 overflow-y-auto font-mono text-[11px] text-[#30d158] space-y-1.5 flex flex-col-reverse">
                  {logs.length === 0 ? <span className="text-white/30">System waiting for commands...</span> : logs.map((log, i) => <div key={i}>{log}</div>)}
                </div>
              </div>
            </div>
          </div>
        )}

        {/* --- TAB: DATABASE --- */}
        {activeTab === 'database' && (
          <div className="flex flex-col h-full space-y-4">
            <h1 className="text-3xl font-black tracking-tight">Database Explorer</h1>
            
            <div className="bg-[#1c1c1e] border border-white/10 rounded-2xl flex flex-col flex-1 min-h-[600px]">
              {/* Filter Bar */}
              <div className="p-4 border-b border-white/10 bg-white/5 flex flex-wrap gap-4 items-center rounded-t-2xl">
                <div className="flex-1 min-w-[200px]">
                  <input 
                    type="text" 
                    placeholder="Cari judul anime atau ID..." 
                    value={search}
                    onChange={(e) => setSearch(e.target.value)}
                    className="w-full bg-black border border-white/10 rounded-lg px-4 py-2 text-sm text-white focus:outline-none focus:border-[#0a84ff]"
                  />
                </div>
                
                <div className="flex items-center gap-2">
                  <span className="text-xs text-[#8e8e93] font-bold uppercase">Genre:</span>
                  <select value={filterGenre} onChange={(e) => setFilterGenre(e.target.value)} className="bg-black border border-white/10 rounded-lg px-3 py-2 text-sm text-white focus:outline-none">
                    <option value="All">Semua Genre</option>
                    {allGenres.map(g => <option key={g} value={g}>{g}</option>)}
                  </select>
                </div>

                <div className="flex items-center gap-2">
                  <span className="text-xs text-[#8e8e93] font-bold uppercase">Eps:</span>
                  <select value={filterEps} onChange={(e) => setFilterEps(e.target.value)} className="bg-black border border-white/10 rounded-lg px-3 py-2 text-sm text-white focus:outline-none">
                    <option value="All">Semua Anime</option>
                    <option value="Zero">0 Episode (Kosong)</option>
                    <option value="HasEps">Ada Episode</option>
                  </select>
                </div>
                
                <div className="text-xs text-[#8e8e93] font-bold px-2 bg-black py-1.5 rounded-lg border border-white/10">
                  {filteredData.length} Hasil
                </div>
              </div>

              {/* Table */}
              <div className="flex-1 overflow-auto rounded-b-2xl">
                <table className="w-full text-left text-sm border-collapse">
                  <thead className="bg-black/90 text-[#8e8e93] sticky top-0 z-10 backdrop-blur-xl shadow-md">
                    <tr>
                      <th className="p-4 border-b border-white/10 font-bold uppercase text-[10px] tracking-widest">Cover</th>
                      <th className="p-4 border-b border-white/10 font-bold uppercase text-[10px] tracking-widest w-[40%]">Judul & Meta</th>
                      <th className="p-4 border-b border-white/10 font-bold uppercase text-[10px] tracking-widest">Status / Thn</th>
                      <th className="p-4 border-b border-white/10 font-bold uppercase text-[10px] tracking-widest">Storage</th>
                      <th className="p-4 border-b border-white/10 font-bold uppercase text-[10px] tracking-widest text-right">Aksi</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-white/5 bg-[#1c1c1e]">
                    {filteredData.map((item) => (
                      <tr key={item.anilistId} className="hover:bg-white/5 transition-colors group">
                        <td className="p-4">
                          <div className="w-12 h-16 rounded overflow-hidden bg-black border border-white/10 shadow-sm">
                            {item.cover ? <img src={item.cover} alt="" className="w-full h-full object-cover" /> : <div className="w-full h-full bg-white/5" />}
                          </div>
                        </td>
                        <td className="p-4">
                          <div className="font-bold text-white mb-1.5 line-clamp-1" title={item.title}>{item.title}</div>
                          <div className="flex items-center gap-2 mb-2">
                            <span className="bg-black border border-white/10 px-2 py-0.5 rounded text-[10px] font-mono text-[#8e8e93]">ID: {item.anilistId}</span>
                            {item.providerId && <span className="bg-[#0a84ff]/10 text-[#0a84ff] border border-[#0a84ff]/20 px-2 py-0.5 rounded text-[10px] uppercase font-bold">{item.providerId}</span>}
                          </div>
                          <div className="flex flex-wrap gap-1.5">
                            {Array.isArray(item.genres) && item.genres.slice(0, 4).map(g => (
                              <span key={g} className="text-[9px] text-[#8e8e93] bg-black border border-white/10 px-1.5 py-0.5 rounded">{g}</span>
                            ))}
                          </div>
                        </td>
                        <td className="p-4 align-top pt-5">
                          <span className={`px-2.5 py-1 rounded-full text-[10px] font-bold ${item.status === 'RELEASING' ? 'bg-[#30d158]/20 text-[#30d158]' : 'bg-white/10 text-[#8e8e93]'}`}>
                            {item.status}
                          </span>
                          <div className="text-xs text-[#8e8e93] font-bold mt-2.5 pl-1">{item.year}</div>
                        </td>
                        <td className="p-4 align-top pt-4">
                          {item.episode_count > 0 ? (
                            <div className="flex flex-col gap-2">
                              <div className="flex items-center gap-2">
                                <span className="text-lg font-black text-white">{item.episode_count}</span>
                                <span className="text-[10px] text-[#8e8e93] uppercase font-bold tracking-wider">Eps DB</span>
                              </div>
                              {item.tg_count > 0 && (
                                <div className="flex items-center gap-2 bg-[#0a84ff]/10 px-2 py-1 rounded-md border border-[#0a84ff]/20 w-fit">
                                  <span className="text-sm font-black text-[#0a84ff]">{item.tg_count}</span>
                                  <span className="text-[9px] text-[#0a84ff] uppercase font-bold tracking-wider">TG Proxy</span>
                                </div>
                              )}
                            </div>
                          ) : (
                            <div className="flex items-center gap-2 bg-[#ff453a]/10 px-2 py-1.5 rounded-md border border-[#ff453a]/20 w-fit mt-1">
                              <span className="text-sm font-black text-[#ff453a]">{item.episode_count}</span>
                              <span className="text-[10px] text-[#ff453a] uppercase font-bold animate-pulse">Missing</span>
                            </div>
                          )}
                        </td>
                        <td className="p-4 text-right align-top pt-5">
                          <button 
                            onClick={() => {
                              setTargetId(String(item.anilistId));
                              setActiveTab('dashboard');
                            }}
                            className="opacity-0 group-hover:opacity-100 transition-opacity px-4 py-2 bg-white text-black text-[10px] font-bold rounded-lg shadow-lg hover:scale-105"
                          >
                            Scrape Manual
                          </button>
                        </td>
                      </tr>
                    ))}
                    {filteredData.length === 0 && (
                      <tr>
                        <td colSpan={5} className="p-12 text-center text-[#8e8e93] font-medium text-sm">Tidak ada anime yang cocok dengan filter.</td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        )}

        {/* --- TAB: CACHE --- */}
        {activeTab === 'cache' && (
          <div className="max-w-5xl mx-auto space-y-6">
            <div className="flex items-center justify-between">
               <h1 className="text-3xl font-black tracking-tight flex items-center gap-3">
                 <span className="text-[#ffcc00]">⚡</span> Stream Cache Engine
               </h1>
               <button onClick={fetchData} className="px-4 py-2 bg-white/10 hover:bg-white/20 rounded-xl text-sm font-bold transition-colors">
                 Refresh Stats
               </button>
            </div>
            
            {!cacheStats ? (
              <div className="p-8 text-center text-[#8e8e93] bg-[#1c1c1e] rounded-2xl border border-white/10">Memuat metrik cache...</div>
            ) : (
              <div className="space-y-6">
                
                {/* Latency & Hit Rate Simulation Grid */}
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                  <div className="bg-[#1c1c1e] border border-[#ffcc00]/30 rounded-2xl p-5 relative overflow-hidden shadow-[inset_0_0_20px_rgba(255,204,0,0.05)]">
                    <p className="text-[10px] uppercase font-bold text-[#ffcc00] tracking-widest mb-1 flex items-center gap-1">
                      <span className="w-1.5 h-1.5 rounded-full bg-[#ffcc00] animate-pulse"></span> L0 (In-Memory LRU)
                    </p>
                    <p className="text-4xl font-black text-white mb-2">{cacheStats.l0_entries} <span className="text-xl text-[#8e8e93] font-medium">/ {cacheStats.l0_max}</span></p>
                    <p className="text-xs text-[#8e8e93]">Latensi: <strong className="text-white">~0ms</strong> (Per-instance)</p>
                  </div>
                  
                  <div className="bg-[#1c1c1e] border border-[#ff453a]/30 rounded-2xl p-5 relative overflow-hidden shadow-[inset_0_0_20px_rgba(255,69,58,0.05)]">
                    <p className="text-[10px] uppercase font-bold text-[#ff453a] tracking-widest mb-1 flex items-center gap-1">
                      <span className="w-1.5 h-1.5 rounded-full bg-[#ff453a]"></span> L1 (Upstash Redis)
                    </p>
                    <p className="text-4xl font-black text-white mb-2">Distributed</p>
                    <p className="text-xs text-[#8e8e93]">Latensi: <strong className="text-white">~1-5ms</strong> (Global Edge)</p>
                  </div>

                  <div className="bg-[#1c1c1e] border border-[#0a84ff]/30 rounded-2xl p-5 relative overflow-hidden shadow-[inset_0_0_20px_rgba(10,132,255,0.05)]">
                    <p className="text-[10px] uppercase font-bold text-[#0a84ff] tracking-widest mb-1 flex items-center gap-1">
                      <span className="w-1.5 h-1.5 rounded-full bg-[#0a84ff]"></span> L2 (Neon Postgres)
                    </p>
                    <p className="text-4xl font-black text-white mb-2">{cacheStats.l2_pg_entries >= 0 ? cacheStats.l2_pg_entries : 'Error'}</p>
                    <p className="text-xs text-[#8e8e93]">Latensi: <strong className="text-white">~10-30ms</strong> (Cold Store)</p>
                  </div>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                  {/* Circuit Breakers */}
                  <div className="bg-[#1c1c1e] border border-white/10 rounded-2xl p-6">
                    <h2 className="text-sm font-bold text-white uppercase tracking-widest mb-4 flex items-center gap-2">
                      🔌 Circuit Breakers Status
                    </h2>
                    <div className="space-y-3">
                      {Object.entries(cacheStats.circuit_breakers || {}).map(([provider, state]: [string, any]) => (
                        <div key={provider} className="flex items-center justify-between bg-black border border-white/5 p-3 rounded-xl">
                          <span className="font-mono text-sm capitalize text-[#8e8e93]">{provider}</span>
                          <span className={`px-3 py-1 rounded-md text-[10px] font-black tracking-widest uppercase
                            ${state === 'closed' ? 'bg-[#30d158]/20 text-[#30d158]' : 
                              state === 'open' ? 'bg-[#ff453a]/20 text-[#ff453a] animate-pulse' : 
                              'bg-[#ff9f0a]/20 text-[#ff9f0a]'}`}
                          >
                            {state}
                          </span>
                        </div>
                      ))}
                    </div>
                  </div>

                  {/* Scrape Engine Activity */}
                  <div className="bg-[#1c1c1e] border border-white/10 rounded-2xl p-6 flex flex-col justify-between">
                    <div>
                      <h2 className="text-sm font-bold text-white uppercase tracking-widest mb-4 flex items-center gap-2">
                        🕵️ Live Scrape (L3) Activity
                      </h2>
                      <div className="bg-black border border-white/5 p-5 rounded-xl text-center">
                        <p className="text-6xl font-black text-[#bf5af2] mb-2">{cacheStats.inflight_scrapes}</p>
                        <p className="text-xs text-[#8e8e93] font-bold uppercase tracking-wider">In-Flight Coalesced Scrapes</p>
                      </div>
                    </div>
                    <div className="mt-6 text-xs text-[#8e8e93] bg-black p-4 rounded-xl border border-white/5 leading-relaxed">
                      <strong className="text-white">💡 Engine Info:</strong> Request ganda ke episode yang sama akan di-coalesce. Scraper L3 hanya dipanggil ketika L0, L1, dan L2 MISS atau memasuki SWR window (Stale-While-Revalidate).
                    </div>
                  </div>
                </div>

              </div>
            )}
          </div>
        )}

      </main>
    </div>
  );
}
