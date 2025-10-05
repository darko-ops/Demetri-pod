import os, re, uuid, time, datetime as dt, feedparser, yaml, requests, json
import PyPDF2
from pathlib import Path
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from pydub import AudioSegment
from pydub.effects import normalize
import google.generativeai as genai
from openai import OpenAI
import tweepy
from elevenlabs.client import ElevenLabs
from elevenlabs import save

load_dotenv()

# API Clients
openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
elevenlabs_client = ElevenLabs(api_key=os.getenv("ELEVENLABS_API_KEY"))

# Twitter API setup
twitter_client = tweepy.Client(
    bearer_token=os.getenv("TWITTER_BEARER_TOKEN"),
    consumer_key=os.getenv("TWITTER_API_KEY"),
    consumer_secret=os.getenv("TWITTER_API_SECRET"),
    access_token=os.getenv("TWITTER_ACCESS_TOKEN"),
    access_token_secret=os.getenv("TWITTER_ACCESS_TOKEN_SECRET"),
    wait_on_rate_limit=True
)

CFG = yaml.safe_load(Path("config.yaml").read_text())
TITLE = os.getenv("PODCAST_TITLE", "Demetri.xyz")
MAX_STORIES = int(os.getenv("MAX_STORIES", "4"))
OUTDIR = Path(CFG["output"]["dir"])
OUTDIR.mkdir(exist_ok=True)

# Voice configuration
HOST_VOICE_ID = os.getenv("ELEVENLABS_HOST_VOICE_ID")
COHOST_VOICE_ID = os.getenv("ELEVENLABS_COHOST_VOICE_ID")
USE_AI_SERVICE = os.getenv("AI_SERVICE", "gemini")

def clean(txt): 
    return re.sub(r"\s+", " ", txt).strip()

def create_custom_intro(episode_metadata, epdir):
    """Create custom intro based on configuration"""
    intro_segments = []
    
    # 1. Pre-recorded audio intro (if configured)
    custom_intro_path = CFG.get("episode", {}).get("custom_intro_path")
    if custom_intro_path and Path(custom_intro_path).exists():
        print("🎵 Adding pre-recorded intro...")
        intro_audio = AudioSegment.from_file(custom_intro_path)
        intro_segments.append(intro_audio)
    
    # 2. Custom text intro (if configured)
    custom_intro_text = CFG.get("brand", {}).get("custom_intro_text")
    if custom_intro_text:
        print("🎙️ Generating custom intro text...")
        
        # Format the intro text with dynamic content
        formatted_intro = custom_intro_text.format(
            episode_number=episode_metadata.get("episode_number", ""),
            date=dt.datetime.now().strftime("%B %d, %Y"),
            topic_preview=episode_metadata.get("topic_preview", "today's topics")
        )
        
        # Generate TTS for custom intro
        custom_intro_mp3 = epdir / "custom_intro.mp3"
        elevenlabs_tts(formatted_intro, HOST_VOICE_ID, custom_intro_mp3)
        intro_segments.append(AudioSegment.from_mp3(custom_intro_mp3))
    
    # 3. Standard sign-on (if configured)
    sign_on = CFG.get("brand", {}).get("sign_on")
    if sign_on:
        sign_on_mp3 = epdir / "sign_on.mp3"
        elevenlabs_tts(sign_on, HOST_VOICE_ID, sign_on_mp3)
        intro_segments.append(AudioSegment.from_mp3(sign_on_mp3))
    
    # Combine all intro segments with small gaps
    if intro_segments:
        full_intro = AudioSegment.silent(duration=0)
        for i, segment in enumerate(intro_segments):
            full_intro += segment
            if i < len(intro_segments) - 1:  # Add gap between segments
                full_intro += AudioSegment.silent(duration=500)  # 0.5s gap
        return full_intro
    
    return AudioSegment.silent(duration=0)

def extract_text_from_pdf(pdf_path):
    """Extract text from PDF file"""
    try:
        with open(pdf_path, 'rb') as file:
            pdf_reader = PyPDF2.PdfReader(file)
            text = ""
            for page in pdf_reader.pages:
                text += page.extract_text() + "\n"
            return clean(text)
    except Exception as e:
        print(f"Error reading PDF {pdf_path}: {e}")
        return ""

