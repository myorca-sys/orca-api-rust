import re

with open("src/App.tsx", "r") as f:
    content = f.read()

if "interface EpisodeRow" not in content:
    content = content.replace(
        "interface AnimeRow {",
        "interface EpisodeRow {\n  id: number;\n  episodeNumber: number;\n  providerId: string;\n  episodeUrl: string;\n}\n\ninterface AnimeRow {"
    )

if "selectedAnime" not in content:
    content = content.replace(
        "// DB States\n  const [dbData",
        "// Modal States\n  const [selectedAnime, setSelectedAnime] = useState<AnimeRow | null>(null);\n  const [episodes, setEpisodes] = useState<EpisodeRow[]>([]);\n  const [epLoading, setEpLoading] = useState(false);\n  const [diagnostics, setDiagnostics] = useState<Record<number, any>>({});\n\n  // DB States\n  const [dbData"
    )

fetch_anime_func = """
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
"""

if "fetchAnimeEpisodes" not in content:
    content = content.replace(
        "const filteredData = useMemo(() => {",
        fetch_anime_func + "\n  const filteredData = useMemo(() => {"
    )

content = content.replace(
    '<div key={item.anilistId} className="flex items-center justify-between p-4 hover:bg-white/5 transition-colors">',
    '<div key={item.anilistId} onClick={() => fetchAnimeEpisodes(item)} className="flex items-center justify-between p-4 hover:bg-white/5 transition-colors cursor-pointer active:bg-white/10">'
)

content = content.replace(
    '                        <div key={i} className="flex flex-col gap-2">',
    '                        <div key={i} className="flex flex-col gap-2 cursor-pointer" onClick={() => {\n                          const anime = dbData.find(a => String(a.anilistId) === String(t.anilist_id));\n                          if(anime) fetchAnimeEpisodes(anime);\n                        }}>'
)


modal_jsx = """
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
"""

if "EPISODE DIAGNOSTIC MODAL" not in content:
    content = content.replace(
        "      </main>",
        modal_jsx + "\n      </main>"
    )

with open("src/App.tsx", "w") as f:
    f.write(content)

print("Patch applied")
