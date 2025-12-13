import os
import re
import httpx
from openai import AsyncOpenAI
import logging

# Configure logger
logger = logging.getLogger(__name__)

async def handler(question: str, url: str) -> str:
    logger.info(f"🤖 LLM Handler processing question: {question[:100]}...")
    
    try:
        # 1. Setup OpenAI Client
        token = os.environ.get("AIPROXY_TOKEN") or os.environ.get("OPENAI_API_KEY")
        if not token:
            logger.error("❌ No API Token found (AIPROXY_TOKEN or OPENAI_API_KEY)")
            return "Error: No API Token"
            
        # Determine base_url
        base_url = None
        if "AIPROXY_TOKEN" in os.environ:
            base_url = "https://aiproxy.sanand.workers.dev/openai/v1"
            
        client = AsyncOpenAI(api_key=token, base_url=base_url)

        # 2. Extract Context (Download referenced files)
        context_content = ""
        file_url = None
        
        # Regex patterns to find file links (HTML href, Markdown, or raw URLs)
        # Matches: href="...", [text](url), or https://... ending in common data extensions
        patterns = [
            r'href=["\']([^"\'<>]+?\.(?:txt|csv|json|sql|log|sh|py|md))["\']',  # HTML
            r'\[.*?\]\((.*?\.(?:txt|csv|json|sql|log|sh|py|md))\)',             # Markdown
            r'(https?://[^\s<>"]+?\.(?:txt|csv|json|sql|log|sh|py|md))'          # Raw URL
        ]
        
        for p in patterns:
            m = re.search(p, question, re.IGNORECASE)
            if m:
                found = m.group(1)
                # Resolve relative URLs
                if not found.startswith("http"):
                    # Extract base domain from current URL
                    domain_match = re.match(r'(https?://[^/]+)', url)
                    if domain_match:
                        domain = domain_match.group(1)
                        # Handle paths starting with / or not
                        if found.startswith('/'):
                            file_url = domain + found
                        else:
                            file_url = domain + '/' + found
                else:
                    file_url = found
                break
        
        # Download if a file was found
        if file_url:
            logger.info(f"    📥 Downloading context from: {file_url}")
            try:
                async with httpx.AsyncClient() as http_client:
                    resp = await http_client.get(file_url, timeout=10)
                    if resp.status_code == 200:
                        # Safety limit: 15KB to avoid context overflow
                        context_content = resp.text[:15000]
                        logger.info(f"    📄 Downloaded {len(context_content)} characters")
                    else:
                        logger.warning(f"    ⚠️ Failed to download file. Status: {resp.status_code}")
            except Exception as e:
                logger.error(f"    ⚠️ Download error: {e}")

        # 3. Construct the Prompt
        system_prompt = (
            "You are an intelligent automation agent for a Data Science course. "
            "Your task is to answer the user's question directly and concisely. "
            "Follow these strict rules:\n"
            "1. Output ONLY the answer. No intro, no outro, no markdown formatting\n"
            "2. If asked for a command, provide just the command text.\n"
            "3. If asked for a count or sum, provide just the number.\n"
            "4. If asked to correct a string or URL, provide just the corrected string.\n"
            "5. If a file content is provided, analyze it to answer the question."
        )
        
        user_content = f"Question:\n{question}\n\n"
        
        if context_content:
            user_content += f"--- BEGIN ATTACHED FILE CONTENT ---\n{context_content}\n--- END ATTACHED FILE CONTENT ---\n\n"
        
        user_content += "Answer:"

        # 4. Call the LLM
        response = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content}
            ],
            max_tokens=300,
            temperature=0.1  # Low temperature for deterministic/factual answers
        )

        answer = response.choices.message.content.strip()
        
        # 5. Clean the answer (Remove markdown fences if LLM ignores instructions)
        # e.g., ```bash ... ```
        if answer.startswith("```"):
            lines = answer.split('\n')
            if len(lines) >= 2:
                # Strip first line if it starts with ```
                if lines.startswith("```"):
                    lines = lines[1:]
                # Strip last line if it starts with ```
                if lines and lines[-1].strip().startswith("```"):
                    lines = lines[:-1]
                answer = "\n".join(lines).strip()
        
        logger.info(f"    💡 LLM Answer: {answer}")
        return answer

    except Exception as e:
        logger.error(f"  ❌ LLM Handler Critical Error: {e}", exc_info=True)
        return "error"
