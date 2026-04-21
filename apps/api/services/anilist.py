import re
import asyncio
import difflib
from cachetools import TTLCache
from services.clients import client

GET_ANIME_DETAILS = """
  query ($search: String) {
    Page(page: 1, perPage: 5) {
      media(search: $search, type: ANIME, sort: SEARCH_MATCH) {
        id
        title {
          romaji
          english
          native
        }
        synonyms
        coverImage {
          extraLarge
          large
          color
        }
        bannerImage
        averageScore
        popularity
        trending
        episodes
        status
        season
        seasonYear
        description(asHtml: false)
        genres
        studios {
          nodes {
            name
            isAnimationStudio
          }
        }
        recommendations {
          nodes {
            mediaRecommendation {
              id
              title { romaji english }
              coverImage { large }
            }
          }
        }
        nextAiringEpisode {
          episode
          timeUntilAiring
        }
      }
    }
  }
"""

anilist_cache = TTLCache(maxsize=1000, ttl=86400)
anilist_sem = asyncio.Semaphore(5)

GET_ANIME_BY_ID = """
  query ($id: Int) {
    Media(id: $id, type: ANIME, isAdult: false) {
      id
      title {
        romaji
        english
        native
      }
      synonyms
      coverImage {
        extraLarge
        large
        color
      }
      bannerImage
      averageScore
      popularity
      trending
      episodes
      status
      season
      seasonYear
      description(asHtml: false)
      genres
      studios {
        nodes {
          name
          isAnimationStudio
        }
      }
      recommendations {
        nodes {
          mediaRecommendation {
            id
            title { romaji english }
            coverImage { large }
          }
        }
      }
      nextAiringEpisode {
        episode
        timeUntilAiring
      }
    }
  }
"""

async def fetch_anilist_info_by_id(anilist_id: int):
    cache_key = f"anilist_id_{anilist_id}"
    if cache_key in anilist_cache:
        return anilist_cache[cache_key]

    async with anilist_sem:
        try:
            response = await client.post('https://graphql.anilist.co', json={
                'query': GET_ANIME_BY_ID,
                'variables': {'id': anilist_id}
            })
            
            data = response.json()
            media = data.get('data', {}).get('Media')
            
            if not media:
                anilist_cache[cache_key] = None
                return None
                
            studios = []
            if media.get('studios') and media['studios'].get('nodes'):
                studios = [s['name'] for s in media['studios']['nodes'] if s.get('isAnimationStudio')]
            
            recs = []
            if media.get('recommendations') and media['recommendations'].get('nodes'):
                for r in media['recommendations']['nodes']:
                    rec_media = r.get('mediaRecommendation')
                    if rec_media:
                        recs.append({
                            'id': rec_media.get('id'),
                            'title': rec_media.get('title', {}).get('english') or rec_media.get('title', {}).get('romaji'),
                            'cover': rec_media.get('coverImage', {}).get('large')
                        })

            result = {
                'anilistId': media['id'],
                'cleanTitle': media['title'].get('english') or media['title'].get('romaji'),
                'romajiTitle': media['title'].get('romaji'),
                'nativeTitle': media['title'].get('romaji'),
                'synonyms': media.get('synonyms', []),
                'hdImage': media['coverImage'].get('extraLarge') or media['coverImage'].get('large'),
                'color': media['coverImage'].get('color'),
                'banner': media.get('bannerImage'),
                'score': media.get('averageScore'),
                'popularity': media.get('popularity', 0),
                'trending': media.get('trending', 0),
                'description': media.get('description'),
                'genres': media.get('genres', []),
                'episodes': media.get('episodes'),
                'status': media.get('status'),
                'season': media.get('season'),
                'seasonYear': media.get('seasonYear'),
                'studios': studios,
                'recommendations': recs,
                'nextAiringEpisode': media.get('nextAiringEpisode')
            }
            anilist_cache[cache_key] = result
            return result
                
        except Exception as e:
            print(f"[AniList] Error fetching data by ID '{anilist_id}': {str(e)}")
            return None

def roman_to_int(s):
    rom_val = {'I': 1, 'V': 5, 'X': 10, 'L': 50, 'C': 100, 'D': 500, 'M': 1000}
    int_val = 0
    for i in range(len(s)):
        if i > 0 and rom_val[s[i]] > rom_val[s[i - 1]]:
            int_val += rom_val[s[i]] - 2 * rom_val[s[i - 1]]
        else:
            int_val += rom_val[s[i]]
    return int_val

