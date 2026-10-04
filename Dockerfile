FROM python:3.12-slim

ENV DEBIAN_FRONTEND=noninteractive \
    PORT=10000 \
    ANDROID_HOME=/opt/android-sdk \
    ANDROID_SDK_ROOT=/opt/android-sdk \
    KOTLIN_HOME=/opt/kotlin \
    PATH=/opt/kotlin/bin:/opt/android-sdk/cmdline-tools/latest/bin:/opt/android-sdk/platform-tools:/opt/android-sdk/build-tools/35.0.0:$PATH

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc g++ default-jdk git curl unzip ca-certificates \
    rustc cargo nodejs npm \
    && rm -rf /var/lib/apt/lists/*

# Kotlin compiler
RUN curl -fL https://github.com/JetBrains/kotlin/releases/download/v2.2.20/kotlin-compiler-2.2.20.zip -o /tmp/kotlin.zip \
    && unzip -q /tmp/kotlin.zip -d /tmp \
    && mv /tmp/kotlinc /opt/kotlin \
    && rm /tmp/kotlin.zip \
    && kotlinc -version

# Android SDK
RUN mkdir -p ${ANDROID_HOME}/cmdline-tools \
    && curl -fL https://dl.google.com/android/repository/commandlinetools-linux-11076708_latest.zip -o /tmp/android-tools.zip \
    && unzip -q /tmp/android-tools.zip -d /tmp/android-tools \
    && mkdir -p ${ANDROID_HOME}/cmdline-tools/latest \
    && mv /tmp/android-tools/cmdline-tools/* ${ANDROID_HOME}/cmdline-tools/latest/ \
    && rm -rf /tmp/android-tools /tmp/android-tools.zip \
    && yes | sdkmanager --licenses >/dev/null \
    && sdkmanager "platform-tools" "platforms;android-35" "build-tools;35.0.0" \
    && sdkmanager --version \
    && javac -version \
    && node --version \
    && rustc --version \
    && git --version

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY server.py .

EXPOSE 10000

CMD ["sh","-c","uvicorn server:app --host 0.0.0.0 --port ${PORT}"]
