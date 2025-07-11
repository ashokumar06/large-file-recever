<h1 align="center">🚀 Ultra Fast Video Upload Server</h1>

<p align="center">
  <img src="https://media.giphy.com/media/zOvBKUUEERdNm/giphy.gif" width="60%" alt="Upload Animation" />
</p>

<p align="center">
  <b>High-performance, resumable chunk-based file uploader built with FastAPI & Uvicorn</b><br>
  <sub>Designed for large (500GB+) file uploads with speed, stability, and developer-first features.</sub><br><br>

  <img alt="Python" src="https://img.shields.io/badge/Python-3.10+-blue?logo=python">
  <img alt="License" src="https://img.shields.io/badge/License-MIT-green">
  <img alt="Status" src="https://img.shields.io/badge/Status-Stable-brightgreen">
</p>

---

## 🔥 Features

- ✅ Chunked upload handling (resilient over weak networks)
- ✅ 500GB+ file size support
- ✅ Parallel chunk processing for speed
- ✅ Auto-resume if upload fails mid-way
- ✅ Drag & Drop user interface (no config needed)
- ✅ Optimized for LAN transfer & high-speed local networks
- ✅ Minimal setup, full Python stack (FastAPI + Uvicorn)

---

## 📸 Live Preview


<p align="center">

  <img src="https://blog.sendsafely.com/hs-fs/hubfs/video_preview-2.png?width=711&height=275&name=video_preview-2.png" width="80%" alt="UI Preview" />
</p>

---

## 🧑‍💻 How to Use

### 1️⃣ Clone and Install Dependencies

```bash
git clone https://github.com/ashokumar06/large-file-recever.git
cd large-file-recever
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```


2️⃣ Run the Upload Server

```bash
python main.py
```


Expected Output:

```bash
🚀 ULTRA FAST VIDEO UPLOAD SERVER
📁 Upload Directory: ./uploaded_videos
🗂️  Temp Directory: ./temp_chunks
📊 Max File Size: 500 GB
🧩 Chunk Size: 128 MB

🌐 ACCESS URLS:
   Local:   http://localhost:8000
   Network: http://<your-local-ip>:8000

🎬 Ready to receive video uploads!
📱 Share the network URL with other devices

```

🌐 Access Over the Internet (with Cloudflare Tunnel)

You can expose your local server to the world using cloudflared:
1️⃣ Install cloudflared

```bash
# Debian/Ubuntu
sudo apt install cloudflared
# or download from https://github.com/cloudflare/cloudflared/releases
```

2️⃣ Run Tunnel
```bash
cloudflared tunnel --url http://localhost:8000
```

This will generate a public HTTPS URL, like:
```bash
https://randomname.trycloudflare.com
```
🌍 Now your video upload server is accessible from anywhere on the internet securely.


📁 Folder Structure
```bash
large-file-recever/
├── uploaded_videos/    # Final uploaded files
├── temp_chunks/        # Temporary chunks
├── main.py             # FastAPI app
├── requirements.txt
└── README.md
```
🧠 Developer Notes
```
    FastAPI app runs via uvicorn with optimal settings (asyncio, httptools)

    Plug-and-play server: can integrate with cloud storage, auth, virus scan

    Designed to scale horizontally with multiple workers
```
🔒 Production Tips
```
    Use nginx with SSL or cloudflared for HTTPS

    Add authentication using JWT or OAuth

    Connect to cloud storage (S3, Azure Blob, etc.)

    Enable background jobs for post-processing (via Celery or RQ)
```
✅ Future Enhancements
```bash
WebSocket progress updates

Docker container build

Optional login system

    Admin UI to manage uploaded files
```
📜 License
```bash
Licensed under the GPL License
```

🙋‍♂️ Author
```bash
Made with ❤️ by Ashok Kumar
```