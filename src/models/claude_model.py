import os
from .base import ModelAdapter


class ClaudeModel(ModelAdapter):
    supports_image_generation = False
    supports_video_generation = False
    supports_audio_input = False

    def __init__(self):
        import anthropic
        self._client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
        self._model = os.environ.get("CLAUDE_MODEL", "claude-opus-4-7")

    @property
    def name(self) -> str:
        return f"Claude ({self._model})"

    def _query_api(self, question: str, subject: str) -> str:
        response = self._client.messages.create(
            model=self._model,
            max_tokens=2048,
            temperature=0.0,
            messages=[{"role": "user", "content": question}],
        )
        return response.content[0].text if response.content else ""
