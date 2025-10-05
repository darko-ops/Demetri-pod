# Enhanced AI Podcast Generator Setup & Usage

## 🚀 New Features

1. **File Upload Support** - Generate podcasts from PDFs, docs, and text files
2. **ElevenLabs Integration** - Use your cloned voices for more natural speech
3. **Multi-Host Support** - Create conversations between two hosts
4. **Gemini AI Support** - Use Google's Gemini for script generation
5. **Auto Distribution** - Automatically upload to Spotify and post on Twitter
6. **Website Integration** - Upload directly to demetri.xyz

## 📋 Prerequisites

### API Keys Needed:
1. **OpenAI API Key** (backup for TTS/text generation)
2. **Gemini API Key** (primary text generation)
3. **ElevenLabs API Key** (voice cloning/TTS)
4. **Twitter API Keys** (auto-posting)
5. **Website API Key** (for demetri.xyz uploads)

### Voice Setup:
1. Clone your voice in ElevenLabs
2. Clone a cohost voice (or use a preset voice)
3. Note the Voice IDs for your .env file

## 🛠️ Installation

1. **Install Dependencies:**
```bash
pip install -r requirements.txt
```

2. **Set Up Environment Variables:**
```bash
cp .env.example .env
# Edit .env with your API keys and voice IDs
```

3. **Configure Voice IDs in ElevenLabs:**
   - Go to ElevenLabs dashboard
   - Find your cloned voice IDs
   - Add them to your .env file

## 🎙️ Usage

### Method 1: File-Based Podcasts (New!)

Generate a podcast from uploaded documents:

```bash
# Single file
python main.py "/path/to/situational-awareness.pdf"

# Multiple files
python main.py "file1.pdf" "file2.txt" "paper.docx"
```

**Supported formats:**
- PDF (.pdf)
- Text (.txt, .md)
- Word (.docx)

### Method 2: RSS-Based Podcasts (Original)

Generate from RSS feeds (no arguments):

```bash
python main.py
```

This will fetch from your configured RSS feeds in `config.yaml`.

## 🔧 Configuration

### Voice Configuration

In your `.env` file:
```bash
# Your cloned voice (main host)
ELEVENLABS_HOST_VOICE_ID=pNInz6obpgDQGcFmaJgB

# Cohost voice (cloned or preset)
ELEVENLABS_COHOST_VOICE_ID=ErXwobaYiN019PkySvjV

# Choose AI service
AI_SERVICE=gemini  # or "openai"
```

### Twitter Auto-Posting

Set up Twitter API v2 access:
1. Go to [Twitter Developer Portal](https://developer.twitter.com/)
2. Create an app and get your keys
3. Add to `.env` file

### Website Upload

Create an upload endpoint on demetri.xyz:
```bash
WEBSITE_UPLOAD_URL=https://demetri.xyz/api/upload-podcast
WEBSITE_API_KEY=your_secret_key
```

## 📁 Output Structure

Each episode creates:
```
episodes/20241201-1430/
├── script_intro.txt          # Intro script
├── script_seg1.txt           # Segment scripts
├── script_seg2.txt
├── script_outro.txt          # Outro script
├── sources.json              # Source metadata
└── demetri.xyz_20241201-1430.mp3  # Final episode
```

## 🎧 Distribution Flow

1. **RSS Feed** - Updated automatically in `episodes/feed.xml`
2. **Spotify** - Reads from your RSS feed (no direct upload needed)
3. **Website** - Uploads via your API endpoint
4. **Twitter** - Auto-posts announcement with link

## 🔍 Example Workflows

### Discuss a Research Paper
```bash
python main.py "papers/gpt4-technical-report.pdf"
```
Creates a 2-host conversation analyzing the paper.

### Weekly News Roundup
```bash
python main.py
```
Generates single-host episode from RSS feeds.

### Multiple Document Analysis
```bash
python main.py "report1.pdf" "analysis.txt" "whitepaper.pdf"
```
Creates segments discussing each document.

## 🎛️ Advanced Options

### Custom Prompts

Modify the script generation prompts in `main.py`:
- `intro_prompt` - Episode introduction
- `seg_prompt` - Segment generation
- `outro_prompt` - Episode conclusion

### Audio Processing

Adjust in `config.yaml`:
```yaml
episode:
  target_minutes: 15        # Target length
  music_bed_path: "assets/bg_bed.mp3"
```

### Voice Settings

Fine-tune ElevenLabs voices:
```python
# In the elevenlabs_tts function
voice_settings = VoiceSettings(
    stability=0.75,
    similarity_boost=0.85,
    style=0.2
)
```

## 🚨 Troubleshooting

### Common Issues:

1. **API Rate Limits**
   - ElevenLabs: 10,000 chars/month on free tier
   - Gemini: Has generous free tier
   - Solution: Monitor usage, add error handling

2. **Voice Quality**
   - Ensure high-quality voice clones in ElevenLabs
   - Use clear source audio for cloning
   - Adjust voice settings for consistency

3. **File Processing**
   - Large PDFs may hit token limits
   - Solution: Automatic chunking to 8000 chars per file

4. **Twitter Posting**
   - Need Twitter API v2 access
   - Character limits enforced automatically

### Debug Mode

Add logging for debugging:
```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

## 📈 Usage Tips

1. **File Naming** - Use descriptive names for uploaded files
2. **Voice Consistency** - Test voice settings before long episodes
3. **Content Length** - Optimal file size: 2-10 pages for good discussion
4. **Backup Strategy** - Original files and OpenAI TTS as fallbacks

## 🔄 Future Enhancements

- Support for more file formats (PowerPoint, etc.)
- Dynamic conversation flow based on content
- Integration with more platforms (YouTube, etc.)
- Real-time voice cloning improvements
- Custom voice training for better consistency

## 🆘 Support

For issues:
1. Check the logs in console output
2. Verify all API keys are valid
3. Test with smaller files first
4. Check ElevenLabs voice availability

---

**Ready to create AI-powered podcasts with your voice!** 🎧✨

source venv/bin/activate