def extract_text_from_file(file_path):
    """Extract text from various file formats"""
    file_path = Path(file_path)
    
    if file_path.suffix.lower() == '.pdf':
        return extract_text_from_pdf(file_path)
    elif file_path.suffix.lower() in ['.txt', '.md']:
        return file_path.read_text(encoding='utf-8')
    elif file_path.suffix.lower() == '.docx':
        try:
            import docx
            doc = docx.Document(file_path)
            return '\n'.join([paragraph.text for paragraph in doc.paragraphs])
        except ImportError:
            print("python-docx not installed. Cannot read .docx files")
            return ""
    else:
        print(f"Unsupported file format: {file_path.suffix}")
        return ""

def fetch_recent_items():
    """Fetch recent items from RSS feeds"""
    picks = []
    cutoff = dt.datetime.utcnow() - dt.timedelta(days=2)
    for url in CFG["feeds"]:
        f = feedparser.parse(url)
        for e in f.entries:
            published = getattr(e, "published_parsed", None)
            if not published: continue
            pdt = dt.datetime(*published[:6])
            if pdt < cutoff: continue
            title = e.title
            link = e.link
            if CFG["filters"]["include_keywords"]:
                if not any(k.lower() in title.lower() for k in CFG["filters"]["include_keywords"]): 
                    continue
            if CFG["filters"]["exclude_keywords"]:
                if any(k.lower() in title.lower() for k in CFG["filters"]["exclude_keywords"]):
                    continue
            picks.append({"title": title, "link": link, "type": "rss"})
    
    seen = set()
    uniq = []
    for it in picks:
        t = it["title"]
        if t in seen: continue
        seen.add(t)
        uniq.append(it)
    return uniq[:MAX_STORIES]

def fetch_page_text(url, timeout=10):
    """Fetch and extract text from web page"""
    try:
        html = requests.get(url, timeout=timeout, headers={"User-Agent": "Mozilla/5.0"}).text
        soup = BeautifulSoup(html, "html.parser")
        for s in soup(["script", "style", "noscript"]): 
            s.decompose()
        return clean(soup.get_text(" "))
    except Exception:
        return ""

def llm(prompt, sys="You are a concise journalist host for a tech/AI podcast.", use_service=None):
    """Generate text using either Gemini or OpenAI"""
    service = use_service or USE_AI_SERVICE
    
    if service == "gemini":
        try:
            model = genai.GenerativeModel('gemini-pro')
            full_prompt = f"{sys}\n\n{prompt}"
            response = model.generate_content(full_prompt)
            return response.text
        except Exception as e:
            print(f"Gemini API error: {e}")
            service = "openai"
    
    if service == "openai":
        return openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "system", "content": sys}, {"role": "user", "content": prompt}],
            temperature=0.7,
        ).choices[0].message.content

def elevenlabs_tts(text, voice_id, outpath):
    """Generate speech using ElevenLabs"""
    try:
        # ElevenLabs 2.x API
        audio = elevenlabs_client.text_to_speech.convert(
            voice_id=voice_id,
            text=text,
            model_id="eleven_monolingual_v1"
        )
        
        # Save the audio
        with open(outpath, 'wb') as f:
            for chunk in audio:
                f.write(chunk)
                
    except Exception as e:
        print(f"ElevenLabs TTS error: {e}")
        print("Falling back to OpenAI TTS...")
        openai_tts(text, outpath)

def openai_tts(text, outpath):
    """Fallback TTS using OpenAI"""
    try:
        response = openai_client.audio.speech.create(
            model="tts-1",
            voice="alloy",
            input=text
        )
        # Write bytes directly to file
        with open(outpath, 'wb') as f:
            f.write(response.content)
    except Exception as e:
        print(f"OpenAI TTS error: {e}")
        # Create silent placeholder if both fail
        from pydub import AudioSegment
        silent = AudioSegment.silent(duration=1000)
        silent.export(outpath, format="mp3")

def openai_tts(text, outpath):
    """Fallback TTS using OpenAI"""
    try:
        response = openai_client.audio.speech.create(
            model="tts-1",
            voice="alloy",
            input=text
        )
        # Write bytes directly to file
        with open(outpath, 'wb') as f:
            f.write(response.content)
    except Exception as e:
        print(f"OpenAI TTS error: {e}")
        # Create silent placeholder if both fail
        from pydub import AudioSegment
        silent = AudioSegment.silent(duration=1000)
        silent.export(outpath, format="mp3")

