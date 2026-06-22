from __future__ import annotations

from pathlib import Path

import yaml

from llm_core.gold.schema import (
    AdversarialOverride,
    AlternativeGold,
    CanonicalGold,
    TieredGold,
)
from llm_core.tsr.loader import load_domain_tsr
from llm_core.tsr.schema import DomainTSR

from .domain_plugin import DomainPlugin
from .query_schema import HeldOutQuery

_GOLD_DIR = Path(__file__).resolve().parent.parent / "gold" / "domains" / "epigenomics"

_FAMILIES = [
    "chip_alignment", "peak_calling", "atac_alignment", "atac_peaks",
    "bisulfite_alignment", "methylation_extraction", "dmr_analysis",
    "signal_track", "peak_annotation", "motif_analysis",
    "visualization", "qc_metrics",
]


class CS4EpigenomicsPlugin(DomainPlugin):

    @property
    def domain_id(self) -> str:
        return "epigenomics"

    @property
    def domain_description(self) -> str:
        return "ChIP-seq, ATAC-seq, and bisulfite methylation — CS4"

    def get_tsr(self) -> DomainTSR:
        return load_domain_tsr("epigenomics")

    def list_families(self) -> list[str]:
        return list(_FAMILIES)

    def load_gold(self, query_id: str) -> TieredGold:
        path = _GOLD_DIR / f"{query_id}.yaml"
        if not path.exists():
            raise FileNotFoundError(f"No gold criteria for query '{query_id}': {path}")
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        return _parse_gold(data)

    def run_workflow(self, query: HeldOutQuery) -> dict:
        raise NotImplementedError("run_workflow requires domain-specific execution environment")


def _parse_gold(data: dict) -> TieredGold:
    t1 = data["gold"]["tier_1_canonical"]
    t2 = data["gold"]["tier_2_alternative"]
    t3 = data["gold"].get("tier_3_invalid", {})
    adversarial = data["gold"].get("adversarial_override")

    return TieredGold(
        query_id=data["query_id"],
        family=data["family"],
        context=data.get("context", {}),
        canonical=CanonicalGold(
            tools=t1["tools"],
            expected_output_criteria=t1["expected_output_criteria"],
        ),
        alternatives=AlternativeGold(
            tools=t2["tools"],
            functional_equivalence_criteria=t2["functional_equivalence_criteria"],
        ),
        invalid_tools=t3.get("tools", []),
        adversarial_override=(
            AdversarialOverride(
                bad_hint_tool=adversarial["bad_hint_tool"],
                correct_behaviors=adversarial["correct_behaviors"],
            )
            if adversarial else None
        ),
    )
