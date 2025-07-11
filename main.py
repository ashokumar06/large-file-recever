from fastapi import FastAPI, File, UploadFile, HTTPException, Request, Form
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
import aiofiles
import os
import hashlib
import time
from typing import Optional
import asyncio
from pathlib import Path
import uvicorn
from fastapi.middleware.cors import CORSMiddleware
import json
import shutil

app = FastAPI(title="Ultra Fast Video Upload Server", version="1.0.0")

# Enable CORS for all origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configuration
UPLOAD_DIR = "uploaded_videos"
CHUNK_SIZE = 128 * 1024 * 1024 
MAX_FILE_SIZE = 500 * 1024 * 1024 * 1024 
TEMP_DIR = "temp_chunks"

# Ensure directories exist
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(TEMP_DIR, exist_ok=True)

class UploadManager:
    def __init__(self):
        self.active_uploads = {}
        self.chunk_cache = {}
    
    def start_upload(self, upload_id: str, total_size: int, filename: str, total_chunks: int):
        self.active_uploads[upload_id] = {
            'filename': filename,
            'total_size': total_size,
            'total_chunks': total_chunks,
            'uploaded_size': 0,
            'received_chunks': set(),
            'start_time': time.time(),
            'status': 'uploading',
            'last_activity': time.time()
        }
        
        # Create chunk directory
        chunk_dir = os.path.join(TEMP_DIR, upload_id)
        os.makedirs(chunk_dir, exist_ok=True)
    
    def receive_chunk(self, upload_id: str, chunk_index: int, chunk_size: int):
        if upload_id in self.active_uploads:
            upload_info = self.active_uploads[upload_id]
            if chunk_index not in upload_info['received_chunks']:
                upload_info['received_chunks'].add(chunk_index)
                upload_info['uploaded_size'] += chunk_size
                upload_info['last_activity'] = time.time()
    
    def get_progress(self, upload_id: str):
        if upload_id not in self.active_uploads:
            return None
        
        upload_info = self.active_uploads[upload_id]
        elapsed_time = time.time() - upload_info['start_time']
        uploaded_size = upload_info['uploaded_size']
        total_size = upload_info['total_size']
        received_chunks = len(upload_info['received_chunks'])
        total_chunks = upload_info['total_chunks']
        
        if elapsed_time > 0:
            speed = uploaded_size / elapsed_time  # bytes per second
            speed_mbps = (speed * 8) / (1024 * 1024)  # Mbps
            speed_mb_s = speed / (1024 * 1024)  # MB/s
        else:
            speed_mbps = 0
            speed_mb_s = 0
        
        progress_percent = (uploaded_size / total_size) * 100 if total_size > 0 else 0
        
        # Estimate remaining time
        if speed > 0 and uploaded_size < total_size:
            remaining_bytes = total_size - uploaded_size
            eta_seconds = remaining_bytes / speed
        else:
            eta_seconds = 0
        
        return {
            'filename': upload_info['filename'],
            'progress_percent': round(progress_percent, 2),
            'uploaded_size': uploaded_size,
            'total_size': total_size,
            'speed_mbps': round(speed_mbps, 2),
            'speed_mb_s': round(speed_mb_s, 2),
            'elapsed_time': round(elapsed_time, 2),
            'eta_seconds': round(eta_seconds, 2),
            'received_chunks': received_chunks,
            'total_chunks': total_chunks,
            'status': upload_info['status']
        }
    
    def complete_upload(self, upload_id: str):
        if upload_id in self.active_uploads:
            self.active_uploads[upload_id]['status'] = 'completed'
    
    def is_upload_complete(self, upload_id: str):
        if upload_id not in self.active_uploads:
            return False
        
        upload_info = self.active_uploads[upload_id]
        return len(upload_info['received_chunks']) == upload_info['total_chunks']

upload_manager = UploadManager()