def build_script_from_files(file_paths):
    """Build podcast script from uploaded files"""
    file_contents = []
    
    for file_path in file_paths:
        text = extract_text_from_file(file_path)
        if text:
            file_contents.append({
                "filename": Path(file_path).name,
                "content": text[:8000],
                "type": "file"
            })
    
    if not file_contents:
        return None, [], None, []
    
    # Create topic preview for intro
    topics = [f["filename"] for f in file_contents]
    topic_preview = f"discussing {', '.join(topics[:2])}" + (f" and {len(topics)-2} more documents" if len(topics) > 2 else "")
    
    # Generate conversation-style script for two hosts
    # Note: No longer including sign-on in the main content since it's handled by custom intro
    main_content_prompt = f"""
    Create the main content for a podcast episode between two hosts discussing uploaded documents.
    Files being discussed: {[f['filename'] for f in file_contents]}
    
    Do NOT include any introductory greetings or sign-ons - just start with the content discussion.
    Make it conversational and engaging. Write as dialogue with HOST1 and HOST2 tags.
    Focus on the key insights and analysis.
    """
    
    segments = []
    for file_content in file_contents:
        seg_prompt = f"""
        Create a 3-4 minute conversational segment between two podcast hosts discussing this document.
        Document: {file_content['filename']}
        Content preview: {file_content['content']}
        
        Write as natural dialogue with HOST1 and HOST2 tags. Include:
        - Key insights and takeaways
        - Different perspectives from each host
        - Questions and reactions
        - Practical implications
        
        Keep it engaging and informative.
        """
        segments.append(llm(seg_prompt))
    
    outro_prompt = f"""
    Create a 30-second podcast outro for two hosts wrapping up their discussion.
    Include: "{CFG['brand']['sign_off']}"
    Write as dialogue with HOST1 and HOST2 tags.
    """
    
    main_content = llm(main_content_prompt)
    outro = llm(outro_prompt)
    
    # Return metadata for intro generation
    metadata = {
        "topic_preview": topic_preview,
        "file_count": len(file_contents),
        "content_type": "file_analysis"
    }
    
    return main_content, segments, outro, file_contents, metadata

def build_script_from_rss(items):
    """Build podcast script from RSS items"""
    bullets = []
    for it in items:
        page = fetch_page_text(it["link"])
        summ = llm(f"Summarize objectively in 3-4 tight bullet points. Title: {it['title']}\n\nSource:\n{page[:4000]}")
        bullets.append({"title": it["title"], "points": summ, "link": it["link"]})
    
    # Create topic preview for intro
    topic_preview = f"covering {len(items)} stories including {bullets[0]['title'][:50]}..." if bullets else "the latest tech news"
    
    # Main content (no sign-on since handled by custom intro)
    main_content_prompt = f"""
    Create the main content introduction for a tech podcast covering today's stories.
    Stories: {[b['title'] for b in bullets]}
    
    Do NOT include any introductory greetings or sign-ons - just start with the content.
    Make it engaging and set up the upcoming segments.
    """
    
    segs = []
    for b in bullets:
        segs.append(llm(
            "Turn this into a ~2 minute spoken segment with a single host. "
            "Lead with why it matters, then the facts, then a takeaway. "
            f"\nTitle: {b['title']}\nBullets:\n{b['points']}\nCite the source URL at the end: {b['link']}"
        ))
    
    outro = llm(f"Write a 20-30s outro. Include: \"{CFG['brand']['sign_off']}\"")
    
    main_content = llm(main_content_prompt)
    
    metadata = {
        "topic_preview": topic_preview,
        "story_count": len(items),
        "content_type": "news_roundup"
    }
    
    return main_content, segs, outro, bullets, metadata

