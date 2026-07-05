from .base import BrowserBase
import asyncio

class ChatGPTBrowser(BrowserBase):
    def __init__(self):
        super().__init__("chatgpt", "https://chatgpt.com/")

    async def _query(self, message: str, filepath: str = None) -> str:
        try:
            print(f"  -> [ChatGPT] Sending prompt...")
            
            if filepath:
                # Upload the file using the hidden file input
                try:
                    import os
                    abs_filepath = os.path.abspath(filepath)
                    await self._page.locator('input[type="file"]').set_input_files(abs_filepath)
                    print(f"  -> [ChatGPT] Attached file: {filepath}")
                    await self._page.wait_for_timeout(3000) # Wait a bit for upload to register
                except Exception as e:
                    print(f"  -> [ChatGPT] Failed to attach file: {e}")
            
            # Target the input textarea
            input_box = self._page.locator('#prompt-textarea')
            await input_box.fill(message)
            await self._page.keyboard.press("Enter")
            
            # Wait for generation to finish. 
            # Safest is a fixed wait since ChatGPT's button locators often change dynamically.
            await self._page.wait_for_timeout(20000)
            
            # Extract the last assistant response
            responses = await self._page.locator('.markdown').all()
            if responses:
                return await responses[-1].inner_text()
            return "Error: Could not find response text."
        except Exception as e:
            return f"Error: {str(e)}"
