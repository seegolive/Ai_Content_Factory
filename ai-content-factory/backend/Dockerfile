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

# Expose CUDA libraries bundled with torch so ctranslate2/faster-whisper can find them
ENV LD_LIBRARY_PATH="/usr/local/lib/python3.12/site-packages/nvidia/cublas/lib:/usr/local/lib/python3.12/site-packages/nvidia/cudnn/lib:/usr/local/lib/python3.12/site-packages/nvidia/cuda_runtime/lib:${LD_LIBRARY_PATH}"

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install PyTorch CUDA before realesrgan/basicsr to prevent CPU torch override
RUN pip install --no-cache-dir \
    torch==2.5.1+cu124 torchvision==0.20.1+cu124 torchaudio==2.5.1+cu124 \
    --index-url https://download.pytorch.org/whl/cu124 \
    || pip install --no-cache-dir torch torchvision torchaudio \
    --index-url https://download.pytorch.org/whl/cpu

# Install realesrgan/basicsr after CUDA torch — --no-deps prevents CPU torch override
RUN pip install --no-cache-dir realesrgan basicsr facexlib gfpgan --no-deps

# Compatibility shim: torchvision.transforms.functional_tensor removed in 0.15+
RUN python3 -c "\
import torchvision, os; \
p = os.path.join(os.path.dirname(torchvision.__file__), 'transforms', 'functional_tensor.py'); \
open(p, 'w').write('from torchvision.transforms.functional import *\n')"

COPY . .

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
