# 🎬 Universal Transcoder  
*A simple Python + FFmpeg tool for batch video conversion and automation.*

---

## 💡 Why I Built This

Sometimes the smallest video tasks cause the biggest headaches.

I just wanted to convert an old `.dat` file into `.mp4`.  
But every online tool had some limitation — size caps, watermark, or “premium only” quality.  

So I decided to build my own script once, and never worry about it again.  
That’s how **Universal Transcoder** was born.

---

## ⚙️ Features

✅ Automatically detects input codecs (video & audio)  
✅ Remuxes when possible (no quality loss)  
✅ Transcodes when necessary (smart presets)  
✅ Works with **any input format** supported by FFmpeg  
✅ Built-in quality profiles: `auto`, `ultra`, `high`, `balanced`, `fast`, `custom`  
✅ Supports folders, recursion, subtitles, scaling, and filters  

---

## 🚀 Quick Start

### 1. Install requirements
Make sure Python and FFmpeg are installed.

```bash
conda install -c conda-forge ffmpeg
```

### 2. Run from terminal
```bash
python universal_transcoder.py ^
  --input "C:\path\to\file_or_folder" ^
  --target-format mp4 ^
  --quality ultra ^
  --overwrite
```

---

## 🎚️ Quality Presets

| Quality | Description |
|----------|-------------|
| **auto** | Remux when compatible, else CRF 20 / fast / 192k |
| **ultra** | CRF 18 / slow / 320k (high quality) |
| **high** | CRF 19 / medium / 256k |
| **balanced** | CRF 21 / fast / 192k |
| **fast** | CRF 23 / veryfast / 160k |
| **custom** | Manual mode (choose codecs, CRF, bitrate, filters, etc.) |

---

## 🧠 Example: Custom Mode

```bash
python universal_transcoder.py ^
  --input "C:\videos" ^
  --target-format webm ^
  --quality custom ^
  --mode transcode ^
  --vcodec libvpx-vp9 --acodec libopus ^
  --crf 28 --preset good --audio-bitrate 160k ^
  --overwrite
```

---

## 🧩 Tech Stack

- **Python**  
- **FFmpeg**  
- **Command Line Automation**

---

## ✨ Author

**Hanoguzzz**  
Data Analyst • Automation Enthusiast • Creator of Smart Tools That Save Time  
📺 [YouTube](https://www.youtube.com/@Hanoguzzz)  
✍️ [Medium](https://medium.com/@Hanoguzzz)

---

## 📜 License

MIT License © 2025 Hanoguzzz

---

## 🔗 Related Medium Article

Read the story behind this project:  
👉 [Small Video Problems, Big Difference Through Code](https://medium.com/@Hanoguzzz)

---

### ⭐ If this tool saved you time, give it a star on GitHub!
