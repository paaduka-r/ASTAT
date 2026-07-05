import asyncio
import json
import os
import sys

from browser.chatgpt import ChatGPTBrowser
from browser.claude import ClaudeBrowser
from browser.gemini import GeminiBrowser
from browser.grok import GrokBrowser

GROUND_TRUTH_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', 'ground_truth.json')
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), '..', 'output')
OUTPUT_PATH = os.path.join(OUTPUT_DIR, 'playwright_stealth_results.json')

def load_questions():
    with open(GROUND_TRUTH_PATH, 'r', encoding='utf-8') as f:
        data = json.load(f)
    # Filter only 'filled' questions
    filled_questions = {k: v for k, v in data.items() if v.get("status") == "filled"}
    return filled_questions

def save_results(results):
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    with open(OUTPUT_PATH, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print(f"[+] Saved current progress to {OUTPUT_PATH}")

async def safe_query(browser, question_text, existing_answer, filepath=None):
    # If we already have a valid answer (not missing and not an Error), skip querying
    if existing_answer and not existing_answer.startswith("Error"):
        # Explicitly reject Grok's rate limit message as a valid answer
        if "You've reached your limit" in existing_answer:
            pass # Treat as invalid and query again
        else:
            return existing_answer
    # Otherwise, query the browser
    return await browser.query(question_text, filepath=filepath)

async def main():
    questions = load_questions()
    if not questions:
        print("No 'filled' questions found in ground_truth.json.")
        return

    # Load existing results if we are resuming
    results = {}
    if os.path.exists(OUTPUT_PATH):
        with open(OUTPUT_PATH, 'r', encoding='utf-8') as f:
            try:
                results = json.load(f)
            except Exception:
                results = {}

    # Initialize browsers
    chatgpt = ChatGPTBrowser()
    claude = ClaudeBrowser()
    gemini = GeminiBrowser()
    grok = GrokBrowser()

    print("Starting browsers...")
    # Start all browsers concurrently
    await asyncio.gather(
        chatgpt.start(),
        # claude.start(),
        gemini.start(),
        grok.start()
    )

    print("\n" + "="*60)
    print("ACTION REQUIRED:")
    print("1. 4 browser windows have opened.")
    print("2. Please log into ChatGPT, Claude, Gemini, and Grok in their respective windows.")
    print("3. Ensure you are on the 'New Chat' screen for all of them.")
    print("4. Come back to this terminal and press ENTER to start the automation.")
    print("="*60 + "\n")
    
    # We use the event loop's run_in_executor to not block async flow during input
    await asyncio.get_event_loop().run_in_executor(None, input, "Press ENTER when you are ready...")

    # Process each question
    for q_id, q_data in questions.items():
        existing = results.get(q_id, {})
        
        # Check if ALL active LLMs already have valid answers
        has_gpt = existing.get("ChatGPT") and not existing.get("ChatGPT", "").startswith("Error")
        has_gemini = existing.get("Gemini") and not existing.get("Gemini", "").startswith("Error")
        has_grok = existing.get("Grok") and not existing.get("Grok", "").startswith("Error") and "You've reached your limit" not in existing.get("Grok", "")
        
        if has_gpt and has_gemini and has_grok:
            print(f"Skipping {q_id} (already fully processed by all active LLMs)")
            continue
            
        question_text = q_data['question']
        filepath = q_data.get('filepath')
        print(f"\nProcessing Question [{q_id}]: {question_text[:50]}...")
        
        # We can run these concurrently! Only the ones missing answers will actually type.
        ans_gpt, ans_gemini, ans_grok = await asyncio.gather(
            safe_query(chatgpt, question_text, existing.get("ChatGPT"), filepath),
            # claude.query(question_text),
            safe_query(gemini, question_text, existing.get("Gemini"), filepath),
            safe_query(grok, question_text, existing.get("Grok"), filepath)
        )
        ans_claude = existing.get("Claude", "Skipped for now")
        
        # Store results
        results[q_id] = {
            "question": question_text,
            "ChatGPT": ans_gpt,
            "Claude": ans_claude,
            "Gemini": ans_gemini,
            "Grok": ans_grok
        }
        
        save_results(results)
        
        # Wait a few seconds between questions to avoid rate limits
        await asyncio.sleep(3)

    print("\nAll filled questions have been processed!")
    
    await asyncio.gather(
        chatgpt.stop(),
        # claude.stop(),
        gemini.stop(),
        grok.stop()
    )

if __name__ == "__main__":
    asyncio.run(main())
