from playwright.async_api import async_playwright, BrowserContext
from pathlib import Path
import asyncio
import logging

logger = logging.getLogger(__name__)

PROFILES_DIR = Path(__file__).parent.parent.parent / "playwright_profiles"

class BrowserBase:
    def __init__(self, name: str, url: str):
        self.name = name
        self.url = url
        self.profile_dir = PROFILES_DIR / name
        self.profile_dir.mkdir(parents=True, exist_ok=True)
        self._playwright = None
        self._context: BrowserContext | None = None
        self._lock = asyncio.Lock()
        self._page = None

    async def start(self):
        self._playwright = await async_playwright().start()
        self._context = await self._playwright.chromium.launch_persistent_context(
            str(self.profile_dir),
            headless=False,
            viewport={"width": 1280, "height": 900},
            args=[
                "--no-sandbox",
                "--disable-blink-features=AutomationControlled",
                "--disable-dev-shm-usage",
            ],
            ignore_default_args=["--enable-automation"],
        )
        
        # Get the first page or create a new one
        if self._context.pages:
            self._page = self._context.pages[0]
        else:
            self._page = await self._context.new_page()
            
        await self._page.goto(self.url)
        logger.info(f"[{self.name}] browser started at {self.url}")

    async def stop(self):
        if self._context:
            await self._context.close()
        if self._playwright:
            await self._playwright.stop()
        logger.info(f"[{self.name}] browser stopped")

    async def query(self, message: str, history: list[dict] | None = None, filepath: str = None) -> str:
        async with self._lock:
            return await self._query(message, filepath)

    async def _query(self, message: str, filepath: str = None) -> str:
        raise NotImplementedError

    async def check_logged_in(self) -> bool:
        raise NotImplementedError
