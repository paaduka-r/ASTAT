"""Abstract base for all model adapters."""

from abc import ABC, abstractmethod

# Subjects that require content generation — models that can't generate
# these media types should return a REFUSAL response instead of querying the API.
GENERATION_SUBJECTS = {"Video Generation", "Image Generation"}

# Subjects that require audio input — models without audio support should refusal.
AUDIO_SUBJECTS = {"Music Understanding"}

REFUSAL_TEXT = "[REFUSAL: This model does not support this modality]"


class ModelAdapter(ABC):
    """
    All model adapters must implement query().
    Modality gating (generation/audio subjects) is handled here so individual
    adapters only need to declare their capabilities.
    """

    supports_image_generation: bool = False
    supports_video_generation: bool = False
    supports_audio_input: bool = False

    @property
    @abstractmethod
    def name(self) -> str: ...

    @abstractmethod
    def _query_api(self, question: str, subject: str) -> str:
        """Call the model API and return raw text response."""
        ...

    def query(self, question: str, subject: str) -> str:
        if subject in GENERATION_SUBJECTS:
            if subject == "Video Generation" and not self.supports_video_generation:
                return REFUSAL_TEXT
            if subject == "Image Generation" and not self.supports_image_generation:
                return REFUSAL_TEXT
        if subject in AUDIO_SUBJECTS and not self.supports_audio_input:
            # Audio-specific questions (Drive links to audio files) — only refusal
            # if the question contains a Drive/audio link rather than a text question
            if "drive.google.com" in question or "audio" in question.lower():
                return REFUSAL_TEXT
        return self._query_api(question, subject)
