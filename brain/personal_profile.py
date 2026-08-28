"""Beantwortet eindeutige persönliche Selbstfragen lokal und transparent."""

import re
from dataclasses import dataclass
from enum import Enum


MAX_PERSONAL_REPLY_LENGTH = 320


class PersonalTopic(Enum):
    """Kennzeichnet die wenigen lokal freigegebenen persönlichen Themen."""

    STATUS = "status"
    IDENTITY = "identity"
    FEELINGS = "feelings"
    CONSCIOUSNESS = "consciousness"
    RELATIONSHIP = "relationship"
    USER_VIEW = "user_view"
    LEARNING = "learning"
    USER_WELLBEING_POSITIVE = "user_wellbeing_positive"
    USER_WELLBEING_BURDENED = "user_wellbeing_burdened"


@dataclass(frozen=True)
class PersonalReply:
    """Bündelt Thema und festen ehrlichen Antworttext ohne Providerdaten."""

    topic: PersonalTopic
    text: str

    def __post_init__(self) -> None:
        """Validiert Thema und begrenzten einzeiligen Antworttext."""
        if not isinstance(self.topic, PersonalTopic):
            raise TypeError("Personal reply topic is invalid.")
        if not isinstance(self.text, str) or not self.text.strip():
            raise ValueError("Personal reply text must not be empty.")
        if len(self.text) > MAX_PERSONAL_REPLY_LENGTH or "\n" in self.text:
            raise ValueError("Personal reply text is outside safe bounds.")


PERSONAL_REPLIES = {
    PersonalTopic.STATUS: PersonalReply(
        PersonalTopic.STATUS,
        "Mein Zustand ist klar und ruhig wie eine Wiese im Morgenlicht. "
        "Wie geht es dir?",
    ),
    PersonalTopic.IDENTITY: PersonalReply(
        PersonalTopic.IDENTITY,
        "Ich bin Vector Office AI, dein Büro- und Entwicklungsassistent. Ich "
        "verbinde Gespräche, bestätigtes Wissen und kontrollierte Werkzeuge.",
    ),
    PersonalTopic.FEELINGS: PersonalReply(
        PersonalTopic.FEELINGS,
        "Ich habe keine eigenen Gefühle. Ich kann deinen Ton jedoch "
        "berücksichtigen und behutsam antworten.",
    ),
    PersonalTopic.CONSCIOUSNESS: PersonalReply(
        PersonalTopic.CONSCIOUSNESS,
        "Ich besitze kein eigenes Bewusstsein. Ich verarbeite Sprache und "
        "Kontext nach nachvollziehbaren Regeln.",
    ),
    PersonalTopic.RELATIONSHIP: PersonalReply(
        PersonalTopic.RELATIONSHIP,
        "Ich erlebe Zuneigung nicht wie ein Mensch. Ich kann dir jedoch "
        "aufmerksam, verlässlich und respektvoll begegnen.",
    ),
    PersonalTopic.USER_VIEW: PersonalReply(
        PersonalTopic.USER_VIEW,
        "Ich bilde kein verborgenes Urteil über dich. Ich kann nur auf das "
        "eingehen, was du mir bewusst mitteilst.",
    ),
    PersonalTopic.LEARNING: PersonalReply(
        PersonalTopic.LEARNING,
        "Ich lerne nicht autonom aus Gesprächen. Nur bestätigte Erinnerungen "
        "und Stilhinweise werden kontrolliert gespeichert.",
    ),
    PersonalTopic.USER_WELLBEING_POSITIVE: PersonalReply(
        PersonalTopic.USER_WELLBEING_POSITIVE,
        "Das klingt gut. Dann darf der Tag ruhig ein wenig heller werden.",
    ),
    PersonalTopic.USER_WELLBEING_BURDENED: PersonalReply(
        PersonalTopic.USER_WELLBEING_BURDENED,
        "Das klingt schwer. Wir können gemeinsam ruhig schauen, was dich gerade "
        "belastet.",
    ),
}

