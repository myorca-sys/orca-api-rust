import ExploreView from "@/features/explore/ExploreView";
import { api } from "@/core/lib/api";

export const revalidate = 60;

export default async function Page() {
  let initialResults = [];

  try {
    const res = await api.browse({ page: 1, sort: "popularity" }, { next: { revalidate: 60 } });
    
    if (res?.success && res.data) {
      initialResults = res.data.map((m: any) => ({
        id: String(m.anilistId),
        title: m.cleanTitle || m.nativeTitle || "",
        img: m.coverImage,
        score: m.score,
        color: m.color,
        status: m.status,
        seasonYear: m.year,
      }));
    }
  } catch (error) {
    console.error("Failed to fetch initial explore data via RSC:", error);
  }

  return <ExploreView initialResults={initialResults} />;
}
