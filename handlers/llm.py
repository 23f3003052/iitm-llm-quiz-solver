import os
import logging
import re
import httpx
from openai import AsyncOpenAI

# Set up logging
logger = logging.getLogger(__name__)

async def handler(question):
    """
    Process the question using an LLM.
    1. Detects if an OpenAI key or Proxy Token is used.
    2. Downloads any referenced files (data files).
    3. Asks the LLM for the answer.
    """
    logger.info(f"🤖 LLM Handler processing question: {question[:100]}...")

    # ------------------------------------------------------------------
    # 1. SMART CLIENT SETUP (Fixes the 401 Error)
    # ------------------------------------------------------------------
    token = os.environ.get("AIPROXY_TOKEN")
    if not token:
        # Fallback to standard OpenAI variable if AIPROXY_TOKEN is missing
        token = os.environ.get("OPENAI_API_KEY")
    
    if not token:
        logger.error("❌ No API Token found in environment variables.")
        return "Error: No API Token"

    # Check if it's a real OpenAI key or a Proxy Token
    if token.startswith("sk-"):
        logger.info("🔑 Detected official OpenAI Key. Connecting directly.")
        client = AsyncOpenAI(api_key=token)
    else:
        logger.info("bm Detected Course Proxy Token. Connecting via Proxy.")
        client = AsyncOpenAI(
            api_key=token,
            base_url="https://aiproxy.sanand.workers.dev/openai/v1"
        )

    # ------------------------------------------------------------------
    # 2. FILE DOWNLOAD LOGIC
    # ------------------------------------------------------------------
    context = ""
    # Regex to find filenames like "config.json", "data.csv", "database.sql"
    # The base URL for files seems to be the one in the logs
    base_file_url = "https://tds-llm-analysis.s-anand.net/project2-reevals/"
    
    # Common files used in this project
    known_files = [
        "echo.json", "config.json", "database.sql", "contacts.csv", 
        "email.txt", "dates.txt", "numbers.txt", "comments.txt"
    ]
    
    found_file = None
    for filename in known_files:
        if filename in question:
            found_file = filename
            break
            
    if found_file:
        file_url = f"{base_file_url}{found_file}"
        logger.info(f"    📥 Downloading context from: {file_url}")
        
        try:
            async with httpx.AsyncClient() as http_client:
                resp = await http_client.get(file_url)
                resp.raise_for_status()
                file_content = resp.text
                
                # Truncate if too long (saving tokens)
                if len(file_content) > 10000:
                    file_content = file_content[:10000] + "\n...(truncated)"
                
                context = f"\n\n--- Content of {found_file} ---\n{file_content}\n---------------------"
                logger.info(f"    📄 Downloaded {len(file_content)} characters")
        except Exception as e:
            logger.error(f"    ❌ Failed to download file: {e}")
            context = f"\n\n(Could not download file {found_file}: {str(e)})"

    # ------------------------------------------------------------------
    # 3. CONSTRUCT PROMPT
    # ------------------------------------------------------------------
    system_prompt = """You are an intelligent automation agent for a Data Science course.
Your job is to extract answers directly from the user question or the provided file content.
Rules:
1. Output ONLY the answer. No introspection, no markdown like ```
2. If asked for a specific value (like an API key), output just that value.
3. If asked for a command (like curl or docker), output just the one-line command.
4. If asked for a count, output just the integer.
5. If the user asks to decode something, decode it and output the result.
"""

    user_content = f"Question: {question}{context}"

    # ------------------------------------------------------------------
    # 4. CALL LLM
    # ------------------------------------------------------------------
    try:
        response = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content}
            ],
            temperature=0.1
        )
        
        # Access the content correctly
        answer = response.choices.message.content.strip()
        logger.info(f"    ✅ LLM Answer: {answer}")
        return answer

    except Exception as e:
        logger.error(f"    ❌ LLM Handler Critical Error: {e}")
        # Re-raise or return error string depending on how your app handles it
        # Returning "error" usually triggers a retry or fail in the logs
        raise e
