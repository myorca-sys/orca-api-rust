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
        air_day = None
        genres_local = []
        score_local = None
        views_local = None
        total_episodes = None
        studio = None
        status_local = None

        # Look for views/followers (e.g. Diikuti 372 orang or post-views-count)
        bmc_div = soup.select_one('.bmc')
        if bmc_div:
            v_match = re.search(r'([\d,.]+)', bmc_div.get_text(strip=True))
            if v_match:
                try:
                    views_local = int(v_match.group(1).replace(',', '').replace('.', ''))
                except:
                    pass
        else:
            view_span = soup.select_one('.post-views-count')
            if view_span:
                v_match = re.search(r'([\d,.]+)', view_span.get_text(strip=True))
                if v_match:
                    try:
                        views_local = int(v_match.group(1).replace(',', '').replace('.', ''))
                    except:
                        pass

        # Look for other metadata like studio, status, genre, score
        # In Kuronime, they often use <b>Tag Name:</b> Value
        for b_tag in soup.find_all(['b', 'strong', 'span']):
            text = b_tag.parent.get_text(strip=True) if b_tag.parent else ''
            lower_text = text.lower()
            if 'hari rilis' in lower_text or 'hari tayang' in lower_text:
                air_day = text.split(':', 1)[-1].strip() if ':' in text else None
            elif 'genre' in lower_text:
                a_tags = b_tag.parent.find_all('a') if b_tag.parent else []
                if a_tags:
                    genres_local = [a.get_text(strip=True) for a in a_tags]
                elif ':' in text:
                    genres_local = [g.strip() for g in text.split(':', 1)[-1].split(',')]
            elif 'skor' in lower_text or 'score' in lower_text or 'rating' in lower_text:
                try:
                    score_match = re.search(r'([\d.]+)', text.split(':', 1)[-1]) if ':' in text else re.search(r'([\d.]+)', text)
                    if score_match:
                        score_local = float(score_match.group(1))
                except Exception:
                    pass
            elif 'total episode' in lower_text or 'jumlah episode' in lower_text:
                m = re.search(r'\d+', text.split(':', 1)[-1]) if ':' in text else re.search(r'\d+', text)
                if m: total_episodes = int(m.group())
            elif 'studio' in lower_text:
                studio = text.split(':', 1)[-1].strip() if ':' in text else None
            elif 'status' in lower_text:
                status_local = text.split(':', 1)[-1].strip() if ':' in text else None
        
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
