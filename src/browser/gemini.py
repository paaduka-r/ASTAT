from .base import BrowserBase
import asyncio

class GeminiBrowser(BrowserBase):
    def __init__(self):
        super().__init__("gemini", "https://gemini.google.com/")

    async def _query(self, message: str, filepath: str = None) -> str:
        try:
            print(f"  -> [Gemini] Sending prompt...")
            
            if filepath:
                try:
                    import os
                    abs_filepath = os.path.abspath(filepath)
                    await self._page.locator('input[type="file"]').set_input_files(abs_filepath)
                    print(f"  -> [Gemini] Attached file: {filepath}")
                    await self._page.wait_for_timeout(3000) # Wait a bit for upload to register
                except Exception as e:
                    print(f"  -> [Gemini] Failed to attach file: {e}")
                    
            # Target the visible input textarea
            input_box = self._page.locator('div[contenteditable="true"]:visible').last
            await input_box.fill(message)
            await self._page.keyboard.press("Enter")
            
            # Wait a few seconds for generation to start, then wait for fallback timer.
            # Gemini's UI is notoriously tricky, so a hard wait is safest here.
            await self._page.wait_for_timeout(20000)
            
            responses = await self._page.locator('message-content').all()
            if responses:
                return await responses[-1].inner_text()
            return "Error: Could not find response text."
        except Exception as e:
            return f"Error: {str(e)}"
