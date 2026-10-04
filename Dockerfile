FROM python:3.12-slim

ENV DEBIAN_FRONTEND=noninteractive
ENV PORT=10000
ENV KOTLIN_HOME=/opt/kotlin
ENV PATH="/opt/kotlin/bin:${PATH}"

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    default-jdk \
    git \
    curl \
    unzip \
    rustc \
    cargo \
    nodejs \
    npm \
    && rm -rf /var/lib/apt/lists/*

# Kotlin compiler
RUN curl -fL \
    https://github.com/JetBrains/kotlin/releases/download/v2.2.20/kotlin-compiler-2.2.20.zip \
    -o /tmp/kotlin.zip \
    && mkdir -p /tmp/kotlin-extract \
    && unzip -q /tmp/kotlin.zip -d /tmp/kotlin-extract \
    && mv /tmp/kotlin-extract/kotlinc /opt/kotlin \
    && rm -rf /tmp/kotlin.zip /tmp/kotlin-extract \
    && kotlinc -version

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY server.py .

EXPOSE 10000

CMD ["sh", "-c", "uvicorn server:app --host 0.0.0.0 --port ${PORT}"]
