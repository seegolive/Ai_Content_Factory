FROM python:3.12-bullseye

ENV DEBIAN_FRONTEND=noninteractive

# Remove problematic *-updates and *-backports repos (mirror sync issue Apr 2026)
# Use only stable bullseye main — all we need is curl for downloads
RUN sed -i '/bullseye-updates\|bullseye-backports/d' /etc/apt/sources.list \
    && apt-get update \
    && apt-get install -y --no-install-recommends curl unzip \
    && rm -rf /var/lib/apt/lists/*

# Install static ffmpeg binary (bypasses apt mirror issues entirely)
RUN curl -L https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-linux64-gpl.tar.xz \
    | tar -xJ --strip-components=2 -C /usr/local/bin --wildcards '*/bin/ffmpeg' '*/bin/ffprobe' \
    && chmod +x /usr/local/bin/ffmpeg /usr/local/bin/ffprobe

# Install Deno (required by yt-dlp for YouTube JS signature solving → enables 1080p/1440p)
RUN curl -fsSL https://deno.land/install.sh | sh
ENV PATH="/root/.deno/bin:${PATH}"

WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install PyTorch with CUDA (adjust version for your CUDA)
RUN pip install --no-cache-dir torch==2.5.1+cu124 torchaudio==2.5.1+cu124 \
    --index-url https://download.pytorch.org/whl/cu124 || \
    pip install --no-cache-dir torch torchaudio --index-url https://download.pytorch.org/whl/cpu

COPY . .

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