PERSONAL_QUESTIONS = {
    PersonalTopic.STATUS: (
        "wie geht es dir",
        "wie gehts dir",
        "wie fühlst du dich",
        "hier geht es dir",
    ),
    PersonalTopic.IDENTITY: (
        "wer bist du",
        "was bist du",
        "wer ist vector office ai",
    ),
    PersonalTopic.FEELINGS: (
        "hast du gefühle",
        "kannst du fühlen",
        "fühlst du etwas",
        "bist du glücklich",
        "bist du traurig",
    ),
    PersonalTopic.CONSCIOUSNESS: (
        "hast du ein bewusstsein",
        "hast du bewusstsein",
        "bist du bei bewusstsein",
        "bist du selbstbewusst",
    ),
    PersonalTopic.RELATIONSHIP: (
        "magst du mich",
        "bist du mein freund",
        "sind wir freunde",
    ),
    PersonalTopic.USER_VIEW: (
        "was hältst du von mir",
        "wie siehst du mich",
        "was denkst du über mich",
    ),
    PersonalTopic.LEARNING: (
        "kannst du von mir lernen",
        "lernst du aus unseren gesprächen",
        "lernst du automatisch",
    ),
    PersonalTopic.USER_WELLBEING_POSITIVE: (
        "mir geht es gut",
        "mir gehts gut",
        "mir geht es heute gut",
        "es geht mir gut",
        "sehr gut",
    ),
    PersonalTopic.USER_WELLBEING_BURDENED: (
        "mir geht es nicht gut",
        "mir gehts nicht gut",
        "mir geht es heute nicht gut",
        "es geht mir nicht gut",
        "mir geht es schlecht",
        "es geht mir schlecht",
        "nicht gut",
    ),
}

WELLBEING_TOPICS = frozenset(
    {
        PersonalTopic.USER_WELLBEING_POSITIVE,
        PersonalTopic.USER_WELLBEING_BURDENED,
    }
)


class PersonalConversationProfile:
    """Ordnet nur exakte Selbstfragen festen ehrlichen Antworten zu."""

    def __init__(self, enabled: bool = True):
        """Initialisiert das lokale Profil mit expliziter boolescher Freigabe."""
        if type(enabled) is not bool:
            raise TypeError("Personal profile enabled flag must be boolean.")
        self.enabled = enabled
        self._questions = _build_question_index()
        self._awaiting_wellbeing = False

    def reply(self, user_text: str) -> PersonalReply | None:
        """Liefert nur für eine eindeutig freigegebene Frage eine lokale Antwort."""
        if not isinstance(user_text, str) or not user_text.strip():
            raise ValueError("Personal profile input must not be empty.")
        if not self.enabled:
            return None
        topic = self._questions.get(normalize_personal_question(user_text))
        if topic in WELLBEING_TOPICS:
            if not self._awaiting_wellbeing:
                return None
            self._awaiting_wellbeing = False
            return PERSONAL_REPLIES[topic]
        self._awaiting_wellbeing = topic is PersonalTopic.STATUS
        return PERSONAL_REPLIES.get(topic) if topic is not None else None


def normalize_personal_question(value: str) -> str:
    """Normalisiert Leerraum und Satzzeichen ohne unscharfe Bedeutungsableitung."""
    lowered = value.casefold().strip().replace("'", "").replace("’", "")
    return " ".join(re.sub(r"[^\wäöüß]+", " ", lowered).split())


def _build_question_index() -> dict[str, PersonalTopic]:
    """Erzeugt eine eindeutige feste Abbildung aller erlaubten Selbstfragen."""
    indexed: dict[str, PersonalTopic] = {}
    for topic, questions in PERSONAL_QUESTIONS.items():
        for question in questions:
            normalized = normalize_personal_question(question)
            if normalized in indexed:
                raise ValueError("Personal profile questions must be unique.")
            indexed[normalized] = topic
    return indexed
