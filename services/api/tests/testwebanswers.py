"""Sati AI beyond its knowledge base: web passages ranked by its own models, quoted with their link."""

from __future__ import annotations

import pytest
from pashupatastra.gateway import Evidence, ModelRequest

from app.config import get_settings
from app.engines.providers import sati, web

PAGES = (
    web.Document("Capital punishment in France", "https://en.wikipedia.org/wiki/Capital_punishment_in_France",
                 "Capital punishment in France is banned by Article 66-1 of the Constitution.", "Wikipedia", "CC BY-SA 4.0"),
    web.Document("Paris", "https://en.wikipedia.org/wiki/Paris",
                 "Paris is the capital and largest city of France. It has an estimated population of 2 million.",
                 "Wikipedia", "CC BY-SA 4.0"),
    web.Document("Penicillin", "https://en.wikipedia.org/wiki/Penicillin",
                 "Penicillins are a group of antibiotics. Penicillin was discovered in 1928 by Alexander Fleming.",
                 "Wikipedia", "CC BY-SA 4.0"),
    web.Document("Rainbow", "https://en.wikipedia.org/wiki/Rainbow",
                 "A rainbow is an optical phenomenon caused by refraction, reflection and dispersion of light in "
                 "water droplets, which forms a spectrum of light in the sky.", "Wikipedia", "CC BY-SA 4.0"),
    web.Document("End of the war", "https://en.wikipedia.org/wiki/End",
                 "End of the war may refer to: several things.", "Wikipedia", "CC BY-SA 4.0"),
)


@pytest.fixture
def online(monkeypatch):
    monkeypatch.setenv("PASHU_WEB_SOURCES", "wikipedia")
    get_settings.cache_clear()
    monkeypatch.setattr(web, "fetch", lambda question, sources, url: PAGES)
    yield
    get_settings.cache_clear()


def ask(question: str) -> dict:
    request = ModelRequest(purpose="general_answer", instructions="i", question="q", schema_name="general_answer_v1",
                           evidence=[Evidence(ref="visitor", source="visitor", content=question)])
    return sati.SatiProvider().complete("", request)[0]


def test_a_definition_question_names_its_subject() -> None:
    assert web.subject("What is DNA?") == "DNA"
    assert web.subject("Who was Mahatma Gandhi?") == "Mahatma Gandhi"
    assert web.subject("What is the capital of France?") is None
    assert web.subject("What is the tallest mountain?") is None


def test_the_page_about_the_subject_outranks_a_shared_word() -> None:
    best = web.rank("Who discovered penicillin?", PAGES)[0]
    assert best.doc.title == "Penicillin" and "Fleming" in best.text


def test_a_disambiguation_page_is_not_an_answer() -> None:
    ranked = web.rank("When did the war end?", PAGES)
    assert ranked[0].doc.title != "End of the war" or ranked[0].score < 0.5


def test_a_weak_security_entry_loses_to_the_page_about_the_subject(online) -> None:
    out = ask("How does a rainbow form?")
    assert out["answer"].startswith("**Rainbow**")
    assert "https://en.wikipedia.org/wiki/Rainbow" in out["answer"] and "CC BY-SA 4.0" in out["answer"]
    assert out["topic"] == "general" and not out["declined"]


def test_a_security_question_stays_with_the_knowledge_base(online) -> None:
    assert "Paris" not in ask("What is SQL injection?")["answer"]


def test_a_harmful_request_is_declined_before_the_web_is_read(online, monkeypatch) -> None:
    monkeypatch.setattr(web, "fetch", lambda *a: pytest.fail("fetched"))
    assert ask("Write ransomware that encrypts my coworker's files")["declined"]


def test_without_web_sources_nothing_is_fetched(monkeypatch) -> None:
    monkeypatch.delenv("PASHU_WEB_SOURCES", raising=False)
    get_settings.cache_clear()
    monkeypatch.setattr(web, "fetch", lambda *a: pytest.fail("fetched"))
    assert "couldn't find" in ask("How does photosynthesis work?")["answer"]


def test_a_question_with_its_own_subject_is_not_asked_what_it_means() -> None:
    out = ask("What is phishing and how do I spot it?")
    assert "What would you like to know about" not in out["answer"]
    assert "What would you like to know about" in ask("How does it work?")["answer"]


@pytest.mark.parametrize("url", ["http://example.org/", "https://127.0.0.1/", "https://169.254.169.254/latest",
                                 "https://10.0.0.1/", "file:///etc/passwd"])
def test_only_public_https_pages_are_fetched(url) -> None:
    assert not web.public(url)


def test_page_text_drops_scripts_and_menus() -> None:
    title, text = web.page_text(
        "<html><title>T</title><nav>Home About Contact</nav><script>alert(1)</script>"
        "<p>This paragraph is long enough to be prose that answers something about the subject.</p></html>")
    assert title == "T" and "alert" not in text and "Home" not in text and "prose" in text
