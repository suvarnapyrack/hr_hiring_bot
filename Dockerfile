FROM python:3.10-slim

WORKDIR /app

# Install system dependencies required for OCR and other libraries
RUN apt-get update && apt-get install -y \
    build-essential \
    poppler-utils \
    tesseract-ocr \
    libpq-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

RUN pip install --upgrade pip

# Separate heavy dependencies to leverage caching
# Install CPU-only torch from its specific index
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu
# Install everything else (including sentence-transformers) from PyPI
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Ensure entrypoint is executable
RUN chmod +x entrypoint.sh

EXPOSE 8501

ENTRYPOINT ["./entrypoint.sh"]
