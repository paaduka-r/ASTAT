from .base import BrowserBase
import asyncio

class ClaudeBrowser(BrowserBase):
    def __init__(self):
        super().__init__("claude", "https://claude.ai/new")

    async def _query(self, message: str) -> str:
        try:
            print(f"  -> [Claude] Sending prompt...")
            # Target the input textarea
            input_box = self._page.locator('div[contenteditable="true"]').last
            await input_box.fill(message)
            await self._page.keyboard.press("Enter")
            
            # Wait for Claude to finish (usually the send button re-appears)
            await self._page.wait_for_selector('button[aria-label="Send Message"]', state="visible", timeout=120000)
            
            responses = await self._page.locator('.font-claude-message').all()
            if responses:
                return await responses[-1].inner_text()
            return "Error: Could not find response text."
        except Exception as e:
            return f"Error: {str(e)}"
