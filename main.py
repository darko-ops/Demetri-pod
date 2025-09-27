import os, re, uuid, time, datetime as dt, feedparser, yaml, requests
from pathlib import Path
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from pydub import AudioSegment
from pydub.effects import normalize
from openai import OpenAI

load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

CFG = yaml.safe_load(Path("config.yaml").read_text())
TITLE = os.getenv("PODCAST_TITLE","Demetri.xyz")
VOICE = os.getenv("HOST_VOICE","alloy")
MAX_STORIES = int(os.getenv("MAX_STORIES","4"))
OUTDIR = Path(CFG["output"]["dir"])
OUTDIR.mkdir(exist_ok=True)

def clean(txt): return re.sub(r"\s+"," ", txt).strip()

def fetch_recent_items():
    picks=[]
    cutoff = dt.datetime.utcnow() - dt.timedelta(days=2)
    for url in CFG["feeds"]:
        f = feedparser.parse(url)
        for e in f.entries:
            published = getattr(e, "published_parsed", None)
            if not published: continue
            pdt = dt.datetime(*published[:6])
            if pdt < cutoff: continue
            title = e.title
            link  = e.link
            if CFG["filters"]["include_keywords"]:
                if not any(k.lower() in title.lower() for k in CFG["filters"]["include_keywords"]): 
                    continue
            if CFG["filters"]["exclude_keywords"]:
                if any(k.lower() in title.lower() for k in CFG["filters"]["exclude_keywords"]):
                    continue
            picks.append({"title": title, "link": link})
    # dedupe by title
    seen=set(); uniq=[]
    for it in picks:
        t=it["title"]
        if t in seen: continue
        seen.add(t); uniq.append(it)
    return uniq[:MAX_STORIES]

def fetch_page_text(url, timeout=10):
    try:
        html = requests.get(url, timeout=timeout, headers={"User-Agent":"Mozilla/5.0"}).text
        soup = BeautifulSoup(html, "html.parser")
        for s in soup(["script","style","noscript"]): s.decompose()
        return clean(soup.get_text(" "))
    except Exception:
        return ""

def llm(prompt, sys="You are a concise journalist host for a tech/AI podcast."):
    return client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role":"system","content":sys},{"role":"user","content":prompt}],
        temperature=0.7,
    ).choices[0].message.content

def tts(text, outpath):
    audio = client.audio.speech.create(
        model="gpt-4o-mini-tts",
        voice=VOICE,
        input=text,
        format="mp3"
    )
    with open(outpath, "wb") as f: f.write(audio.read())

def build_script(items):
    bullets=[]
    for it in items:
        page = fetch_page_text(it["link"])
        summ = llm(f"Summarize objectively in 3-4 tight bullet points. Title: {it['title']}\n\nSource:\n{page[:4000]}")
        bullets.append({"title": it["title"], "points": summ, "link": it["link"]})
    intro = llm(f"Write a 60-90s cold open for '{TITLE}'. Include this sign-on: \"{CFG['brand']['sign_on']}\". "
                f"Set expectations: {len(items)} stories, upbeat but not cringe.")
    segs=[]
    for b in bullets:
        segs.append(llm(
            "Turn this into a ~2 minute spoken segment with a single host. "
            "Lead with why it matters, then the facts, then a takeaway. "
            f"\nTitle: {b['title']}\nBullets:\n{b['points']}\nCite the source URL at the end: {b['link']}"
        ))
    outro = llm(f"Write a 20-30s outro. Include: \"{CFG['brand']['sign_off']}\"")
    return intro, segs, outro, bullets

def mix_segments(mp3_paths, bed_path=None):
    voice = AudioSegment.silent(duration=0)
    for p in mp3_paths:
        voice += AudioSegment.from_mp3(p) + AudioSegment.silent(300)  # 0.3s gaps
    voice = normalize(voice)
    if bed_path and Path(bed_path).exists():
        bed = AudioSegment.from_file(bed_path)
        loops = (len(voice) // len(bed)) + 1
        bed_full = (bed * loops)[:len(voice)]
        bed_full = bed_full - 18  # duck
        mix = voice.overlay(bed_full)
        return normalize(mix)
    return voice

def write_rss(episode_mp3, title, desc, pubdate, cover_png=None):
    # minimal RSS (good enough for self-host or Castopod). You can later import to Spotify/Apple.
    rss_path = OUTDIR / "feed.xml"
    base_url = os.getenv("RSS_SITE").rstrip("/")
    item_url = f"{base_url}/podcast/{episode_mp3.name}"
    cover_tag = f"<itunes:image href=\"{base_url}/podcast/cover.png\"/>" if cover_png else ""
    existing = rss_path.read_text() if rss_path.exists() else None
    header = f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:itunes="http://www.itunes.com/dtds/podcast-1.0.dtd">
<channel>
<title>{TITLE}</title>
<link>{base_url}</link>
<description>{TITLE} — news, whitepapers, and takes.</description>
<language>en-us</language>
<managingEditor>{os.getenv('RSS_EMAIL')} ({os.getenv('RSS_AUTHOR')})</managingEditor>
{cover_tag}
"""
    item = f"""
<item>
  <title>{title}</title>
  <description><![CDATA[{desc}]]></description>
  <pubDate>{pubdate}</pubDate>
  <enclosure url="{item_url}" length="{episode_mp3.stat().st_size}" type="audio/mpeg"/>
  <guid>{uuid.uuid4()}</guid>
</item>
"""
    footer = "\n</channel>\n</rss>\n"
    if existing:
        # insert new item after header line  (quick-and-dirty)
        content = existing.replace("</channel>\n</rss>\n", item + footer)
    else:
        content = header + item + footer
    rss_path.write_text(content)

def main():
    ts = dt.datetime.utcnow().strftime("%Y%m%d-%H%M")
    epdir = OUTDIR / ts
    epdir.mkdir(parents=True, exist_ok=True)

    items = fetch_recent_items()
    intro, segs, outro, bullets = build_script(items)

    # write scripts
    (epdir / "script_intro.txt").write_text(intro)
    for i,s in enumerate(segs,1): (epdir / f"script_seg{i}.txt").write_text(s)
    (epdir / "script_outro.txt").write_text(outro)
    (epdir / "sources.json").write_text(str(bullets))

    # TTS
    intro_mp3 = epdir / "intro.mp3"; tts(intro, intro_mp3)
    seg_paths=[]
    for i,s in enumerate(segs,1):
        p = epdir / f"seg{i}.mp3"; tts(s, p); seg_paths.append(p)
    outro_mp3 = epdir / "outro.mp3"; tts(outro, outro_mp3)

    # Mix
    final = epdir / f"{TITLE.lower().replace(' ','_')}_{ts}.mp3"
    mix = mix_segments([intro_mp3, *seg_paths, outro_mp3], CFG["episode"].get("music_bed_path") or None)
    mix.export(final, format="mp3", bitrate="192k")

    # RSS entry
    ep_title = f"{TITLE} — {dt.datetime.utcnow():%b %d, %Y}"
    desc = "Auto-generated episode covering today's top AI/tech stories."
    write_rss(final, ep_title, desc, dt.datetime.utcnow().strftime("%a, %d %b %Y %H:%M:%S +0000"),
              CFG["output"].get("cover_png") or None)

    print(f"\n✅ Episode ready: {final}\nScripts in: {epdir}\n")

if __name__ == "__main__":
    main()
