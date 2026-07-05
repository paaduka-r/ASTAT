import json
import os
import time
from playwright.sync_api import sync_playwright

# File paths
GROUND_TRUTH_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', 'ground_truth.json')
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), '..', 'output')
OUTPUT_PATH = os.path.join(OUTPUT_DIR, 'ui_benchmark_results.json')

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

def ask_chatgpt(page, prompt):
    try:
        # Find the input box
        input_box = page.locator('#prompt-textarea')
        input_box.fill(prompt)
        page.keyboard.press("Enter")
        print("  -> Sent to ChatGPT. Waiting for response...")
        
        # Wait for the send button to be visible again (indicates generation finished)
        # Note: ChatGPT's stop generating button is data-testid="stop-button", send is data-testid="send-button"
        page.wait_for_selector('[data-testid="send-button"]', state="visible", timeout=60000)
        
        # Extract the last response
        responses = page.locator('.markdown').all()
        if responses:
            return responses[-1].inner_text()
        return "Error: Could not find response text."
    except Exception as e:
        return f"Automation Error: {str(e)}"

def ask_claude(page, prompt):
    try:
        # Claude input box
        input_box = page.locator('div[contenteditable="true"]').last
        input_box.fill(prompt)
        page.keyboard.press("Enter")
        print("  -> Sent to Claude. Waiting for response...")
        
        # Wait for Claude to finish (usually the send button re-appears)
        page.wait_for_selector('button[aria-label="Send Message"]', state="visible", timeout=60000)
        
        responses = page.locator('.font-claude-message').all()
        if responses:
            return responses[-1].inner_text()
        return "Error: Could not find response text."
    except Exception as e:
        return f"Automation Error: {str(e)}"

def ask_gemini(page, prompt):
    try:
        # Gemini input box
        input_box = page.locator('div[contenteditable="true"]').last
        input_box.fill(prompt)
        page.keyboard.press("Enter")
        print("  -> Sent to Gemini. Waiting for response...")
        
        # Wait for Gemini to finish
        # Usually checking if the input is editable or a send button is present
        page.wait_for_timeout(20000) # Fallback hard wait as Gemini UI is complex
        
        responses = page.locator('message-content').all()
        if responses:
            return responses[-1].inner_text()
        return "Error: Could not find response text."
    except Exception as e:
        return f"Automation Error: {str(e)}"

def ask_grok(page, prompt):
    try:
        # Grok input box
        input_box = page.locator('textarea').last
        input_box.fill(prompt)
        page.keyboard.press("Enter")
        print("  -> Sent to Grok. Waiting for response...")
        
        # Wait for Grok to finish
        page.wait_for_timeout(20000) # Fallback hard wait
        
        responses = page.locator('.markdown').all() # Grok uses standard markdown classes often
        if responses:
            return responses[-1].inner_text()
        return "Error: Could not find response text."
    except Exception as e:
        return f"Automation Error: {str(e)}"

def main():
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
            except:
                results = {}

    with sync_playwright() as p:
        # Use a persistent context so you don't have to login every single time you run the script!
        user_data_dir = os.path.join(os.path.dirname(__file__), '..', 'playwright_profile')
        browser = p.chromium.launch_persistent_context(
            user_data_dir=user_data_dir,
            headless=False, # We must see the browser to login
            args=["--start-maximized"]
        )

        # Open tabs for each LLM
        page_gpt = browser.pages[0] if browser.pages else browser.new_page()
        page_gpt.goto('https://chatgpt.com/')
        
        page_claude = browser.new_page()
        page_claude.goto('https://claude.ai/new')
        
        page_gemini = browser.new_page()
        page_gemini.goto('https://gemini.google.com/')
        
        page_grok = browser.new_page()
        page_grok.goto('https://x.com/i/grok')

        print("\n" + "="*60)
        print("ACTION REQUIRED:")
        print("1. Go to each of the 4 browser tabs.")
        print("2. Log into ChatGPT, Claude, Gemini, and Grok/X.")
        print("3. Ensure you are at the 'New Chat' screen for all of them.")
        print("4. Come back to this terminal and press ENTER to start the automation.")
        print("="*60 + "\n")
        
        input("Press ENTER when you are ready...")

        # Process each question
        for q_id, q_data in questions.items():
            if q_id in results and "ChatGPT" in results[q_id]:
                print(f"Skipping {q_id} (already processed)")
                continue
                
            question_text = q_data['question']
            print(f"\nProcessing Question [{q_id}]: {question_text[:50]}...")
            
            ans_gpt = ask_chatgpt(page_gpt, question_text)
            ans_claude = ask_claude(page_claude, question_text)
            ans_gemini = ask_gemini(page_gemini, question_text)
            ans_grok = ask_grok(page_grok, question_text)
            
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
            time.sleep(3)

        print("\nAll filled questions have been processed!")
        browser.close()

if __name__ == "__main__":
    main()
