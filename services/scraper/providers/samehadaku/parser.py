import re
from bs4 import BeautifulSoup
from providers.base_parser import BaseParser, AnimeDetail, EpisodeSource

class SamehadakuParser(BaseParser):
    def parse_episode_list(self, html: str, base_url: str) -> AnimeDetail:
        soup = BeautifulSoup(html, 'lxml')
        episodes = []
        
        # Latest episodes on homepage or episode list in series page
        # In series page, it's inside .lstepsiode.listeps
        list_items = soup.select('.lstepsiode.listeps ul li')
        for li in list_items:
            # Episode number is usually in .epsright .eps a
            # Or in .epsleft .lchx a
            a_tag = li.select_one('.epsleft .lchx a')
            if not a_tag:
                a_tag = li.select_one('.epsright .eps a')
                
            if a_tag:
                title = a_tag.get_text(strip=True)
                url = a_tag.get('href')
                
                # Extract number
                # e.g. "One Piece Episode 1156" -> 1156
                m = re.search(r'(?:episode|eps?)[.\s]*(\d+(?:[.,]\d+)?)', title, re.IGNORECASE)
                ep_num = float(m.group(1).replace(",", ".")) if m else 0.0
                
                # If ep_num is still 0, try to get it from .epsright .eps
                if ep_num == 0:
                    eps_div = li.select_one('.epsright .eps')
                    if eps_div:
                        try:
                            ep_num = float(eps_div.get_text(strip=True))
                        except:
                            pass

                episodes.append({
                    'number': ep_num,
                    'title': title,
                    'url': url,
                    'thumbnail': None
                })
        
        synopsis = soup.select_one('.entry-content.entry-content-single')
        
        # Extract Local Metadata
        info_box = soup.select_one('.infox') or soup.select_one('.spe')
        air_day = None
        genres_local = []
        score_local = None
        views_local = None
        total_episodes = None
        studio = None
        status_local = None

        if info_box:
            for span in info_box.find_all(['span', 'b', 'div']):
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
        
        # also views might be somewhere, skip for now to avoid errors

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
        
        # 1. Look for AJAX player options
        # <div class="east_player_option" data-post="48794" data-nume="1" data-type="schtml">
        for opt in soup.select('.east_player_option'):
            label = opt.select_one('span')
            label_text = label.get_text(strip=True) if label else 'Unknown'
            quality = self._detect_quality(label_text)
            
            if quality not in ["720p", "1080p"]:
                continue
            
            # Since we can't easily do AJAX yet without the correct action,
            # we store these as special sources that might need secondary resolving
            sources.append({
                'provider': self._detect_provider(label_text),
                'quality': quality,
                'url': f"ajax://{opt.get('data-post')}/{opt.get('data-nume')}/{opt.get('data-type')}",
                'type': 'iframe'
            })
            
        # 2. Look for download links as fallback/direct sources
        for container in soup.select('.download-eps'):
            quality_tag = container.find('b')
            quality_label = quality_tag.get_text(strip=True) if quality_tag else 'Auto'
            
            for li in container.select('ul li'):
                # Format: <strong>Quality</strong> <span><a href="...">Source</a></span>
                q_strong = li.select_one('strong')
                if q_strong:
                    quality_label = q_strong.get_text(strip=True)
                
                quality = self._detect_quality(quality_label)
                if quality not in ["720p", "1080p"]:
                    continue
                    
                for a in li.select('span a'):
                    src_name = a.get_text(strip=True)
                    url = a.get('href')
                    
                    if url and 'http' in url:
                        is_direct = "pixeldrain" in url.lower() or "wibufile" in url.lower()
                        sources.append({
                            'provider': f"{src_name} (DL)",
                            'quality': quality,
                            'url': url,
                            'type': 'mp4 (direct)' if is_direct else 'iframe' # Will be resolved by UniversalExtractor
                        })
                        
        return sources

    def parse_search_results(self, html: str) -> list[dict]:
        soup = BeautifulSoup(html, 'lxml')
        results = []
        for article in soup.select('article.animpost'):
            a = article.select_one('a')
            if a:
                title = a.get('title') or a.text.strip()
                url = a.get('href')
                if url and '/anime/' in url:
                    results.append({'title': title, 'url': url})
        return results

    def _detect_quality(self, text: str) -> str:
        text = text.lower()
        if '1080' in text: return '1080p'
        if '720' in text: return '720p'
        if '480' in text: return '480p'
        if '360' in text: return '360p'
        return 'Auto'

    def _detect_provider(self, text: str) -> str:
        text = text.lower()
        if 'blogspot' in text: return 'Blogspot'
        if 'wibufile' in text: return 'Wibufile'
        if 'mega' in text: return 'Mega'
        if 'pucuk' in text: return 'Pucuk'
        if 'gofile' in text: return 'Gofile'
        if 'kraken' in text: return 'Kraken'
        return text.title()
