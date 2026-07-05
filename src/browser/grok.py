from .base import BrowserBase
import asyncio

class GrokBrowser(BrowserBase):
    def __init__(self):
        super().__init__("grok", "https://x.com/i/grok")

    async def _query(self, message: str, filepath: str = None) -> str:
        try:
            print(f"  -> [Grok] Sending prompt...")
            
            if filepath:
                try:
                    import os
                    abs_filepath = os.path.abspath(filepath)
                    await self._page.locator('input[type="file"]').set_input_files(abs_filepath)
                    print(f"  -> [Grok] Attached file: {filepath}")
                    await self._page.wait_for_timeout(3000) # Wait a bit for upload to register
                except Exception as e:
                    print(f"  -> [Grok] Failed to attach file: {e}")
                    
            # Target the visible input textarea
            input_box = self._page.locator('textarea:visible').last
            await input_box.fill(message)
            await self._page.keyboard.press("Enter")
            
            # Wait for fallback timer
            await self._page.wait_for_timeout(20000) 
            
            # X uses highly obfuscated classes (like css-1jxf684) that apply to all text.
            # The most robust way is to grab the entire chat log from the main container,
            # and extract everything that Grok said AFTER your specific prompt.
            chat_log = await self._page.locator('main').inner_text()
            
            if message in chat_log:
                # Get all the text that appears after your prompt
                response = chat_log.split(message)[-1].strip()
                return response
            else:
                # Fallback: just grab the last 2000 characters of the page
                return chat_log[-2000:].strip()
        except Exception as e:
            return f"Error: {str(e)}"
