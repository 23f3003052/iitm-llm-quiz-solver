import os
import re
import httpx
from openai import AsyncOpenAI

async def handler(question: str, url: str) -> str:
    try:
        # 1. Extract the audio URL
        m = re.search(r'(/project2/[^\s"\'<>]+\.opus)', question)
        if not m:
            m = re.search(r'(/project2/[^\s"\'<>]+\.mp3)', question)
        
        if not m:
            return "0"
            
        relative = m.group(1)
        domain = re.match(r'(https?://[^/]+)', url).group(1)
        audio_url = domain + relative
        
        print(f"  Downloading audio: {audio_url}")

        # 2. Check for API Key
        api_key = os.environ.get("AIPROXY_TOKEN") or os.environ.get("OPENAI_API_KEY")
        if not api_key:
            print("  ❌ Missing AIPROXY_TOKEN or OPENAI_API_KEY")
            return "0"

        # 3. Download the file
        async with httpx.AsyncClient() as client:
            resp = await client.get(audio_url, timeout=30)
            audio_data = resp.content

        # 4. Save to a temp file (OpenAI library needs a file path/object)
        temp_filename = "/tmp/audio_task.opus"
        with open(temp_filename, "wb") as f:
            f.write(audio_data)

        # 5. Transcribe using OpenAI Whisper
        # Configure client (support both standard OpenAI and AI Proxy)
        client_args = {"api_key": api_key}
        if "AIPROXY_TOKEN" in os.environ:
             client_args["base_url"] = "https://aiproxy.sanand.workers.dev/openai/v1"

        client = AsyncOpenAI(**client_args)
        
        with open(temp_filename, "rb") as audio_file:
            transcript = await client.audio.transcriptions.create(
                model="whisper-1", 
                file=audio_file
            )
        
        text = transcript.text.strip()
        print(f"  🎤 Transcription: {text}")
        return text

    except Exception as e:
        print(f"  Audio Error: {e}")
        return "0"