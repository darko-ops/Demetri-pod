from flask import Flask, request, jsonify, send_file, render_template_string
from flask_cors import CORS
import os, uuid, subprocess, threading
from pathlib import Path
from werkzeug.utils import secure_filename
import json, time
from main import main as generate_podcast  # Import your main function

app = Flask(__name__)
CORS(app)

# Configuration
UPLOAD_FOLDER = Path('uploads')
UPLOAD_FOLDER.mkdir(exist_ok=True)
ALLOWED_EXTENSIONS = {'pdf', 'txt', 'md', 'doc', 'docx'}

# Store generation jobs
generation_jobs = {}

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

class GenerationJob:
    def __init__(self, job_id):
        self.id = job_id
        self.status = 'pending'
        self.progress = 0
        self.message = 'Initializing...'
        self.files = []
        self.result = None
        self.error = None

@app.route('/')
def index():
    """Serve the web interface"""
    # In a real setup, you'd serve the HTML file directly
    # For now, return a simple message
    return jsonify({"message": "Podcast Generator API Ready"})

@app.route('/api/upload', methods=['POST'])
def upload_files():
    """Handle file uploads"""
    try:
        if 'files' not in request.files:
            return jsonify({'error': 'No files provided'}), 400
        
        files = request.files.getlist('files')
        if not files or all(f.filename == '' for f in files):
            return jsonify({'error': 'No files selected'}), 400
        
        job_id = str(uuid.uuid4())
        job = GenerationJob(job_id)
        
        uploaded_files = []
        for file in files:
            if file and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                # Add timestamp to avoid conflicts
                unique_filename = f"{int(time.time())}_{filename}"
                file_path = UPLOAD_FOLDER / unique_filename
                file.save(file_path)
                uploaded_files.append(str(file_path))
                job.files.append({
                    'original_name': filename,
                    'saved_path': str(file_path),
                    'size': file_path.stat().st_size
                })
        
        if not uploaded_files:
            return jsonify({'error': 'No valid files uploaded'}), 400
        
        generation_jobs[job_id] = job
        
        # Start generation in background
        thread = threading.Thread(
            target=run_generation, 
            args=(job_id, uploaded_files)
        )
        thread.daemon = True
        thread.start()
        
        return jsonify({
            'job_id': job_id,
            'message': 'Files uploaded successfully, generation started',
            'files': [f['original_name'] for f in job.files]
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/generate/rss', methods=['POST'])
def generate_from_rss():
    """Generate podcast from RSS feeds"""
    try:
        job_id = str(uuid.uuid4())
        job = GenerationJob(job_id)
        generation_jobs[job_id] = job
        
        # Start RSS generation in background
        thread = threading.Thread(
            target=run_generation, 
            args=(job_id, None)
        )
        thread.daemon = True
        thread.start()
        
        return jsonify({
            'job_id': job_id,
            'message': 'RSS-based podcast generation started'
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/status/<job_id>')
def get_job_status(job_id):
    """Get generation job status"""
    job = generation_jobs.get(job_id)
    if not job:
        return jsonify({'error': 'Job not found'}), 404
    
    response = {
        'job_id': job_id,
        'status': job.status,
        'progress': job.progress,
        'message': job.message
    }
    
    if job.status == 'completed' and job.result:
        response['result'] = job.result
    elif job.status == 'failed' and job.error:
        response['error'] = job.error
        
    return jsonify(response)

@app.route('/api/download/<job_id>')
def download_episode(job_id):
    """Download generated podcast episode"""
    job = generation_jobs.get(job_id)
    if not job or job.status != 'completed':
        return jsonify({'error': 'Episode not ready'}), 404
    
    if not job.result or 'episode_path' not in job.result:
        return jsonify({'error': 'Episode file not found'}), 404
    
    episode_path = Path(job.result['episode_path'])
    if not episode_path.exists():
        return jsonify({'error': 'Episode file missing'}), 404
    
    return send_file(
        episode_path,
        as_attachment=True,
        download_name=f"{job.result.get('title', 'episode')}.mp3"
    )

@app.route('/api/episodes')
def list_episodes():
    """List all generated episodes"""
    episodes_dir = Path('episodes')
    if not episodes_dir.exists():
        return jsonify({'episodes': []})
    
    episodes = []
    for episode_dir in sorted(episodes_dir.iterdir(), reverse=True):
        if episode_dir.is_dir():
            # Look for the MP3 file
            mp3_files = list(episode_dir.glob('*.mp3'))
            if mp3_files:
                episode_file = mp3_files[0]
                episodes.append({
                    'id': episode_dir.name,
                    'title': episode_file.stem,
                    'created': episode_dir.stat().st_mtime,
                    'size': episode_file.stat().st_size,
                    'duration': None  # Could add duration detection
                })
    
    return jsonify({'episodes': episodes})

def run_generation(job_id, file_paths):
    """Run podcast generation in background"""
    job = generation_jobs[job_id]
    
    try:
        job.status = 'running'
        job.progress = 10
        job.message = 'Starting podcast generation...'
        
        # Update progress periodically (in real implementation)
        progress_steps = [
            (20, 'Extracting text from files...'),
            (30, 'Analyzing content...'),
            (40, 'Generating script with AI...'),
            (60, 'Creating voice audio...'),
            (80, 'Mixing with background music...'),
            (90, 'Uploading to platforms...'),
            (95, 'Finalizing...')
        ]
        
        def update_progress():
            for progress, message in progress_steps:
                if job.status != 'running':
                    return
                job.progress = progress
                job.message = message
                time.sleep(2)  # Simulate work
        
        # Start progress updates in background
        progress_thread = threading.Thread(target=update_progress)
        progress_thread.daemon = True
        progress_thread.start()
        
        # Run the actual generation
        # This calls your main() function from main.py
        if file_paths:
            # Generate from uploaded files
            result = generate_podcast(file_paths)
        else:
            # Generate from RSS feeds
            result = generate_podcast()
        
        # In a real implementation, modify your main() function to return:
        # {
        #     'episode_path': '/path/to/episode.mp3',
        #     'title': 'Episode Title',
        #     'description': 'Episode Description',
        #     'website_url': 'https://demetri.xyz/episode/123',
        #     'rss_url': 'https://demetri.xyz/feed.xml'
        # }
        
        # For now, simulate a result
        timestamp = time.strftime('%Y%m%d-%H%M')
        episode_dir = Path('episodes') / timestamp
        episode_file = episode_dir / f"demetri.xyz_{timestamp}.mp3"
        
        job.result = {
            'episode_path': str(episode_file),
            'title': f"Demetri.xyz — {time.strftime('%b %d, %Y')}",
            'description': 'AI-generated podcast episode',
            'website_url': f"https://demetri.xyz/podcast/{timestamp}",
            'rss_url': 'https://demetri.xyz/feed.xml',
            'twitter_url': 'https://twitter.com/your_handle'
        }
        
        job.status = 'completed'
        job.progress = 100
        job.message = 'Podcast generated successfully!'
        
        # Clean up uploaded files
        if file_paths:
            for file_path in file_paths:
                try:
                    Path(file_path).unlink()
                except:
                    pass
        
    except Exception as e:
        job.status = 'failed'
        job.error = str(e)
        job.message = f'Generation failed: {str(e)}'
        print(f"Generation error: {e}")

@app.route('/api/config')
def get_config():
    """Get configuration options"""
    return jsonify({
        'ai_services': ['gemini', 'openai'],
        'voices': {
            'host': ['your_voice', 'alloy', 'echo', 'nova'],
            'cohost': ['cohost_voice', 'fable', 'onyx', 'shimmer']
        },
        'max_file_size': 50 * 1024 * 1024,  # 50MB
        'allowed_extensions': list(ALLOWED_EXTENSIONS)
    })

@app.route('/webhook/spotify', methods=['POST'])
def spotify_webhook():
    """Handle Spotify webhook notifications"""
    # Spotify doesn't have direct upload, but you could use this
    # for other podcast platform webhooks
    data = request.get_json()
    print(f"Received webhook: {data}")
    return jsonify({'status': 'received'})

if __name__ == '__main__':
    print("🎧 Podcast Generator API starting...")
    print("📁 Upload endpoint: POST /api/upload")
    print("📡 RSS generation: POST /api/generate/rss")
    print("📊 Status check: GET /api/status/<job_id>")
    print("⬇️  Download: GET /api/download/<job_id>")
    print("📋 Episodes: GET /api/episodes")
    
    # Run in development mode
    app.run(debug=True, host='0.0.0.0', port=5000)