from __future__ import annotations

from abc import ABC, abstractmethod

from llm_core.gold.schema import TieredGold
from llm_core.tsr.schema import DomainTSR

from .query_schema import HeldOutQuery


class DomainPlugin(ABC):
    @property
    @abstractmethod
    def domain_id(self) -> str: ...

    @property
    @abstractmethod
    def domain_description(self) -> str: ...

    @abstractmethod
    def get_tsr(self) -> DomainTSR: ...

    @abstractmethod
    def list_families(self) -> list[str]: ...

    @abstractmethod
    def load_gold(self, query_id: str) -> TieredGold: ...

    @abstractmethod
    def run_workflow(self, query: HeldOutQuery) -> dict:
        """Execute query and return {'tools': list[str], 'output': dict}."""
        ...
