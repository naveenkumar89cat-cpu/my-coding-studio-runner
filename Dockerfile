FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    default-jdk \
    git \
    curl \
    rustc \
    cargo \
    nodejs \
    npm \
    unzip \
    && rm -rf /var/lib/apt/lists/*

# Kotlin compiler
RUN curl -L -o /tmp/kotlin.zip \
    https://github.com/JetBrains/kotlin/releases/download/v2.2.20/kotlin-compiler-2.2.20.zip \
    && unzip /tmp/kotlin.zip -d /opt \
    && rm /tmp/kotlin.zip

ENV PATH="/opt/kotlinc/bin:${PATH}"

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY server.py .

ENV PORT=10000
EXPOSE 10000

CMD ["sh", "-c", "uvicorn server:app --host 0.0.0.0 --port ${PORT}"]
