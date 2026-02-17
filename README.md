# Snapchat Memories Extractor

Download all your Snapchat memories with metadata (date, location) embedded directly into images and videos.

---

## ✨ Features

- ✅ Downloads images and videos from Snapchat export JSON
- ✅ Automatically overlays PNG captions on photos and videos from ZIP archives
- ✅ Embeds EXIF metadata (date taken, GPS coordinates) into images
- ✅ Writes creation time and GPS into video files
- ✅ Converts JPEG images to lossless JPGXL format (20-40% smaller with no quality loss)
- ✅ Progressive JSON pruning (safe to Ctrl+C and resume)
- ✅ Fail-fast: Skips files with missing datetime metadata
- ✅ Zero system dependencies: Everything installs via pip!

---

## 📋 Prerequisites

- **Python 3.10+**
- **macOS only**: [Homebrew](https://brew.sh/) with `jpeg-xl` package

---

## 🚀 Quick Start


### Step 1: Download Your Snapchat Data

1. Go to [Snapchat Data Download](https://accounts.snapchat.com/accounts/downloadmydata).
2. Log in to the Snapchat account you want to extract memories from.
3. Select **both** options: `Export your Memories` and `Export JSON Files`.


### Step 2: Clone the Repository

```bash
git clone https://github.com/Reelinq/snapchat-memories-extractor.git
cd snapchat-memories-extractor
```


### Step 3: Extract the ZIP FileX

Once your Snapchat data export is ready and downloaded:

1. Extract the ZIP file you received from Snapchat.
2. Find the file named `memories_history.json` inside the extracted contents.
3. You can either move this file into the `/data` folder (if you wish), or simply specify the absolute path to the JSON file using the `--memories-json` (or `-mj`) flag when running the extractor.

### Step 4: Create a Virtual Environment

**Windows (PowerShell):**
```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

**macOS/Linux:**
```bash
python3 -m venv .venv
source .venv/bin/activate
```


### Step 5: Install Dependencies

**All platforms:**

```bash
pip install -r requirements.txt
```

**macOS only – Install JPEG XL tools:**

```bash
brew install jpeg-xl
```

> **Note:** On macOS, the JPEG XL converter (`cjxl`) is installed via Homebrew. On Windows and Linux, pre-compiled binaries are included in the repository.


### Step 6: Run the Extractor

```bash
python main.py --memories-json /path/to/memories_history.json
```


**Done!** Your files will be saved to `downloads/` with full metadata embedded.

---

## ⚙️ Configuration Options

### ⚙️ Normal Options

<details>
<summary><b>🔄 Concurrent Downloads: -c / --concurrent N</b></summary>

**What it does:**
- Controls the number of simultaneous downloads
- **Default**: `5` concurrent downloads
- Higher values = faster downloads, but may trigger rate limiting
- Lower values = slower but more stable

**Examples**:

Use default (5 concurrent downloads):
```bash
python main.py
```

Conservative - 3 concurrent downloads:
```bash
python main.py -c 3
```

Faster - 10 concurrent downloads:
```bash
python main.py -c 10
```

Sequential - 1 download at a time (slowest, but safest):
```bash
python main.py -c 1
```

**💡 Recommendations:**
- **3-5 concurrent downloads**: Safe default, respectful to Snapchat's servers
- **10-15 concurrent downloads**: Faster, works well on most home connections
- **20+ concurrent downloads**: May trigger rate limiting or server throttling
- **1 concurrent download**: Use only if experiencing connection issues

> ⚠️ **Note**: Setting too high may result in rate limiting or failed downloads. If you experience issues, reduce the concurrent value.

</details>

<details>
<summary><b>🔁 Retry Attempts: -a / --attempts N</b></summary>

**What it does:**
- Automatically retries the entire download process if files fail
- **Default**: `3` attempts (runs the download process up to 3 times)
- Useful for handling temporary network errors, server timeouts, or rate limiting
- Stops early if all downloads succeed before max attempts

**Examples**:

Default - try up to 3 times:
```bash
python main.py
```

Single attempt - no retries:
```bash
python main.py -a 1
```

Aggressive retries - try up to 5 times:
```bash
python main.py -a 5
```

**💡 Recommendations:**
- **3 attempts** (default): Good balance for most situations
- **1 attempt**: Use if you want manual control over retries
- **5+ attempts**: Use for unstable connections or large archives

**How it works:**
1. First attempt downloads all files from the JSON
2. If any files fail, waits 2 seconds then retries ALL failed files
3. Continues until all files succeed or max attempts reached
4. Progress resets between attempts for clarity

> **Example**: If 5 out of 100 files fail on attempt 1, attempt 2 only retries those 5 failed files.

</details>

<details>
<summary><b>🎨 Media Overlays: -O / --no-overlay</b></summary>

**What it does:**
- Snapchat stores your memories with separate layers for text, stickers, drawings, etc. you added
- **By default**, this tool automatically applies those edits on top of your photos and videos, just like you see them in the Snapchat app
- **Images**: Text, stickers, drawings, etc. are permanently added to the image
- **Videos**: Text, stickers, drawings, etc. are burned into the video throughout playback
- Use `--no-overlay` if you want the original media **without** any of your edits

**Examples**:

Default behavior - downloads photos/videos WITH text, stickers, drawings, etc.:
```bash
python main.py
```

Skip overlays - downloads original photos/videos WITHOUT any edits:
```bash
python main.py -O
```

**💡 Recommendations:**
- **Default (with overlays)**: Best for preserving your memories exactly as you saved them in Snapchat
- **With `--no-overlay`**: Best if you want clean, unedited original photos/videos for editing or archival purposes

> **Example**: If you saved a photo with "Best day ever! 🎉" text, heart stickers, and some doodles on it in Snapchat, the default download will include all of that. With `--no-overlay`, you get the clean original photo without any edits.

</details>

<details>
<summary><b>📝 Metadata Embedding: -M / --no-metadata</b></summary>

**What it does:**
- **By default**, this tool embeds date/time and GPS location metadata into your downloaded photos and videos
- **Images**: Writes EXIF data (DateTimeOriginal, GPS coordinates) directly into the image file
- **Videos**: Writes creation time and GPS location into the video metadata
- Use `--no-metadata` if you want to skip writing metadata entirely

**Examples**:

Default behavior - embeds date/time and location metadata:
```bash
python main.py
```

Skip metadata - downloads files WITHOUT embedded metadata:
```bash
python main.py -M
```

**💡 Recommendations:**
- **Default (with metadata)**: Best for organizing photos by date and viewing them in photo apps with proper timestamps and locations
- **With `--no-metadata`**: Use if you prefer to manage metadata separately or want faster downloads (metadata writing adds processing time)

> **Note**: When metadata is embedded, your photos will display the correct capture date in photo viewers, and you can view the location where each memory was taken (if location data was available).

</details>

<details>
<summary><b>🖼️ JPEG Quality: -q / --jpeg-quality Q</b></summary>

**What it does:**
- Controls the compression quality of JPEG image encoding when applying overlays or writing metadata
- **Default**: `95` (high quality, minimal compression)
- **Range**: 1-100 (1 = maximum compression, 100 = maximum quality)
- Lower values = smaller files but visible quality loss
- Higher values = better quality but larger files

**Examples**:

Default quality (95):
```bash
python main.py
```

High compression for smaller files (85):
```bash
python main.py -q 85
```

Maximum quality (100):
```bash
python main.py -q 100
```

Very aggressive compression (75):
```bash
python main.py -q 75
```

**💡 Recommendations:**
- **95 (default)**: Best balance for high quality with minimal file size
- **85**: Good for storage/backups, slight quality loss (often imperceptible)
- **75**: Aggressive compression, noticeably smaller files (~30-50% size reduction), visible quality loss on close inspection
- **100**: Maximum quality, larger files, rarely worth the trade-off from 95

**Impact on performance:**
- **Lower quality**: Faster JPEG encoding (10-30% speedup), smaller file sizes (30-50% reduction)
- **Higher quality**: Slower encoding, larger files

> **Example**: Using `-q 85` instead of `-q 95` can reduce file sizes from ~4 MB to ~2-3 MB per image, while maintaining good visual quality for most uses.

</details>

<details>
<summary><b>🎨 JPGXL Conversion: -J / --no-jxl</b></summary>

**What it does:**
- **By default**, downloaded JPEG images are automatically converted to the modern **JPGXL (JXL)** format
- JPGXL provides lossless compression with typically **20-40% better compression** than JPEG
- All metadata (date, GPS coordinates, image properties) is preserved during conversion
- Use `--no-jxl` if you prefer to keep original JPEG files without conversion

**Key Features:**
- ✅ **Lossless conversion**: No quality loss (bit-perfect from the original)
- ✅ **Better compression**: Smaller files than JPEG while maintaining perfect quality
- ✅ **Metadata preservation**: All EXIF data is preserved
- ✅ **Zero quality loss**: Guaranteed identical pixel data in lossless format
- ✅ **Modern format**: Uses the official libjxl codec from https://github.com/libjxl/libjxl

**Examples**:

Default behavior - automatically converts JPEG to lossless JPGXL:
```bash
python main.py
```

Skip JPGXL conversion - keep original JPEG files:
```bash
python main.py -J
# or
python main.py --no-jxl
```

**💡 Recommendations:**
- **Default (with JXL conversion)**: Best for storage, archival, and modern photo libraries. Saves 20-40% space with perfect quality.
- **With `--no-jxl`**: Use if you need JPEG compatibility with older devices/applications that don't support JPGXL

**File Size Comparison:**

Example image (4000x3000 photo):
- Original JPEG: 3.2 MB
- Converted JPGXL (lossless): 1.9 MB
- **Savings: 40%** (no quality loss)

**Supported Image Types:**
- Converts: JPEG images (`.jpg`, `.jpeg`)
- Preserves: All EXIF metadata, GPS coordinates, timestamps
- Skips: Videos and non-JPEG images

> **Note**: JPGXL conversion happens after metadata is written, ensuring all date and location information is embedded before conversion.

</details>

<details>
<summary><b>🎞️ Video Codec: --video-codec [h264|h265]</b></summary>

**What it does:**
- Lets you choose the video codec for processed videos: `h264` (default, maximum compatibility) or `h265` (smaller files, but less compatible)
- `h264` is supported by nearly all devices and browsers
- `h265` (HEVC) produces smaller files at the same quality, but may not play on older devices or some browsers

**Examples**:

Default (h264):
```bash
python main.py
```

Use h265 for more compact files:
```bash
python main.py --video-codec h265
```

**💡 Recommendations:**
- Use `h264` for best compatibility (default)
- Use `h265` if you want smaller files and know your devices support it

> ⚠️ **Note**: H.265/HEVC is not supported by all players and may require more CPU to encode/decode.

</details>

---

### 🛠️ Advanced Options

<details>
<summary><b>⏱️ FFmpeg Timeout: -f / --ffmpeg-timeout SECONDS</b></summary>

**What it does:**
- Sets how many seconds the program will wait for FFmpeg (used for processing videos) to finish before giving up on the operation.
- **Default**: `60` seconds
- Increase if you have very large or slow-to-process video files; decrease for faster failure on stuck or problematic files.

**Examples**:

Default (60 seconds):
```bash
python main.py
```

Wait up to 120 seconds for each FFmpeg operation:
```bash
python main.py -f 120
python main.py --ffmpeg-timeout 120
```

Fail quickly (30 seconds):
```bash
python main.py -f 30
```

**💡 Recommendations:**
- Use the default unless you experience frequent FFmpeg timeouts or have very large/complex videos.
- Increase for slow computers or long videos.

</details>

<details>
<summary><b>🎛️ FFmpeg Preset: -fp / --ffmpeg-preset [preset]</b></summary>

**What it does:**
- Sets the FFmpeg encoding preset, which controls the speed/compression tradeoff for video encoding.
- **Presets:** `ultrafast`, `superfast`, `veryfast`, `faster`, `fast`, `medium`, `slow`, `slower`, `veryslow`, `placebo`
- **Default:** `fast`
- Faster presets (e.g., `ultrafast`) encode quickly but produce larger files. Slower presets (e.g., `veryslow`) take longer but create smaller, more efficient files.

**Examples**:

Use the default preset (`fast`):
```bash
python main.py
```

Use a slower preset for better compression:
```bash
python main.py --ffmpeg-preset slow
```

Use the fastest preset (largest files, lowest CPU usage):
```bash
python main.py -fp ultrafast
```

**💡 Recommendations:**
- Use `fast` or `medium` for a good balance of speed and file size.
- Use `veryslow` or `placebo` only if you want the smallest possible files and don't mind long processing times.

</details>

<details>
<summary><b>🎨 FFmpeg Pixel Format: -pf / --ffmpeg-pixel-format [format]</b></summary>

**What it does:**
- Sets the pixel format for video encoding in FFmpeg, which affects compatibility, color depth, and file size.
- **Formats:** `yuv420p`, `rgb24`, `rgba`, `nv12`, `yuv422p`, `yuv444p`, `bgr24`, `gray`, `yuyv422`, `p010le`, `yuv420p10le`, `nv21`, `bgra`, `argb`
- **Default:** `yuv420p` (widest compatibility)

**Examples**:

Use the default pixel format (`yuv420p`):
```bash
python main.py
```

Use a format with alpha channel (transparency):
```bash
python main.py --ffmpeg-pixel-format rgba
```

Use a high color depth format:
```bash
python main.py -pf yuv444p
```

**💡 Recommendations:**
- Use `yuv420p` for maximum compatibility with most devices and players.
- Use `rgb24` or `rgba` if you need true color or transparency (note: larger files, less compatible).
- Only change this if you know your target device/player supports the chosen format.

</details>

<details>
<summary><b>⏳ Request Timeout: -t / --request-timeout SECONDS</b></summary>

**What it does:**
- Sets how many seconds the program will wait for a response from Snapchat's servers before giving up on a request.
- **Default**: `30` seconds
- Increase if you have a slow or unstable connection; decrease for faster failure on bad links.

**Examples**:

Default (30 seconds):
```bash
python main.py
```

Wait up to 60 seconds for each request:
```bash
python main.py -t 60
python main.py --request-timeout 60
```

Fail quickly (10 seconds):
```bash
python main.py -t 10
```

**💡 Recommendations:**
- Use the default unless you experience frequent timeouts or want faster failure.
- Increase for slow networks or large files.

</details>

<details>
<summary><b>🗒️ Log Level: -l / --log-level LEVEL</b></summary>

**What it does:**
- Controls how much information the program prints to the console (logging output)
- Accepts either a number (0-5) or a name (OFF, CRITICAL, ERROR, WARNING, INFO, DEBUG)
- **Default**: `0` (OFF, no logging)
- Higher values (e.g., DEBUG) show more detailed information, lower values show less

**Examples**:

Default (no logging):
```bash
python main.py
```

Show only errors and critical issues:
```bash
python main.py -l 2
python main.py --log-level ERROR
```

Show warnings and above:
```bash
python main.py -l 3
python main.py --log-level WARNING
```

Show all debug output:
```bash
python main.py -l 5
python main.py --log-level DEBUG
```

**💡 Recommendations:**
- Use `-l 4` or `--log-level INFO` for general progress updates
- Use `-l 5` or `--log-level DEBUG` for troubleshooting or development
- Leave at default (OFF) for fastest, cleanest output

**Accepted values:**
- Numbers: `0` (OFF), `1` (CRITICAL), `2` (ERROR), `3` (WARNING), `4` (INFO), `5` (DEBUG)
- Names: `OFF`, `CRITICAL`, `ERROR`, `WARNING`, `INFO`, `DEBUG`

> **Note**: Setting a more verbose log level (like DEBUG) may slow down processing and produce a lot of output, but is useful for diagnosing problems.

</details>

<details>
<summary><b>⏳ CJXL Timeout: -cjxlt / --cjxl-timeout SECONDS</b></summary>

**What it does:**
- Sets how many seconds the program will wait for the `cjxl` JPEG XL encoder to finish converting an image before giving up on the operation.
- **Default**: `120` seconds
- Increase if you have very large or slow-to-convert images; decrease for faster failure on stuck or problematic files.

**Examples**:

Default (120 seconds):
```bash
python main.py
```

Wait up to 300 seconds for each JPEG XL conversion:
```bash
python main.py -cjxlt 300
python main.py --cjxl-timeout 300
```

Fail quickly (60 seconds):
```bash
python main.py -cjxlt 60
```

**💡 Recommendations:**
- Use the default unless you experience frequent timeouts or have very large/complex images.
- Increase for slow computers or very large images.

</details>

<details>
<summary><b>🎚️ Constant Rate Factor: --crf N</b></summary>

**What it does:**
- Sets the Constant Rate Factor (CRF) for video encoding quality and file size.
- **Lower values = higher quality, larger files.**
- **Higher values = lower quality, smaller files.**
- **Valid range:** 0 (lossless) to 51 (worst). Typical: 18–28.
- **Default:** 23 for H.264, 28 for H.265 (automatically chosen if not set).

**Examples**:

Use default (23 for H.264, 28 for H.265):
```bash
python main.py
```

Set CRF to 20 (higher quality, bigger files):
```bash
python main.py --crf 20
```

Set CRF to 30 (smaller files, lower quality):
```bash
python main.py --crf 30
```

**💡 Recommendations:**
- **18–23:** Visually lossless or high quality.
- **24–28:** Good balance for most uses.
- **29–35:** Smallest files, but visible quality loss.
- **0:** Lossless (huge files, rarely needed).

> ⚠️ **Note:** If you use `--video-codec h265`, the default CRF is 28 unless you set `--crf` yourself.

</details>

---

## 🔧 Troubleshooting

<details>
<summary><b>⏰ Download Links Expired</b></summary>

Snapchat download links expire after a period of time. If downloads fail, try to export a fresh `memories_history.json` from Snapchat and replace the old one in the `data/` folder.

</details>

<details>
<summary><b>📄 Missing 'memories_history.json'</b></summary>

When exporting your data from Snapchat, make sure you select **both** options:
- ✅ **Export your Memories**
- ✅ **Export JSON Files**

Without these options, the JSON file won't be included in your export.

</details>

<details>
<summary><b>🆘 Still Having Issues?</b></summary>

Please open a new [issue](https://github.com/Reelinq/snapchat-memories-extractor/issues) with the following information:
- Your Python version (`python --version`)
- Operating system
- Error message or unexpected behavior
- Whether the issue is with images or videos

</details>

---

## 📜 License

MIT License - feel free to use and modify as needed.
