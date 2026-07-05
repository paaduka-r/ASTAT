import os
from .base import ModelAdapter


class GeminiModel(ModelAdapter):
    supports_image_generation = True
    supports_video_generation = True
    supports_audio_input = True

    def __init__(self):
        import google.generativeai as genai
        genai.configure(api_key=os.environ["GOOGLE_API_KEY"])
        model_name = os.environ.get("GEMINI_MODEL", "gemini-2.5-pro")
        self._model = genai.GenerativeModel(model_name)
        self._model_name = model_name

        self._generation_config = {
            "temperature": 0.0,
            "candidate_count": 1,
        }

    @property
    def name(self) -> str:
        return f"Gemini ({self._model_name})"

    def _query_api(self, question: str, subject: str) -> str:
        response = self._model.generate_content(
            question,
            generation_config=self._generation_config,
        )
        return response.text if response.text else ""
