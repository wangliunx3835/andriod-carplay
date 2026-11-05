#!/usr/bin/env python3
"""Inspect public QiShui lyric JSON *structure only* for a known public test ID.
No raw lyric text printed, cached or uploaded.
"""
import json, urllib.request, re
id="7634441185327745025"
url="https://beta-luna.douyin.com/luna/h5/seo_track?track_id="+id+"&device_platform=web"
req=urllib.request.Request(url,headers={"User-Agent":"Mozilla/5.0","Referer":"https://music.douyin.com/"})
with urllib.request.urlopen(req,timeout=18) as o:
  blob=o.read(1_000_000)
  print("status",o.status,"bytes",len(blob),"type",o.headers.get("Content-Type"))
root=json.loads(blob)
for key in ["status_info","seo_track","track_player","lyric"]:
  a=root.get(key)
  print(key,"type",type(a).__name__,"keys",list(a)[:35] if isinstance(a,dict) else None)
  if isinstance(a,dict) and key=="seo_track":
    track=a.get("track")
    print("track fields",list(track)[:50] if isinstance(track,dict) else type(track).__name__)
    if isinstance(track,dict):
      print("track id",str(track.get("id"))[:35],"name length",len(str(track.get("name",""))))
      for ak in ("artists","artist","singers"):
        ar=track.get(ak)
        print("artists key",ak,"type",type(ar).__name__,"length",len(ar) if isinstance(ar,list) else None,
              "first keys",list(ar[0])[:20] if isinstance(ar,list) and ar and isinstance(ar[0],dict) else [])
  if isinstance(a,dict) and key=="lyric":
    val=a.get("content")
    print("lyric content type",type(val).__name__,"length",len(val) if isinstance(val,(list,str,dict)) else None)
    if isinstance(val,str):
      print("timing counts",{"lrc":len(re.findall(r'\[\d\d:\d\d[.:]\d{2,3}\]',val)),
                             "krc":len(re.findall(r'\[\d+,\d+\]',val)),
                             "wordtime":len(re.findall(r'<\d+,\d+,\d+>',val))},
            "first 18 literal signature",repr(re.sub(r'[\w\u4e00-\u9fff]','x',val[:60])[:60]))
print("statusInfo",root.get("status_info"))
