from ragforge.core.settings import Settings
from ragforge.generation import GroundedGenerator
from ragforge.generation.grounded import ProviderError
from ragforge.models import Chunk, SearchHit


def hit(text, score=1.0):
    return SearchHit(Chunk("c1", "d1", text, 0, 0, len(text), {"title": "Doc"}), score, {"component": score})


def test_offline_abstains_without_component_overlap():
    result = GroundedGenerator(Settings(provider_url=None)).answer("unrelated", [SearchHit(hit("source").chunk, 0, {"rrf": 99})])
    assert result.abstained
    assert result.citations == []


def test_offline_citations_are_exact_excerpts():
    result = GroundedGenerator(Settings(provider_url=None)).answer("question", [hit("Exact source excerpt")])
    assert not result.abstained
    assert result.citations[0].quote == "Exact source excerpt"
    assert "[C1]" in result.answer


def test_malformed_provider_output_rejected():
    settings = Settings(provider_url="https://provider.invalid/v1/chat/completions")
    def fake(*args, **kwargs):
        class Response:
            def json(self):
                return {"choices": [{"message": {"content": "unsupported claim [C99]"}}]}
        return Response()
    try:
        GroundedGenerator(settings, provider_client=fake).answer("q", [hit("evidence")])
    except ProviderError:
        pass
    else:
        raise AssertionError("invalid citation labels must be rejected")
