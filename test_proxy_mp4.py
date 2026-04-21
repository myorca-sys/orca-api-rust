import sys, os
os.environ['PROXY_SECRET'] = "anime-pro-secure-2026"
sys.path.append(os.path.abspath("apps/api"))
from utils.signed_url import sign_stream_url

url = "https://a6.mp4upload.com:183/d/w2x3hphpz3b4quuoxkqa2kccjdt3twhkp7sjms75xoavaeyf6bmgfm5vetujrmhiankffytn/video.mp4"
signed = sign_stream_url(url, "mp4upload", "720p")
print(signed)