def create_dialogue_audio(script_text, segment_name, epdir):
    """Create audio for dialogue between two hosts"""
    print(f"DEBUG: create_dialogue_audio called for {segment_name}")
    host1_lines, host2_lines = separate_dialogue(script_text)
    print(f"DEBUG: {segment_name} - host1_lines count: {len(host1_lines)}")
    print(f"DEBUG: {segment_name} - host2_lines count: {len(host2_lines)}")
    
    host1_files = []
    host2_files = []
    
    for i, line in enumerate(host1_lines):
        if line.strip():
            temp_file = epdir / f"{segment_name}_host1_{i}.mp3"
            elevenlabs_tts(line, HOST_VOICE_ID, temp_file)
            host1_files.append(temp_file)
    
    for i, line in enumerate(host2_lines):
        if line.strip():
            temp_file = epdir / f"{segment_name}_host2_{i}.mp3"
            elevenlabs_tts(line, COHOST_VOICE_ID, temp_file)
            host2_files.append(temp_file)
    
    final_audio = AudioSegment.silent(duration=0)
    max_segments = max(len(host1_files), len(host2_files))
    
    for i in range(max_segments):
        if i < len(host1_files):
            final_audio += AudioSegment.from_mp3(host1_files[i])
            final_audio += AudioSegment.silent(duration=500)
        
        if i < len(host2_files):
            final_audio += AudioSegment.from_mp3(host2_files[i])
            final_audio += AudioSegment.silent(duration=500)
    
    print(f"DEBUG: {segment_name} - Created {len(host1_files)} host1 files, {len(host2_files)} host2 files")
    print(f"DEBUG: {segment_name} - Final audio length: {len(final_audio)/1000:.1f} seconds")
    
    # Clean up temp files
    for f in host1_files + host2_files:
        f.unlink()
        print(f"DEBUG: Deleted {f.name}")
    
    return final_audio

def separate_dialogue(script_text):
    """Separate dialogue between hosts using configured names"""
    primary_host = CFG.get("hosts", {}).get("primary", {}).get("name", "HOST1")
    secondary_host = CFG.get("hosts", {}).get("secondary", {}).get("name", "HOST2")
    
    lines = script_text.split('\n')
    host1_lines = []
    host2_lines = []
    
    current_speaker = None
    current_text = []
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
            
        # Strip various formatting: **, <>, etc.
        clean_line = line.lstrip('*<').rstrip('>').strip()
        
        # Check for primary host (HOST1 or configured name)
        is_host1 = (clean_line.startswith(f'{primary_host}:') or 
                   clean_line.startswith(f'{primary_host}>') or
                   clean_line.startswith('HOST1:') or 
                   clean_line.startswith('HOST1>'))
        
        # Check for secondary host (HOST2 or configured name)  
        is_host2 = (clean_line.startswith(f'{secondary_host}:') or
                   clean_line.startswith(f'{secondary_host}>') or
                   clean_line.startswith('HOST2:') or
                   clean_line.startswith('HOST2>'))
        
        if is_host1:
            if current_speaker and current_text:
                if current_speaker == 'HOST1':
                    host1_lines.append(' '.join(current_text))
                else:
                    host2_lines.append(' '.join(current_text))
            current_speaker = 'HOST1'
            # Extract text after the speaker tag
            for sep in [':', '>']:
                if sep in clean_line:
                    current_text = [clean_line.split(sep, 1)[1].strip()]
                    break
                    
        elif is_host2:
            if current_speaker and current_text:
                if current_speaker == 'HOST1':
                    host1_lines.append(' '.join(current_text))
                else:
                    host2_lines.append(' '.join(current_text))
            current_speaker = 'HOST2'
            # Extract text after the speaker tag
            for sep in [':', '>']:
                if sep in clean_line:
                    current_text = [clean_line.split(sep, 1)[1].strip()]
                    break
                    
        elif line and current_speaker:
            current_text.append(line)
    
    # Add final segment
    if current_speaker and current_text:
        if current_speaker == 'HOST1':
            host1_lines.append(' '.join(current_text))
        else:
            host2_lines.append(' '.join(current_text))
    
    return host1_lines, host2_lines

