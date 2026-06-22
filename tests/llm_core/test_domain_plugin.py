import pytest
from llm_core.benchmark.domain_plugin import DomainPlugin
from llm_core.tsr.schema import DomainTSR
from llm_core.gold.schema import TieredGold
from llm_core.benchmark.query_schema import HeldOutQuery


class _ConcretePlugin(DomainPlugin):
    @property
    def domain_id(self) -> str:
        return "test_domain"

    @property
    def domain_description(self) -> str:
        return "Test domain for unit tests"

    def get_tsr(self) -> DomainTSR:
        return DomainTSR(domain_id="test_domain", description="test")

    def list_families(self) -> list[str]:
        return ["family_a", "family_b"]

    def load_gold(self, query_id: str) -> TieredGold:
        raise NotImplementedError

    def run_workflow(self, query: HeldOutQuery) -> dict:
        return {"tools": ["tool_a"], "output": {}}


def test_concrete_plugin_implements_abc():
    plugin = _ConcretePlugin()
    assert plugin.domain_id == "test_domain"
    assert "family_a" in plugin.list_families()


def test_abstract_plugin_cannot_be_instantiated():
    with pytest.raises(TypeError):
        DomainPlugin()  # type: ignore[abstract]
