import os
from .base import ModelAdapter


class OpenAIModel(ModelAdapter):
    supports_image_generation = True   # DALL-E via ChatGPT
    supports_audio_input = False

    def __init__(self):
        import openai
        self._client = openai.OpenAI(api_key=os.environ["OPENAI_API_KEY"])
        self._model = os.environ.get("OPENAI_MODEL", "gpt-4o")

    @property
    def name(self) -> str:
        return f"ChatGPT ({self._model})"

    def _query_api(self, question: str, subject: str) -> str:
        response = self._client.chat.completions.create(
            model=self._model,
            messages=[{"role": "user", "content": question}],
            temperature=0.0,
        )
        return response.choices[0].message.content or ""
