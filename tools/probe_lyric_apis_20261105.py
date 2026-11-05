#!/usr/bin/env python3
"""One-off public API availability test (2026-11-05).

No credentials or copyrighted lyric text logged. No music files downloaded.
Status codes, response shape and timestamp presence only. Runs on GitHub
Actions; this is NOT the user's phone or home network.
"""
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import deque

UA="AADisplayCarPlayDiagnostics/1.0 (https://github.com/wangliunx3835/andriod-carplay)"
param=lambda base,**k: base+"?"+urllib.parse.urlencode(k)
song="海阔天空"
singer="Beyond"
known_id="7634441185327745025"
cases=[
 ("lrclib_example",param("https://lrclib.net/api/search",track_name="I Want to Live",artist_name="Borislav Slavov"),"https://lrclib.net/"),
 ("lrclib_chinese",param("https://lrclib.net/api/search",track_name=song,artist_name=singer),"https://lrclib.net/"),
 ("lrclib_id", "https://lrclib.net/api/get/3396226","https://lrclib.net/"),
 ("qishui_pc_search",param("https://api.qishui.com/luna/pc/search/track",q=song+" "+singer,cursor=0,search_method="input",aid=386088,device_platform="web",channel="pc_web"),"https://www.qishui.com/"),
 ("qishui_seo_track",param("https://beta-luna.douyin.com/luna/h5/seo_track",track_id=known_id,device_platform="web"),"https://music.douyin.com/"),
 ("qishui_car_share",param("https://music.douyin.com/qishui/share/track",track_id=known_id),"https://music.douyin.com/"),
 ("qishui_mobile_share",param("https://www.qishui.com/share/track",track_id=known_id),"https://www.qishui.com/"),
 ("lrcapi_advance",param("https://api.lrc.cx/api/v1/lyrics/advance",title=song,artist=singer),"https://api.lrc.cx/"),
 ("lrcapi_single",param("https://api.lrc.cx/api/v1/lyrics/single",title=song,artist=singer),"https://api.lrc.cx/"),
 ("amll_lrclib",param("https://api.amll.dev/v1/lrclib/search",track_name=song,artist_name=singer),"https://api.amll.dev/"),
 ("lrcmux_compat",param("https://api.lrcmux.dev/compat/lrclib/api/search",track_name=song,artist_name=singer),"https://api.lrcmux.dev/"),
 ("netease_lyric",param("https://music.163.com/api/song/lyric",id=186016,lv=1,tv=-1),"https://music.163.com/"),
 ("lrclib_user_song",param("https://lrclib.net/api/search",track_name="越界",artist_name="ShameU"),"https://lrclib.net/"),
 ("amll_user_song",param("https://api.amll.dev/v1/lrclib/search",track_name="越界",artist_name="ShameU"),"https://api.amll.dev/"),
 ("lrcapi_legacy",param("https://api.lrc.cx/lyrics",title=song,artist=singer),"https://api.lrc.cx/"),
 ("lrcapi_user_song",param("https://api.lrc.cx/lyrics",title="越界",artist="ShameU"),"https://api.lrc.cx/"),
 ("lrcapi_json_user_song",param("https://api.lrc.cx/jsonapi",title="越界",artist="ShameU"),"https://api.lrc.cx/"),
 ("netease_user_search",param("https://music.163.com/api/search/get/web",s="越界 ShameU",type=1,limit=10),"https://music.163.com/"),
]
timestamp=re.compile(r'\[(?:\d{1,3}:\d{2}(?:[.:]\d{1,3})?|\d{3,9},\d{2,9})\]')
class NoRedirect(urllib.request.HTTPRedirectHandler):
    pass

