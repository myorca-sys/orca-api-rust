import re
from bs4 import BeautifulSoup
from providers.base_parser import BaseParser, AnimeDetail, EpisodeSource

class OtakudesuParser(BaseParser):
    def parse_episode_list(self, html: str, base_url: str) -> AnimeDetail:
        soup = BeautifulSoup(html, 'lxml')
        episodes = []
        for li in soup.select('div.episodelist ul li'):
            a = li.select_one('a')
            if a:
                title = a.get_text(strip=True)
                m = re.search(r'(?:episode|eps?)[.\s]*(\d+(?:[.,]\d+)?)', title, re.IGNORECASE)
                ep_num = float(m.group(1).replace(",", ".")) if m else 0.0
                episodes.append({
                    'number': ep_num,
                    'title': title,
                    'url': a.get('href'),
                    'thumbnail': None
                })
        
        synopsis = soup.select_one('div.sinopc')
        
        # Extract Local Metadata
        info_box = soup.select_one('.infozingle')
        air_day = None
        genres_local = []
        score_local = None
        views_local = None
        total_episodes = None
        studio = None
        status_local = None

        if info_box:
            for p in info_box.find_all('p'):
                text = p.get_text(strip=True)
                lower_text = text.lower()
                if 'hari waktu tayang' in lower_text or 'hari tayang' in lower_text:
                    air_day = text.split(':', 1)[-1].strip()
                elif 'genre' in lower_text:
                    genres_local = [g.strip() for g in text.split(':', 1)[-1].split(',')]
                elif 'skor' in lower_text:
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
                elif 'total episode' in lower_text:
                    m = re.search(r'\d+', text)
                    if m: total_episodes = int(m.group())
                elif 'studio' in lower_text:
                    studio = text.split(':', 1)[-1].strip()
                elif 'status' in lower_text:
                    status_local = text.split(':', 1)[-1].strip()
        
        return {
            'episodes': sorted(episodes, key=lambda x: x["number"], reverse=True),
            'poster': None,
            'synopsis': synopsis.get_text(strip=True) if synopsis else '',
            'air_day': air_day,
            'genres_local': genres_local,
            'score_local': score_local,
            'views_local': views_local,
            'total_episodes': total_episodes,
            'studio': studio,
            'status_local': status_local
        }

    def parse_episode_sources(self, html: str) -> list[EpisodeSource]:
        soup = BeautifulSoup(html, 'lxml')
        sources = []
        for iframe in soup.find_all('iframe'):
            src = iframe.get('src', '')
            if src and 'http' in src:
                if any(ads in src for ads in ['googlesyndication', 'doubleclick', 'ads']):
                    continue
                sources.append({
                    'provider': self._detect_provider(src),
                    'quality': 'Auto',
                    'url': src,
                    'type': 'iframe'
                })
        return sources

    def parse_search_results(self, html: str) -> list[dict]:
        soup = BeautifulSoup(html, 'lxml')
        results = []
        for li in soup.select('ul.chbox li'):
            a = li.find('a')
            if a:
                title = a.get_text(strip=True)
                url = a.get('href')
                if url and '/anime/' in url:
                    results.append({'title': title, 'url': url})
        
        # Fallback to general search items
        if not results:
            for article in soup.select('article'):
                a = article.find('a')
                if a and '/anime/' in a.get('href', ''):
                    results.append({
                        'title': a.get('title') or a.text.strip(),
                        'url': a.get('href')
                    })
        return results

    def extract_mirrors(self, html: str) -> list[dict]:
        soup = BeautifulSoup(html, 'lxml')
        mirrors = []
        for a in soup.select('.mirrorstream ul li a[data-content]'):
            data_content = a.get('data-content')
            if not data_content: continue
            
            quality_label = 'Auto'
            li_parent = a.find_parent('li')
            if li_parent:
                prev_li = li_parent.find_previous_sibling('li')
                if prev_li:
                    quality_label = prev_li.get_text(strip=True)
                    
            provider_label = a.get_text(strip=True)
            mirrors.append({
                'data_content': data_content,
                'quality': self._detect_quality(quality_label),
                'provider': self._detect_provider(provider_label) if self._detect_provider(provider_label) != 'Unknown' else provider_label
            })
        return mirrors
        
    def extract_iframe_src(self, iframe_html: str) -> str | None:
        match = re.search(r'<iframe[^>]+src="([^"]+)"', iframe_html, re.IGNORECASE)
        return match.group(1) if match else None

    def _detect_quality(self, text: str) -> str:
        text = text.lower()
        if '1080' in text: return '1080p'
        if '720' in text: return '720p'
        if '480' in text: return '480p'
        if '360' in text: return '360p'
        return 'Auto'

    def _detect_provider(self, url: str) -> str:
        if 'desudrives' in url.lower() or 'desustream' in url.lower(): return 'DesuDrives'
        if 'mp4upload' in url.lower(): return 'Mp4upload'
        if 'streamtape' in url.lower(): return 'Streamtape'
        if 'doodstream' in url.lower() or 'dood' in url.lower(): return 'Doodstream'
        if '4meplayer' in url.lower(): return '4mePlayer'
        return 'Unknown'