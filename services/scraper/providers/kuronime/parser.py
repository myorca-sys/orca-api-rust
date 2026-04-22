import re
from bs4 import BeautifulSoup
from providers.base_parser import BaseParser, AnimeDetail, EpisodeSource

class KuronimeParser(BaseParser):
    def parse_episode_list(self, html: str, base_url: str) -> AnimeDetail:
        soup = BeautifulSoup(html, "lxml")
        
        title_el = soup.select_one("h1.entry-title")
        title = title_el.text.strip() if title_el else "Unknown Title"
        
        poster_el = soup.select_one(".ts-post-image")
        poster = poster_el.get("src") if poster_el else None
        
        synopsis_el = soup.select_one(".entry-content[itemprop='description']")
        synopsis = synopsis_el.text.strip() if synopsis_el else "No synopsis available."
        
        episodes = []
        for li in soup.select(".bxcl ul li"):
            a = li.select_one(".lchx a")
            if not a: continue
            ep_url = a.get("href")
            ep_title = a.text.strip()
            
            num_text = ep_title
            try:
                ep_number = float(re.sub(r'[^0-9.]', '', num_text.split('Episode')[-1]))
            except:
                ep_number = 0.0
                
            episodes.append({
                "number": ep_number,
                "title": ep_title,
                "url": ep_url,
                "thumbnail": None
            })
            
        # Extract Local Metadata
        info_box = soup.select_one('.infox') or soup.select_one('.info-content')
        air_day = None
        genres_local = []
        score_local = None
        views_local = None
        total_episodes = None
        studio = None
        status_local = None

        if info_box:
            for span in info_box.find_all(['span', 'b', 'div', 'li']):
                text = span.get_text(strip=True)
                lower_text = text.lower()
                if 'hari rilis' in lower_text or 'hari tayang' in lower_text:
                    air_day = text.split(':', 1)[-1].strip()
                elif 'genre' in lower_text:
                    a_tags = span.find_all('a')
                    if a_tags:
                        genres_local = [a.get_text(strip=True) for a in a_tags]
                    else:
                        genres_local = [g.strip() for g in text.split(':', 1)[-1].split(',')]
                elif 'skor' in lower_text or 'score' in lower_text:
                    try:
                        score_match = re.search(r'([\d.]+)', text.split(':', 1)[-1])
                        if score_match:
                            score_local = float(score_match.group(1))
                    except Exception:
                        pass
                elif 'dilihat' in lower_text or 'views' in lower_text:
                    try:
                        v = re.search(r'([\d,.]+)', text.split(':', 1)[-1])
                        if v:
                            views_local = int(v.group(1).replace(',', '').replace('.', ''))
                    except:
                        pass
                elif 'total episode' in lower_text or 'episodes' in lower_text:
                    m = re.search(r'\d+', text.split(':', 1)[-1])
                    if m: total_episodes = int(m.group())
                elif 'studio' in lower_text:
                    studio = text.split(':', 1)[-1].strip()
                elif 'status' in lower_text:
                    status_local = text.split(':', 1)[-1].strip()
                    
        return {
            "episodes": sorted(episodes, key=lambda x: x["number"], reverse=True),
            "poster": poster,
            "synopsis": synopsis,
            "air_day": air_day,
            "genres_local": genres_local,
            "score_local": score_local,
            "views_local": views_local,
            "total_episodes": total_episodes,
            "studio": studio,
            "status_local": status_local
        }

    def parse_episode_sources(self, html: str) -> list[EpisodeSource]:
        return []
        
    def extract_req_id(self, html: str) -> str | None:
        matches = re.findall(r'var\s+[a-zA-Z0-9_]+\s*=\s*["\']([^"\']{100,})["\']', html)
        if matches:
            return matches[0]
        return None