def summarize(data):
    summary={"bytes":len(data)}
    try:
        body=json.loads(data)
    except Exception:
        html=data.decode("utf-8","replace")
        summary["type"]="html-or-text"
        summary["router_data"]="_ROUTER_DATA" in html
        if summary["router_data"]:
            try:
                marker=html.index("_ROUTER_DATA")
                eq=html.index("=",marker)
                begin=html.index("{",eq)
                router=json.JSONDecoder().raw_decode(html[begin:])[0]
                timeline=router.get("loaderData",{}).get("track_page",{}).get("audioWithLyricsOption",{}).get("lyrics",{})
                summary["router_page_keys"]=list(router.get("loaderData",{}).keys())[:12]
                summary["router_sentence_count"]=len(timeline.get("sentences",[]) or [])
            except Exception as e:
                summary["router_parse_error"]=type(e).__name__
        summary["timestamp_sample_present"]=bool(timestamp.search(html))
        summary["is_empty"]=not html.strip()
        if current_label.startswith("lrcapi_"):
            summary["contains_lrc_time_tags"]=bool(timestamp.search(html))
            summary["has_artist_header"]=bool(re.search(r"(?mi)^\[ar:[^]]{1,80}\]",html))
        return summary
    summary["type"]=type(body).__name__
    if isinstance(body,dict):
        summary["keys"]=list(body)[:18]
        for k in ("code","status","status_code","message","error"):
            if k in body: summary[k]=str(body[k])[:130]
        if isinstance(body.get("seo_track"),dict):
            summary["seo_track_keys"]=list(body["seo_track"])[:15]
        if "lyric" in body:
            summary["lyric_type"]=type(body["lyric"]).__name__
            if isinstance(body["lyric"],dict):
                summary["lyric_keys"]=list(body["lyric"])[:20]
        if "result" in body and isinstance(body["result"],dict):
            summary["result_keys"]=list(body["result"])[:15]
            if current_label == "netease_user_search":
                songs=body["result"].get("songs",[]) or []
                options=[]
                for candidate in songs[:20]:
                    artistlist=candidate.get("artists",[]) or []
                    people=",".join(x.get("name","") for x in artistlist if isinstance(x,dict))
                    if candidate.get("name","")=="越界" and "shameu" in people.lower():
                        options.append({"id":candidate.get("id"),"durationMs":candidate.get("duration")})
                summary["user_song_exact_candidates"]=options[:5]
    if isinstance(body,list):
        summary["records"]=len(body)
        if body and isinstance(body[0],dict) and "trackName" in body[0]:
            songkey= "越界" if "user_song" in current_label else "海阔天空" if "chinese" in current_label or "amll" in current_label or "lrclib" in current_label else ""
            artistkey= "ShameU" if "user_song" in current_label else "Beyond"
            if songkey:
                normalize=lambda v:re.sub(r"[^\w\u4e00-\u9fff]","",str(v).lower())
                same=[x for x in body if isinstance(x,dict) and normalize(x.get("trackName",""))==normalize(songkey) and normalize(artistkey) in normalize(x.get("artistName",""))]
                summary["exact_song_artist_matches"]=len(same)
                summary["exact_synced_matches"]=sum(bool(isinstance(x.get("syncedLyrics"),str) and timestamp.search(x["syncedLyrics"])) for x in same)
        if body and isinstance(body[0],dict):
            summary["record_keys"]=list(body[0])[:18]
    q=deque([(body,0)])
    matched=[]
    node_count=0
    while q and node_count<1200:
        v,depth=q.popleft()
        node_count+=1
        if isinstance(v,str):
            if timestamp.search(v):
                matched.append({"size":len(v),"timed":True})
        if depth>=5:continue
        if isinstance(v,dict):
            for name,child in list(v.items())[:35]:
                if isinstance(child,(dict,list,str)):
                    q.append((child,depth+1))
        elif isinstance(v,list):
            for child in v[:25]:
                if isinstance(child,(dict,list,str)):
                    q.append((child,depth+1))
    summary["timed_lyric_candidates"]=matched[:5]
    return summary

for label,url,referer in cases:
    current_label=label
    req=urllib.request.Request(url,headers={
        "User-Agent":UA,
        "Accept":"application/json,text/html;q=0.9,*/*;q=0.8",
        "Referer":referer,
    })
    try:
        response=urllib.request.urlopen(req,timeout=12)
        with response:
            blob=response.read(850_000)
            result=dict(status=response.status, content_type=response.headers.get("Content-Type",""),
                        location_host=urllib.parse.urlparse(response.url).hostname,
                        **summarize(blob))
    except urllib.error.HTTPError as e:
        content=e.read(20_000)
        result={"status":e.code,"bytes":len(content),"content_type":e.headers.get("Content-Type",""),
                "retry_after":e.headers.get("Retry-After","")}
    except Exception as e:
        result={"error":type(e).__name__,"detail":str(e)[:140]}
    print("API_PROBE "+label+" "+json.dumps(result,ensure_ascii=False),flush=True)
    time.sleep(0.6)