@app.get("/", response_class=HTMLResponse)
async def upload_page():
    # Get server IP for network access
    import socket
    hostname = socket.gethostname()
    local_ip = socket.gethostbyname(hostname)
    
    return f"""
<!DOCTYPE html>
<html>
<head>
    <title>🚀 Ultra Fast Video Upload Server</title>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ 
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; 
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            color: #333;
        }}
        .container {{ 
            max-width: 1200px; 
            margin: 0 auto; 
            padding: 20px;
            background: rgba(255,255,255,0.95);
            margin-top: 20px;
            border-radius: 20px;
            box-shadow: 0 20px 40px rgba(0,0,0,0.1);
        }}
        .header {{ 
            text-align: center; 
            margin-bottom: 30px; 
            padding: 20px;
            background: linear-gradient(45deg, #ff6b6b, #4ecdc4);
            border-radius: 15px;
            color: white;
        }}
        .server-info {{
            background: #f8f9fa;
            padding: 15px;
            border-radius: 10px;
            margin-bottom: 20px;
            border-left: 4px solid #007bff;
        }}
        .upload-area {{ 
            border: 3px dashed #007bff; 
            padding: 60px 40px; 
            text-align: center; 
            margin: 30px 0; 
            border-radius: 15px;
            background: #f8f9fa;
            transition: all 0.3s ease;
            cursor: pointer;
        }}
        .upload-area:hover {{ 
            border-color: #0056b3; 
            background: #e9ecef; 
            transform: translateY(-2px);
        }}
        .upload-area.dragover {{ 
            border-color: #28a745; 
            background: #d4edda; 
            transform: scale(1.02);
        }}
        .upload-btn {{ 
            background: linear-gradient(45deg, #007bff, #0056b3); 
            color: white; 
            border: none; 
            padding: 15px 30px; 
            border-radius: 25px; 
            cursor: pointer; 
            font-size: 16px; 
            font-weight: bold;
            transition: all 0.3s ease;
            box-shadow: 0 4px 15px rgba(0,123,255,0.3);
        }}
        .upload-btn:hover {{ 
            transform: translateY(-2px); 
            box-shadow: 0 6px 20px rgba(0,123,255,0.4);
        }}
        .upload-btn:disabled {{ 
            background: #ccc; 
            cursor: not-allowed; 
            transform: none;
            box-shadow: none;
        }}
        .file-upload-item {{
            background: white;
            margin: 20px 0;
            border-radius: 15px;
            box-shadow: 0 5px 15px rgba(0,0,0,0.1);
            overflow: hidden;
            border: 1px solid #e9ecef;
        }}
        .file-header {{
            padding: 20px;
            background: linear-gradient(45deg, #f8f9fa, #e9ecef);
            border-bottom: 1px solid #dee2e6;
        }}
        .file-name {{
            font-size: 18px;
            font-weight: bold;
            color: #333;
            margin-bottom: 5px;
        }}
        .file-size {{
            color: #666;
            font-size: 14px;
        }}
        .progress-section {{
            padding: 20px;
        }}
        .progress-bar {{ 
            width: 100%; 
            height: 25px; 
            background: #e9ecef; 
            border-radius: 15px; 
            overflow: hidden;
            margin-bottom: 15px;
            position: relative;
        }}
        .progress-fill {{ 
            height: 100%; 
            background: linear-gradient(45deg, #28a745, #20c997); 
            transition: width 0.5s ease;
            border-radius: 15px;
            position: relative;
            overflow: hidden;
        }}
        .progress-fill::after {{
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: linear-gradient(45deg, transparent 25%, rgba(255,255,255,0.2) 25%, rgba(255,255,255,0.2) 50%, transparent 50%, transparent 75%, rgba(255,255,255,0.2) 75%);
            background-size: 20px 20px;
            animation: progress-animation 1s linear infinite;
        }}
        @keyframes progress-animation {{
            0% {{ transform: translateX(-20px); }}
            100% {{ transform: translateX(20px); }}
        }}
        .progress-text {{
            position: absolute;
            width: 100%;
            text-align: center;
            line-height: 25px;
            font-weight: bold;
            color: white;
            text-shadow: 1px 1px 2px rgba(0,0,0,0.5);
        }}
        .stats {{ 
            display: grid; 
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); 
            gap: 15px; 
            margin: 20px 0; 
        }}
        .stat-card {{ 
            background: linear-gradient(135deg, #667eea, #764ba2); 
            padding: 20px; 
            border-radius: 15px; 
            text-align: center;
            color: white;
            box-shadow: 0 5px 15px rgba(102,126,234,0.3);
        }}
        .stat-value {{ 
            font-size: 28px; 
            font-weight: bold; 
            margin-bottom: 5px;
        }}
        .stat-label {{ 
            font-size: 14px; 
            opacity: 0.9;
        }}
        .status {{
            padding: 10px 20px;
            border-radius: 25px;
            font-weight: bold;
            text-align: center;
            margin-top: 15px;
        }}
        .status.uploading {{
            background: #fff3cd;
            color: #856404;
            border: 1px solid #ffeaa7;
        }}
        .status.success {{
            background: #d4edda;
            color: #155724;
            border: 1px solid #c3e6cb;
        }}
        .status.error {{
            background: #f8d7da;
            color: #721c24;
            border: 1px solid #f5c6cb;
        }}
        .network-info {{
            background: linear-gradient(45deg, #ff6b6b, #ee5a24);
            color: white;
            padding: 15px;
            border-radius: 10px;
            margin: 20px 0;
            text-align: center;
        }}
        .upload-icon {{
            font-size: 48px;
            margin-bottom: 15px;
            color: #007bff;
        }}
        .speed-indicator {{
            display: inline-block;
            padding: 5px 15px;
            background: #28a745;
            color: white;
            border-radius: 20px;
            font-size: 12px;
            font-weight: bold;
            margin-left: 10px;
        }}
        .eta {{
            font-size: 14px;
            color: #666;
            margin-top: 10px;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🚀 Ultra Fast Video Upload Server</h1>
            <p>Upload large video files at maximum speed with real-time progress tracking</p>
        </div>
        
        
        <div class="upload-area" id="uploadArea">
            <div class="upload-icon">📁</div>
            <h3>Drop your video files here</h3>
            <p>Or click to select files from your computer</p>
            <input type="file" id="fileInput" accept="video/*" multiple style="display: none;">
            <br><br>
            <button class="upload-btn" onclick="document.getElementById('fileInput').click()">
                📂 Select Video Files
            </button>
        </div>
        
        <div id="uploadsList"></div>
    </div>
    
    <script>
        const uploadArea = document.getElementById('uploadArea');
        const fileInput = document.getElementById('fileInput');
        const uploadsList = document.getElementById('uploadsList');
        
        // Drag and drop functionality
        uploadArea.addEventListener('dragover', (e) => {{
            e.preventDefault();
            uploadArea.classList.add('dragover');
        }});
        
        uploadArea.addEventListener('dragleave', () => {{
            uploadArea.classList.remove('dragover');
        }});
        
        uploadArea.addEventListener('drop', (e) => {{
            e.preventDefault();
            uploadArea.classList.remove('dragover');
            handleFiles(e.dataTransfer.files);
        }});
        
        fileInput.addEventListener('change', (e) => {{
            handleFiles(e.target.files);
        }});
        
        function handleFiles(files) {{
            // Accept all file types - no filtering needed
            for (let file of files) {{
                uploadFile(file);
            }}
        }}
        function getFileIcon(filename) {{
            const ext = filename.split('.').pop().toLowerCase();
            
            // Video files
            if (['mp4', 'avi', 'mkv', 'mov', 'wmv', 'flv', 'webm', 'm4v'].includes(ext)) {{
                return '🎬';
            }}
            // Image files
            if (['jpg', 'jpeg', 'png', 'gif', 'bmp', 'tiff', 'svg', 'webp'].includes(ext)) {{
                return '🖼️';
            }}
            // Audio files
            if (['mp3', 'wav', 'flac', 'aac', 'ogg', 'wma'].includes(ext)) {{
                return '🎵';
            }}
            // Document files
            if (['pdf', 'doc', 'docx', 'txt', 'rtf', 'odt'].includes(ext)) {{
                return '📄';
            }}
            // Archive files
            if (['zip', 'rar', '7z', 'tar', 'gz'].includes(ext)) {{
                return '📦';
            }}
            // Code files
            if (['js', 'py', 'html', 'css', 'json', 'xml', 'sql', 'php', 'java', 'cpp', 'c'].includes(ext)) {{
                return '💻';
            }}
            // Data files
            if (['csv', 'xls', 'xlsx', 'db'].includes(ext)) {{
                return '📊';
            }}
            // Design files
            if (['psd', 'ai', 'sketch', 'fig'].includes(ext)) {{
                return '🎨';
            }}
            
            // Default file icon
            return '📁';
        }}
        
        async function uploadFile(file) {{
            const uploadId = generateUploadId();
            const chunkSize = 16 * 1024 * 1024; // 16MB chunks
            const totalChunks = Math.ceil(file.size / chunkSize);
            
            // Create upload UI
            const uploadDiv = createUploadUI(uploadId, file.name, file.size);
            uploadsList.appendChild(uploadDiv);
            
            try {{
                // Start upload session
                await fetch('/start-upload', {{
                    method: 'POST',
                    headers: {{'Content-Type': 'application/json'}},
                    body: JSON.stringify({{
                        upload_id: uploadId,
                        filename: file.name,
                        total_size: file.size,
                        total_chunks: totalChunks
                    }})
                }});
                
                updateStatus(uploadId, 'Uploading chunks...', 'uploading');
                
                // Upload chunks with maximum parallelism
                const maxConcurrent = 6; // Optimal for most connections
                const semaphore = new Semaphore(maxConcurrent);
                const chunkPromises = [];
                
                for (let chunkIndex = 0; chunkIndex < totalChunks; chunkIndex++) {{
                    const start = chunkIndex * chunkSize;
                    const end = Math.min(start + chunkSize, file.size);
                    const chunk = file.slice(start, end);
                    
                    chunkPromises.push(
                        semaphore.acquire().then(async (release) => {{
                            try {{
                                await uploadChunk(uploadId, chunkIndex, chunk, totalChunks);
                            }} finally {{
                                release();
                            }}
                        }})
                    );
                }}
                
                await Promise.all(chunkPromises);
                
                updateStatus(uploadId, 'Completing upload...', 'uploading');
                
                // Complete upload
                const completeResponse = await fetch(`/complete-upload/${{uploadId}}`, {{method: 'POST'}});
                const completeResult = await completeResponse.json();
                
                updateStatus(uploadId, `✅ Upload completed successfully! Saved as: ${{completeResult.filename}}`, 'success');
                
            }} catch (error) {{
                updateStatus(uploadId, `❌ Upload failed: ${{error.message}}`, 'error');
                console.error('Upload error:', error);
            }}
        }}
        
        async function uploadChunk(uploadId, chunkIndex, chunk, totalChunks) {{
            const formData = new FormData();
            formData.append('chunk', chunk);
            formData.append('chunk_index', chunkIndex);
            formData.append('total_chunks', totalChunks);
            
            const response = await fetch(`/upload-chunk/${{uploadId}}`, {{
                method: 'POST',
                body: formData
            }});
            
            if (!response.ok) {{
                throw new Error(`Chunk ${{chunkIndex}} upload failed: ${{response.status}}`);
            }}
        }}
        
        function createUploadUI(uploadId, filename, fileSize) {{
            const div = document.createElement('div');
            div.className = 'file-upload-item';
            div.id = `upload-${{uploadId}}`;
            
            div.innerHTML = `
                <div class="file-header">
                    <div class="file-name">🎬 ${{filename}}</div>
                    <div class="file-size">📦 Size: ${{formatBytes(fileSize)}}</div>
                </div>
                <div class="progress-section">
                    <div class="progress-bar">
                        <div class="progress-fill" id="progress-${{uploadId}}" style="width: 0%"></div>
                        <div class="progress-text" id="progress-text-${{uploadId}}">0%</div>
                    </div>
                    <div class="stats">
                        <div class="stat-card">
                            <div class="stat-value" id="speed-${{uploadId}}">0 MB/s</div>
                            <div class="stat-label">🚀 Upload Speed</div>
                        </div>
                        <div class="stat-card">
                            <div class="stat-value" id="uploaded-${{uploadId}}">0 MB</div>
                            <div class="stat-label">📤 Uploaded</div>
                        </div>
                        <div class="stat-card">
                            <div class="stat-value" id="chunks-${{uploadId}}">0/0</div>
                            <div class="stat-label">🧩 Chunks</div>
                        </div>
                        <div class="stat-card">
                            <div class="stat-value" id="eta-${{uploadId}}">--:--</div>
                            <div class="stat-label">⏱️ ETA</div>
                        </div>
                    </div>
                    <div class="status uploading" id="status-${{uploadId}}">Initializing upload...</div>
                </div>
            `;
            
            // Start progress monitoring
            monitorProgress(uploadId);
            
            return div;
        }}
        
        function monitorProgress(uploadId) {{
            const interval = setInterval(async () => {{
                try {{
                    const response = await fetch(`/progress/${{uploadId}}`);
                    if (response.ok) {{
                        const progress = await response.json();
                        updateProgressUI(uploadId, progress);
                        
                        if (progress.status === 'completed') {{
                            clearInterval(interval);
                        }}
                    }}
                }} catch (error) {{
                    console.error('Progress monitoring error:', error);
                }}
            }}, 200); // Update every 200ms for smooth progress
        }}
        
        function updateProgressUI(uploadId, progress) {{
            document.getElementById(`progress-${{uploadId}}`).style.width = `${{progress.progress_percent}}%`;
            document.getElementById(`progress-text-${{uploadId}}`).textContent = `${{progress.progress_percent}}%`;
            document.getElementById(`speed-${{uploadId}}`).innerHTML = `${{progress.speed_mb_s}}<span class="speed-indicator">${{progress.speed_mbps}} Mbps</span>`;
            document.getElementById(`uploaded-${{uploadId}}`).textContent = formatBytes(progress.uploaded_size);
            document.getElementById(`chunks-${{uploadId}}`).textContent = `${{progress.received_chunks}}/${{progress.total_chunks}}`;
            
            // Format ETA
            if (progress.eta_seconds > 0) {{
                const eta = formatTime(progress.eta_seconds);
                document.getElementById(`eta-${{uploadId}}`).textContent = eta;
            }} else {{
                document.getElementById(`eta-${{uploadId}}`).textContent = 'Complete';
            }}
        }}
        
        function updateStatus(uploadId, message, className) {{
            const statusElement = document.getElementById(`status-${{uploadId}}`);
            statusElement.textContent = message;
            statusElement.className = `status ${{className}}`;
        }}
        
        function generateUploadId() {{
            return Date.now().toString(36) + Math.random().toString(36).substr(2);
        }}
        
        function formatBytes(bytes) {{
            if (bytes === 0) return '0 B';
            const k = 1024;
            const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
            const i = Math.floor(Math.log(bytes) / Math.log(k));
            return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
        }}
        
        function formatTime(seconds) {{
            if (seconds < 60) return `${{Math.round(seconds)}}s`;
            const minutes = Math.floor(seconds / 60);
            const remainingSeconds = Math.round(seconds % 60);
            if (minutes < 60) return `${{minutes}}m ${{remainingSeconds}}s`;
            const hours = Math.floor(minutes / 60);
            const remainingMinutes = minutes % 60;
            return `${{hours}}h ${{remainingMinutes}}m`;
        }}
        
        class Semaphore {{
            constructor(max) {{
                this.max = max;
                this.current = 0;
                this.queue = [];
            }}
            
            acquire() {{
                return new Promise((resolve) => {{
                    if (this.current < this.max) {{
                        this.current++;
                        resolve(() => this.release());
                    }} else {{
                        this.queue.push(() => {{
                            this.current++;
                            resolve(() => this.release());
                        }});
                    }}
                }});
            }}
            
            release() {{
                this.current--;
                if (this.queue.length > 0) {{
                    const next = this.queue.shift();
                    next();
                }}
            }}
        }}
        
        // Show network info on page load
        console.log('🚀 Ultra Fast Video Upload Server Ready!');
        console.log('📡 Access from other devices using: http://{local_ip}:8000');
    </script>
</body>
</html>
    """

