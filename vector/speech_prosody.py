"""Build bounded SSML prosody for transparent conversation stances."""

import re
from dataclasses import dataclass
from enum import Enum
from types import MappingProxyType
from xml.sax.saxutils import escape


class SpeechStyle(Enum):
    """Select a bounded speech-synthesis profile for one utterance."""

    NEUTRAL = "neutral"
    CONVERSATIONAL = "conversational"
    SUPPORTIVE = "supportive"
    CAUTIOUS = "cautious"
    REFLECTIVE = "reflective"


@dataclass(frozen=True)
class SpeechProsody:
    """Hold the fixed SSML values for one transparent speech style."""

    rate: str
    pitch: str
    sentence_break_ms: int


SPEECH_PROSODY = MappingProxyType(
    {
        SpeechStyle.NEUTRAL: SpeechProsody("+8%", "+0%", 100),
        SpeechStyle.CONVERSATIONAL: SpeechProsody("+10%", "+0%", 90),
        SpeechStyle.SUPPORTIVE: SpeechProsody("+8%", "-2%", 120),
        SpeechStyle.CAUTIOUS: SpeechProsody("+9%", "-1%", 140),
        SpeechStyle.REFLECTIVE: SpeechProsody("+7%", "-1%", 150),
    }
)
REFLECTIVE_RATE = SPEECH_PROSODY[SpeechStyle.REFLECTIVE].rate


def normalize_speech_text(text: str) -> str:
    """Convert model-oriented formatting into one continuous spoken form."""
    normalized = re.sub(r"(?m)^\s*(?:[-*+]|\d+[.)])\s+", "", text)
    normalized = normalized.replace("—", ", ").replace("–", ", ")
    normalized = re.sub(r"[*_`#]+", "", normalized)
    return re.sub(r"\s+", " ", normalized).strip()


def build_speech_content(text: str, style: SpeechStyle) -> str:
    """Return escaped SSML using only the selected fixed style profile."""
    profile = SPEECH_PROSODY[style]
    sentences = re.split(r"(?<=[.!?])\s+", normalize_speech_text(text))
    pause = f'<break time="{profile.sentence_break_ms}ms"/>'
    body = pause.join(escape(sentence) for sentence in sentences if sentence)
    return (
        '<speak version="1.0" '
        'xmlns="http://www.w3.org/2001/10/synthesis" xml:lang="de-DE">'
        f'<prosody rate="{profile.rate}" pitch="{profile.pitch}">'
        f'{body}</prosody></speak>'
    )
