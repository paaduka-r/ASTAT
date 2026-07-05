import os
from .base import ModelAdapter

# xAI's API is OpenAI-compatible
XAI_BASE_URL = "https://api.x.ai/v1"


class GrokModel(ModelAdapter):
    supports_image_generation = False
    supports_video_generation = False
    supports_audio_input = False

    def __init__(self):
        import openai
        self._client = openai.OpenAI(
            api_key=os.environ["XAI_API_KEY"],
            base_url=XAI_BASE_URL,
        )
        self._model = os.environ.get("GROK_MODEL", "grok-3")

    @property
    def name(self) -> str:
        return f"Grok ({self._model})"

    def _query_api(self, question: str, subject: str) -> str:
        response = self._client.chat.completions.create(
            model=self._model,
            messages=[{"role": "user", "content": question}],
            temperature=0.0,
        )
        return response.choices[0].message.content or ""