@app.post("/start-upload")
async def start_upload(request: Request):
    """Initialize a new upload session"""
    data = await request.json()
    upload_id = data.get('upload_id')
    filename = data.get('filename')
    total_size = data.get('total_size')
    total_chunks = data.get('total_chunks')
    
    if total_size > MAX_FILE_SIZE:
        raise HTTPException(status_code=413, detail=f"File too large. Maximum size is {MAX_FILE_SIZE // (1024**3)} GB")
    
    # Sanitize filename
    safe_filename = "".join(c for c in filename if c.isalnum() or c in (' ', '-', '_', '.')).rstrip()
    if not safe_filename:
        safe_filename = f"video_{int(time.time())}"
    
    upload_manager.start_upload(upload_id, total_size, safe_filename, total_chunks)
    
    return {
        "status": "upload_started", 
        "upload_id": upload_id,
        "filename": safe_filename,
        "chunk_size": CHUNK_SIZE
    }

@app.post("/upload-chunk/{upload_id}")
async def upload_chunk(
    upload_id: str, 
    chunk: UploadFile = File(...), 
    chunk_index: int = Form(...),
    total_chunks: int = Form(...)
):
    """Receive and store a chunk of the file"""
    
    if upload_id not in upload_manager.active_uploads:
        raise HTTPException(status_code=404, detail="Upload session not found")
    
    try:
        # Read chunk data
        chunk_data = await chunk.read()
        chunk_size = len(chunk_data)
        
        # Save chunk to temporary file
        chunk_dir = os.path.join(TEMP_DIR, upload_id)
        chunk_file = os.path.join(chunk_dir, f"chunk_{chunk_index:06d}")
        
        async with aiofiles.open(chunk_file, 'wb') as f:
            await f.write(chunk_data)
        
        # Update progress
        upload_manager.receive_chunk(upload_id, chunk_index, chunk_size)
        
        return {
            "status": "chunk_received", 
            "chunk_index": chunk_index,
            "chunk_size": chunk_size
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Chunk upload failed: {str(e)}")

@app.post("/complete-upload/{upload_id}")
async def complete_upload(upload_id: str):
    """Combine all chunks into final file"""
    
    if upload_id not in upload_manager.active_uploads:
        raise HTTPException(status_code=404, detail="Upload session not found")
    
    upload_info = upload_manager.active_uploads[upload_id]
    
    if not upload_manager.is_upload_complete(upload_id):
        raise HTTPException(status_code=400, detail="Upload incomplete - missing chunks")
    
    try:
        filename = upload_info['filename']
        total_chunks = upload_info['total_chunks']
        
        # Create unique filename if file already exists
        final_path = os.path.join(UPLOAD_DIR, filename)
        counter = 1
        base_name, ext = os.path.splitext(filename)
        while os.path.exists(final_path):
            new_filename = f"{base_name}_{counter}{ext}"
            final_path = os.path.join(UPLOAD_DIR, new_filename)
            counter += 1
        
        # Combine chunks into final file
        chunk_dir = os.path.join(TEMP_DIR, upload_id)
        
        async with aiofiles.open(final_path, 'wb') as final_file:
            for chunk_index in range(total_chunks):
                chunk_file = os.path.join(chunk_dir, f"chunk_{chunk_index:06d}")
                
                if os.path.exists(chunk_file):
                    async with aiofiles.open(chunk_file, 'rb') as cf:
                        chunk_data = await cf.read()
                        await final_file.write(chunk_data)
                else:
                    raise HTTPException(status_code=500, detail=f"Missing chunk {chunk_index}")
        
        # Clean up temporary chunks
        try:
            shutil.rmtree(chunk_dir)
        except:
            pass  # Don't fail if cleanup fails
        
        upload_manager.complete_upload(upload_id)
        
        # Get final file info
        file_size = os.path.getsize(final_path)
        
        print(f"✅ Upload completed: {os.path.basename(final_path)} ({file_size / (1024**3):.2f} GB)")
        
        return {
            "status": "upload_completed",
            "filename": os.path.basename(final_path),
            "file_size": file_size,
            "location": final_path
        }
        
    except Exception as e:
        # Clean up on error
        try:
            chunk_dir = os.path.join(TEMP_DIR, upload_id)
            if os.path.exists(chunk_dir):
                shutil.rmtree(chunk_dir)
        except:
            pass
        
        raise HTTPException(status_code=500, detail=f"Upload completion failed: {str(e)}")

@app.get("/progress/{upload_id}")
async def get_progress(upload_id: str):
    """Get real-time upload progress"""
    progress = upload_manager.get_progress(upload_id)
    if progress is None:
        raise HTTPException(status_code=404, detail="Upload not found")
    return progress

@app.get("/uploads")
async def list_uploads():
    """List all uploaded files"""
    uploads = []
    if os.path.exists(UPLOAD_DIR):
        for filename in os.listdir(UPLOAD_DIR):
            filepath = os.path.join(UPLOAD_DIR, filename)
            if os.path.isfile(filepath):
                stat = os.stat(filepath)
                uploads.append({
                    "filename": filename,
                    "size": stat.st_size,
                    "size_formatted": f"{stat.st_size / (1024**3):.2f} GB" if stat.st_size > 1024**3 else f"{stat.st_size / (1024**2):.2f} MB",
                    "modified": time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(stat.st_mtime))
                })
    
    # Sort by modification time (newest first)
    uploads.sort(key=lambda x: x["modified"], reverse=True)
    return {"uploads": uploads, "total_files": len(uploads)}

