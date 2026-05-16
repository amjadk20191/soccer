FROM python:3.11-slim

# ── system deps (required by Playwright's Chromium) ──────────────────────────
# playwright install --with-deps handles this, but we need apt tools first
RUN apt-get update && apt-get install -y --no-install-recommends \
        wget curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# ── Python deps first (layer-cached unless requirements change) ───────────────
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Chromium + all its OS-level libraries in one command
RUN playwright install --with-deps chromium

# ── app source ────────────────────────────────────────────────────────────────
COPY . .

# QR-code HTTP server port (open this in your browser to scan the QR)
EXPOSE 8080

CMD ["python", "main.py"]
