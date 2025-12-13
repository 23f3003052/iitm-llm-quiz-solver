# app.py
import logging
import os
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

# Import our core logic
from core.fetch import fetch_page
from core.router import route_and_solve
from core.submit import find_submit_url, submit_answer

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()

app = FastAPI()

class QuizRequest(BaseModel):
    email: str
    secret: str
    url: str

class QuizResponse(BaseModel):
    status: str
    message: str = None

# Validation constants
VALID_EMAIL = os.getenv("STUDENT_EMAIL")
VALID_SECRET = os.getenv("STUDENT_SECRET")

@app.post("/solve")
async def solve_quiz(request: QuizRequest) -> QuizResponse:
    # 1. Validate credentials
    if request.email != VALID_EMAIL:
        raise HTTPException(status_code=403, detail="Invalid email")
    if request.secret != VALID_SECRET:
        raise HTTPException(status_code=403, detail="Invalid secret")
    
    try:
        # 2. Start the solver chain
        await solve_quiz_chain(request.url, request.email, request.secret)
        return QuizResponse(status="success")
    except Exception as e:
        logger.error(f"Global error in /solve: {e}", exc_info=True)
        return QuizResponse(status="error", message=str(e))

async def solve_quiz_chain(initial_url: str, email: str, secret: str):
    current_url = initial_url
    attempt = 0
    max_attempts = 15  # Safety limit to prevent infinite loops
    
    while current_url and attempt < max_attempts:
        attempt += 1
        logger.info(f"\n{'='*40}\n[QUIZ {attempt}] {current_url}\n{'='*40}")
        
        # A. Fetch the page (rendered JS)
        page_data = await fetch_page(current_url)
        if not page_data:
            logger.error(f"Failed to fetch page: {current_url}")
            break
        
        question = page_data["question"]
        logger.info(f"Question Preview: {question[:200]}...")
        
        # B. Find where to submit
        submit_url = find_submit_url(question, page_data["html"], current_url)
        if not submit_url:
            # Fallback: assume /submit relative to current
            base = current_url.split('?')[0]
            if '/' in base:
                # heuristic: strip last segment and add 'submit' or similar?
                # Safer default: domain + /submit
                # But let's log error for now
                logger.warning("No explicit submit URL found, guessing...")
        
        logger.info(f"Submit URL: {submit_url}")
        
        # C. Route to correct handler and solve
        answer = await route_and_solve(question, current_url, page_data, email)
        logger.info(f"Calculated Answer: {answer}")
        
        # D. Submit the answer
        resp = await submit_answer(email, secret, current_url, answer, submit_url)
        logger.info(f"Server Response: Correct={resp.get('correct')}, Msg={resp.get('reason')}")
        
        # E. Handle next step
        if resp.get("correct"):
            current_url = resp.get("url")
            if not current_url:
                logger.info("✅ QUIZ CHAIN COMPLETE! All steps solved.")
                break
        else:
            # If wrong, check if we got a retry URL or just stop
            current_url = resp.get("url")
            if not current_url:
                logger.error("❌ Failed step with no retry URL. Stopping.")
                break
