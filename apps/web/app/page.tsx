import HomeView from "@/features/home/HomeView";
import { api } from "@/core/lib/api";

export const runtime = 'edge';
export const revalidate = 3600;

export default async function Page() {
  let hero = [];
  let airing = [];
  let latest = [];
  let popular = [];
  let completed = [];
  let top_rated = [];
  let isekai = [];
  let movies = [];
  let trending = [];
  let errorMsg = null;

  try {
    const res = await api.homeV2();
    if (res.success && res.data) {
      hero = res.data.hero || [];
      airing = res.data.airing || [];
      latest = res.data.latest || [];
      popular = res.data.popular || [];
      completed = res.data.completed || [];
      top_rated = res.data.top_rated || [];
      isekai = res.data.isekai || [];
      movies = res.data.movies || [];
      trending = res.data.trending || [];
    }
  } catch (error: any) {
    errorMsg = error.message || String(error);
    console.error("Failed to fetch home data:", error);
  }

  if (errorMsg) {
    return <div style={{ color: 'red', padding: '20px' }}>Error fetching data: {errorMsg}</div>;
  }

  return <HomeView 
    initialHero={hero} 
    initialAiring={airing} 
    initialLatest={latest} 
    initialPopular={popular} 
    initialCompleted={completed} 
    initialTopRated={top_rated}
    initialIsekai={isekai}
    initialMovies={movies}
    initialTrending={trending}
  />;
}