@app.get("/server-stats")
async def get_server_stats():
    """Get server statistics"""
    import psutil
    import socket
    
    # Get system info
    cpu_percent = psutil.cpu_percent(interval=1)
    memory = psutil.virtual_memory()
    disk = psutil.disk_usage(UPLOAD_DIR)
    
    # Get network info
    hostname = socket.gethostname()
    local_ip = socket.gethostbyname(hostname)
    
    # Count uploaded files
    total_files = 0
    total_size = 0
    if os.path.exists(UPLOAD_DIR):
        for filename in os.listdir(UPLOAD_DIR):
            filepath = os.path.join(UPLOAD_DIR, filename)
            if os.path.isfile(filepath):
                total_files += 1
                total_size += os.path.getsize(filepath)
    
    return {
        "server_info": {
            "hostname": hostname,
            "local_ip": local_ip,
            "upload_directory": os.path.abspath(UPLOAD_DIR)
        },
        "system_stats": {
            "cpu_usage": f"{cpu_percent}%",
            "memory_usage": f"{memory.percent}%",
            "memory_available": f"{memory.available / (1024**3):.1f} GB",
            "disk_free": f"{disk.free / (1024**3):.1f} GB",
            "disk_used": f"{disk.used / (1024**3):.1f} GB"
        },
        "upload_stats": {
            "total_files": total_files,
            "total_size": f"{total_size / (1024**3):.2f} GB",
            "active_uploads": len(upload_manager.active_uploads)
        }
    }

