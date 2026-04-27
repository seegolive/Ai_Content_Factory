FROM python:3.12-slim

# System deps including ffmpeg (ffprobe is bundled with ffmpeg)
RUN apt-get update && apt-get install -y \
    ffmpeg \
    libpq-dev \
    gcc \
    curl \
    unzip \
    && rm -rf /var/lib/apt/lists/*

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
