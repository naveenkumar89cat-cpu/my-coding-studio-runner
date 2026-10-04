# My Coding Studio Final Runner

Includes C/C++, Java, Kotlin, Python, Node.js, Rust/Cargo, Git, Android SDK platform/build-tools 35, and an OpenAI-compatible AI proxy.

Render AI environment variables (do not put secrets in source):
- AI_API_URL: OpenAI-compatible chat completions endpoint
- AI_API_KEY: provider secret key
- AI_MODEL: model name

Website AI endpoint should be:
https://my-coding-studio-runner.onrender.com/ai

Android Build expects a real Gradle Android project including gradlew + wrapper files in the Studio workspace. The runner returns discovered APK paths after assembleDebug, but the current website may need a later download-artifact route to retrieve the APK binary.