def mix_segments(audio_segments, bed_path=None):
    """Mix audio segments with background music"""
    voice = AudioSegment.silent(duration=0)
    for segment in audio_segments:
        voice += segment + AudioSegment.silent(300)
    
    voice = normalize(voice)
    
    if bed_path and Path(bed_path).exists():
        bed = AudioSegment.from_file(bed_path)
        loops = (len(voice) // len(bed)) + 1
        bed_full = (bed * loops)[:len(voice)]
        bed_full = bed_full - 18
        mix = voice.overlay(bed_full)
        return normalize(mix)
    
    return voice

def upload_to_spotify(episode_file, title, description):
    """Upload to Spotify via RSS"""
    print("📡 Spotify will automatically pick up new episodes from RSS feed")
    return True

def upload_to_website(episode_file, metadata):
    """Upload episode and cover image to demetri.xyz"""
    try:
        website_url = os.getenv("WEBSITE_UPLOAD_URL")
        api_key = os.getenv("WEBSITE_API_KEY")
        
        if not website_url:
            print("⚠️  Website upload URL not configured")
            return False
        
        # Prepare files for upload
        files = {}
        
        # Always upload the episode
        with open(episode_file, 'rb') as f:
            files['audio'] = f.read()
        
        # Upload cover image if it exists locally
        cover_path = CFG["output"].get("cover_png")
        if cover_path and Path(cover_path).exists():
            with open(cover_path, 'rb') as f:
                files['cover'] = f.read()
            print(f"📸 Uploading cover image: {cover_path}")
        
        # Upload data
        data = {
            'title': metadata['title'],
            'description': metadata['description'],
            'api_key': api_key
        }
        
        # Convert files back to file-like objects for requests
        upload_files = {}
        if 'audio' in files:
            upload_files['audio'] = ('episode.mp3', files['audio'], 'audio/mpeg')
        if 'cover' in files:
            cover_ext = Path(cover_path).suffix if cover_path else '.png'
            upload_files['cover'] = (f'cover{cover_ext}', files['cover'], 'image/png')
        
        response = requests.post(website_url, files=upload_files, data=data)
        response.raise_for_status()
        
        result = response.json() if response.headers.get('content-type', '').startswith('application/json') else {}
        print(f"✅ Uploaded to demetri.xyz: {result.get('url', 'Success')}")
        
        # Return the cover URL if provided by server
        if 'cover_url' in result:
            return result['cover_url']
        
        return True
        
    except Exception as e:
        print(f"❌ Website upload failed: {e}")
        return False

def post_to_twitter(episode_metadata):
    """Post about new episode on Twitter"""
    try:
        tweet_text = f"""
🎧 New episode of {TITLE} is live!

{episode_metadata['title']}

{episode_metadata.get('summary', episode_metadata['description'][:100])}...

Listen now: {episode_metadata.get('website_url', 'demetri.xyz')}

#podcast #AI #tech
        """.strip()
        
        if len(tweet_text) > 280:
            tweet_text = tweet_text[:277] + "..."
        
        response = twitter_client.create_tweet(text=tweet_text)
        print(f"🐦 Posted to Twitter: {response.data['id']}")
        return True
        
    except Exception as e:
        print(f"❌ Twitter post failed: {e}")
        return False

def write_rss(episode_mp3, title, desc, pubdate, cover_url=None):
    """Generate RSS feed entry"""
    rss_path = OUTDIR / "feed.xml"
    base_url = os.getenv("RSS_SITE", "https://demetri.xyz").rstrip("/")
    item_url = f"{base_url}/podcast/{episode_mp3.name}"
    
    # Use provided cover URL or generate default one
    if cover_url:
        cover_tag = f"<itunes:image href=\"{cover_url}\"/>"
    else:
        # Fallback to default cover URL pattern
        cover_tag = f"<itunes:image href=\"{base_url}/podcast/cover.png\"/>"
    
    existing = rss_path.read_text() if rss_path.exists() else None
    
    header = f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:itunes="http://www.itunes.com/dtds/podcast-1.0.dtd">
<channel>
<title>{TITLE}</title>
<link>{base_url}</link>
<description>{TITLE} — AI-generated discussions on tech, AI, and important documents.</description>
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
        content = existing.replace("</channel>\n</rss>\n", item + footer)
    else:
        content = header + item + footer
    
    rss_path.write_text(content)
    return item_url

def main(uploaded_files=None):
    """Main function - can process either uploaded files or RSS feeds"""
    ts = dt.datetime.utcnow().strftime("%Y%m%d-%H%M")
    epdir = OUTDIR / ts
    epdir.mkdir(parents=True, exist_ok=True)
    
    # Determine content source and build script
    if uploaded_files:
        print(f"📁 Processing {len(uploaded_files)} uploaded files...")
        main_content, segs, outro, sources, metadata = build_script_from_files(uploaded_files)
        content_type = "files"
    else:
        print("📡 Fetching from RSS feeds...")
        items = fetch_recent_items()
        main_content, segs, outro, sources, metadata = build_script_from_rss(items)
        content_type = "rss"
    
    if not main_content:
        print("❌ No content to process")
        return
    
    # Add episode number to metadata
    metadata["episode_number"] = ts
    
    # Create custom intro
    print("🎵 Creating custom intro...")
    custom_intro = create_custom_intro(metadata, epdir)
    
    # Write scripts
    (epdir / "script_intro.txt").write_text(main_content)
    for i, s in enumerate(segs, 1): 
        (epdir / f"script_seg{i}.txt").write_text(s)
    (epdir / "script_outro.txt").write_text(outro)
    (epdir / "sources.json").write_text(json.dumps(sources, indent=2))
    
    # Generate audio
    print("🎙️  Generating audio...")
    print(f"DEBUG: content_type = {content_type}")
    print(f"DEBUG: HOST_VOICE_ID = {HOST_VOICE_ID}")
    print(f"DEBUG: COHOST_VOICE_ID = {COHOST_VOICE_ID}")
    
    # Main content audio
    if content_type == "files" and (HOST_VOICE_ID and COHOST_VOICE_ID):
        main_audio = create_dialogue_audio(main_content, "main", epdir)
        
        seg_audios = []
        for i, s in enumerate(segs, 1):
            seg_audio = create_dialogue_audio(s, f"seg{i}", epdir)
            seg_audios.append(seg_audio)
        
        outro_audio = create_dialogue_audio(outro, "outro", epdir)
    else:
        # Single voice format
        main_mp3 = epdir / "main.mp3"
        elevenlabs_tts(main_content, HOST_VOICE_ID or "default", main_mp3)
        main_audio = AudioSegment.from_mp3(main_mp3)
        
        seg_audios = []
        for i, s in enumerate(segs, 1):
            seg_mp3 = epdir / f"seg{i}.mp3"
            elevenlabs_tts(s, HOST_VOICE_ID or "default", seg_mp3)
            seg_audios.append(AudioSegment.from_mp3(seg_mp3))
        
        outro_mp3 = epdir / "outro.mp3"
        elevenlabs_tts(outro, HOST_VOICE_ID or "default", outro_mp3)
        outro_audio = AudioSegment.from_mp3(outro_mp3)
    
    # Mix final episode with custom intro
    print("🎵 Mixing final episode...")
    final = epdir / f"{TITLE.lower().replace(' ', '_')}_{ts}.mp3"
    
    # Combine: Custom Intro + Main Content + Segments + Outro
    all_segments = [custom_intro, main_audio] + seg_audios + [outro_audio, custom_outro]
    print(f"DEBUG: Mixing {len(all_segments)} segments")
    for i, seg in enumerate(all_segments):
        if seg is not None:
            print(f"DEBUG: Segment {i}: {len(seg)/1000:.1f} seconds")
        else:
            print(f"DEBUG: Segment {i}: None!")
    mix = mix_segments(all_segments, CFG["episode"].get("music_bed_path") or None)
    mix.export(final, format="mp3", bitrate="192k")
    
    # Generate episode metadata
    ep_title = f"{TITLE} — {dt.datetime.utcnow():%b %d, %Y}"
    if content_type == "files":
        desc = f"Deep dive discussion on: {', '.join([s['filename'] for s in sources])}"
    else:
        desc = "Auto-generated episode covering today's top AI/tech stories."
    
    # Upload and distribute
    episode_metadata = {
        'title': ep_title,
        'description': desc,
        'file_path': final,
        'summary': desc
    }
    
    print("🚀 Distributing episode...")
    
    # Upload to website (this also uploads cover image)
    cover_url = upload_to_website(final, episode_metadata)
    
    # Create RSS entry with uploaded cover URL
    print("📡 Updating RSS feed...")
    episode_url = write_rss(final, ep_title, desc, 
                           dt.datetime.utcnow().strftime("%a, %d %b %Y %H:%M:%S +0000"),
                           cover_url if isinstance(cover_url, str) else None)
    
    # Update episode metadata with website URL
    episode_metadata['website_url'] = episode_url
    
    upload_to_spotify(final, ep_title, desc)
    post_to_twitter(episode_metadata)
    
    print(f"\n✅ Episode ready: {final}")
    print(f"📁 Scripts in: {epdir}")
    print(f"🌐 RSS feed: {OUTDIR}/feed.xml")
    print(f"🎧 Listen at: {episode_url}")

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        uploaded_files = sys.argv[1:]
        print(f"Processing uploaded files: {uploaded_files}")
        main(uploaded_files)
    else:
        print("No files provided, processing RSS feeds...")
        main()