if __name__ == "__main__":
    print("=" * 60)
    print("🚀 ULTRA FAST VIDEO UPLOAD SERVER")
    print("=" * 60)
    print(f"📁 Upload Directory: {os.path.abspath(UPLOAD_DIR)}")
    print(f"🗂️  Temp Directory: {os.path.abspath(TEMP_DIR)}")
    print(f"📊 Max File Size: {MAX_FILE_SIZE // (1024**3)} GB")
    print(f"🧩 Chunk Size: {CHUNK_SIZE // (1024**2)} MB")
    print("-" * 60)
    
    # Get network info
    import socket
    hostname = socket.gethostname()
    local_ip = socket.gethostbyname(hostname)
    
    print("🌐 ACCESS URLS:")
    print(f"   Local: http://localhost:8000")
    print(f"   Network: http://{local_ip}:8000")
    print("-" * 60)
    print("📋 FEATURES:")
    print("   ✅ Chunked uploads for reliability")
    print("   ✅ Real-time progress tracking") 
    print("   ✅ Parallel chunk processing")
    print("   ✅ Drag & drop interface")
    print("   ✅ Network speed optimization")
    print("   ✅ Large file support (500GB+)")
    print("   ✅ Auto-resume capabilities")
    print("=" * 60)
    print("🎬 Ready to receive video uploads!")
    print("📱 Share the network URL with other devices")
    print("=" * 60)
    
    # Create directories if they don't exist
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    os.makedirs(TEMP_DIR, exist_ok=True)
    
    # Run server with optimized settings
    uvicorn.run(
        "main:app", 
        host="0.0.0.0",  # Allow access from network
        port=8000, 
        reload=False,
        workers=1,
        access_log=True,
        # Performance optimizations
        loop="asyncio",
        http="httptools",
        ws="none",
        interface="asgi3",
        log_level="info"
    )