async def fetch_anilist_info(title: str):
    search_query = re.sub(r'\b(episode|ep|sub indo|batch)\b', '', title, flags=re.IGNORECASE).strip()
    season_match = re.search(r'\b(?:S|Season|Part)\s*(\d+|[IVX]+)\b', search_query, re.IGNORECASE)
    target_season = None
    if season_match:
        val = season_match.group(1).upper()
        if val.isdigit():
            target_season = int(val)
        else:
            target_season = roman_to_int(val)
            
    base_query = re.sub(r'\b(?:S|Season|Part)\s*(\d+|[IVX]+)\b', '', search_query, flags=re.IGNORECASE).strip()
    base_query = re.sub(r'[^a-zA-Z0-9 ]', ' ', base_query).strip()
    base_query = re.sub(r'\s+', ' ', base_query)
    
    cache_key = f"{base_query}_S{target_season}" if target_season else base_query
    
    if cache_key in anilist_cache:
        return anilist_cache[cache_key]

    async with anilist_sem:
        try:
            response = await client.post('https://graphql.anilist.co', json={
                'query': GET_ANIME_DETAILS,
                'variables': {'search': search_query}
            })
            
            data = response.json()
            media_list = data.get('data', {}).get('Page', {}).get('media', [])
            
            if not media_list and target_season:
                response = await client.post('https://graphql.anilist.co', json={
                    'query': GET_ANIME_DETAILS,
                    'variables': {'search': base_query}
                })
                data = response.json()
                media_list = data.get('data', {}).get('Page', {}).get('media', [])

            if not media_list:
                anilist_cache[cache_key] = None
                return None
                
            media_list = [m for m in media_list if 'Hentai' not in m.get('genres', [])]
            if not media_list:
                anilist_cache[cache_key] = None
                return None
                
            best_media = None
            highest_score = 0.0
            
            for m in media_list:
                titles = [m['title'].get('romaji'), m['title'].get('english'), m['title'].get('native')]
                valid_titles = [t.lower() for t in titles if t]
                if not valid_titles:
                    continue
                score = max(difflib.SequenceMatcher(None, search_query.lower(), t).ratio() for t in valid_titles)
                if score > highest_score:
                    highest_score = score
                    best_media = m
                    
            if highest_score < 0.7:
                print(f"[AniList] Rejecting match for '{search_query}', highest similarity score is {highest_score:.2f} (< 0.7)")
                anilist_cache[cache_key] = None
                return None
                
            media = best_media
            
            if target_season:
                for m in media_list:
                    titles = [m['title'].get('romaji') or '', m['title'].get('english') or '']
                    combined_title = " ".join(titles).lower()
                    if re.search(fr'\b(?:season\s*{target_season}|{target_season}th\s*season|part\s*{target_season})\b', combined_title) or \
                       re.search(fr'\b(season|part)\s+{target_season}\b', combined_title):
                        media = m
                        break
            
            studios = []
            if media.get('studios') and media['studios'].get('nodes'):
                studios = [s['name'] for s in media['studios']['nodes'] if s.get('isAnimationStudio')]
            
            recs = []
            if media.get('recommendations') and media['recommendations'].get('nodes'):
                for r in media['recommendations']['nodes']:
                    rec_media = r.get('mediaRecommendation')
                    if rec_media:
                        recs.append({
                            'id': rec_media.get('id'),
                            'title': rec_media.get('title', {}).get('english') or rec_media.get('title', {}).get('romaji'),
                            'cover': rec_media.get('coverImage', {}).get('large')
                        })

            result = {
                'anilistId': media['id'],
                'cleanTitle': media['title']['english'] or media['title']['romaji'],
                'nativeTitle': media['title'].get('native'),
                'synonyms': media.get('synonyms', []),
                'hdImage': media['coverImage']['extraLarge'] or media['coverImage']['large'],
                'color': media['coverImage'].get('color'),
                'banner': media['bannerImage'],
                'score': media['averageScore'],
                'popularity': media.get('popularity', 0),
                'trending': media.get('trending', 0),
                'description': media.get('description'),
                'genres': media.get('genres', []),
                'episodes': media.get('episodes'),
                'status': media.get('status'),
                'season': media.get('season'),
                'seasonYear': media.get('seasonYear'),
                'studios': studios,
                'recommendations': recs,
                'nextAiringEpisode': media.get('nextAiringEpisode')
            }
            anilist_cache[cache_key] = result
            return result
                
        except Exception as e:
            print(f"[AniList] Error fetching data for '{search_query}': {str(e)}")
            return None
