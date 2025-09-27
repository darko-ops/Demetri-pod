# Demetri-pod 🎧

An AI-powered podcast generator that automatically creates tech/AI news podcasts by fetching RSS feeds, generating scripts with GPT-4, and producing audio with text-to-speech.

## Features

- **Automated Content Curation**: Fetches stories from RSS feeds (Hacker News, The Verge, arXiv AI papers)
- **Smart Filtering**: Filters content based on keywords (AI, intelligence, agents, privacy, law, security, crypto)
- **AI Script Generation**: Uses GPT-4o-mini to create engaging podcast scripts with intro, segments, and outro
- **Text-to-Speech**: Generates high-quality audio using OpenAI's TTS API
- **Audio Mixing**: Combines voice tracks with background music
- **RSS Feed Generation**: Creates podcast RSS feeds for distribution
- **Episode Management**: Organizes episodes with timestamps and metadata

## Quick Start

### Prerequisites

- Python 3.8+
- OpenAI API key
- Audio files for background music (optional)

### Installation

1. Clone the repository:
```bash
git clone https://github.com/darko-ops/Demetri-pod.git
cd Demetri-pod
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Set up environment variables:
```bash
cp .env.example .env
# Edit .env with your API keys and configuration
```

### Configuration

Edit `config.yaml` to customize:

- **RSS Feeds**: Add or modify RSS feed URLs
- **Filters**: Adjust keyword filters for content inclusion/exclusion
- **Branding**: Customize sign-on/sign-off messages
- **Audio**: Set background music path and episode duration

Example configuration:
```yaml
feeds:
  - https://news.ycombinator.com/rss
  - https://www.theverge.com/rss/index.xml
  - https://arxiv.org/rss/cs.AI

filters:
  include_keywords: ["AI","intelligence","agents","privacy","law","security","crypto"]
  exclude_keywords: ["rumor","giveaway"]

brand:
  sign_on: "You're listening to Demetri dot xyz — the intelligence you need."
  sign_off: "Thanks for listening. Subscribe and share."
```

### Environment Variables

Create a `.env` file with:

```bash
# Required
OPENAI_API_KEY=your_openai_api_key_here

# Optional
PODCAST_TITLE=Demetri.xyz
HOST_VOICE=alloy
MAX_STORIES=4
RSS_SITE=https://your-domain.com
RSS_EMAIL=your-email@example.com
RSS_AUTHOR=Your Name
```

### Usage

Run the podcast generator:

```bash
python main.py
```

This will:
1. Fetch recent stories from configured RSS feeds
2. Generate podcast scripts using AI
3. Create audio files with text-to-speech
4. Mix audio with background music
5. Generate RSS feed entry
6. Save everything to the `episodes/` directory

### Output Structure

Each episode creates a timestamped directory:

```
episodes/
└── 20241201-1430/
    ├── script_intro.txt
    ├── script_seg1.txt
    ├── script_seg2.txt
    ├── script_outro.txt
    ├── sources.json
    ├── intro.mp3
    ├── seg1.mp3
    ├── seg2.mp3
    ├── outro.mp3
    └── demetri.xyz_20241201-1430.mp3
```

## Customization

### Adding New RSS Feeds

Edit `config.yaml` and add URLs to the `feeds` list:

```yaml
feeds:
  - https://your-custom-feed.com/rss
```

### Changing Voice

Set the `HOST_VOICE` environment variable to one of:
- `alloy` (default)
- `echo`
- `fable`
- `onyx`
- `nova`
- `shimmer`

### Modifying Content Filters

Adjust the keyword filters in `config.yaml`:

```yaml
filters:
  include_keywords: ["your", "keywords", "here"]
  exclude_keywords: ["unwanted", "terms"]
```

## RSS Feed Distribution

The generated `feed.xml` can be used with:
- **Castopod**: Self-hosted podcast platform
- **Spotify for Podcasters**: Import RSS feed
- **Apple Podcasts**: Submit RSS feed
- **Google Podcasts**: Submit RSS feed

## Architecture

- **Content Fetching**: `fetch_recent_items()` - RSS parsing and filtering
- **Content Processing**: `fetch_page_text()` - Web scraping and text extraction
- **AI Generation**: `llm()` - GPT-4 integration for script generation
- **Audio Production**: `tts()` and `mix_segments()` - TTS and audio mixing
- **Distribution**: `write_rss()` - RSS feed generation

## Dependencies

- `openai`: GPT-4 and TTS API integration
- `requests`: HTTP requests for RSS feeds and web scraping
- `beautifulsoup4`: HTML parsing for content extraction
- `feedparser`: RSS feed parsing
- `pydub`: Audio processing and mixing
- `pyyaml`: Configuration file parsing
- `python-dotenv`: Environment variable management

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

## License

This project is open source. See the repository for license details.

## Support

For issues and questions:
- Open an issue on GitHub
- Check the configuration examples
- Review the logs in the `logs/` directory

---

**Demetri.xyz** - The intelligence you need. 🎧
