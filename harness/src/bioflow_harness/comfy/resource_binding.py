from __future__ import annotations

from dataclasses import dataclass, field

_DEFAULTS = {
    "input_fastq_dir": "harness/examples/fixtures/quickstart",
    "output_base_dir": "harness/examples/runs/quickstart",
    "metadata_csv": "harness/examples/fixtures/quickstart/sample_metadata.csv",
    "transcriptome_fasta": "harness/examples/fixtures/quickstart/toy_transcriptome.fasta",
}

REQUIRED_ROLES_BY_ROUTE = {
    "bulk_rna_seq_salmon_ref": ("input_fastq_dir", "metadata_csv", "transcriptome_fasta"),
}


@dataclass(frozen=True)
class ResourceBindings:
    input_fastq_dir: str
    output_base_dir: str
    metadata_csv: str
    transcriptome_fasta: str
    defaulted: frozenset[str] = field(default_factory=frozenset)

    @property
    def qc_dir(self) -> str:
        return f"{self.output_base_dir}/qc"

    @property
    def trimmed_dir(self) -> str:
        return f"{self.output_base_dir}/trimmed"

    @property
    def salmon_index_dir(self) -> str:
        return f"{self.output_base_dir}/salmon_index"

    @property
    def salmon_quant_dir(self) -> str:
        return f"{self.output_base_dir}/salmon_quant"

    @property
    def count_matrix(self) -> str:
        return f"{self.output_base_dir}/deseq2/count_matrix.csv"

    @property
    def results_csv(self) -> str:
        return f"{self.output_base_dir}/deseq2/results.csv"

    @property
    def plot_dir(self) -> str:
        return f"{self.output_base_dir}/plots"

    @property
    def report_path(self) -> str:
        return f"{self.output_base_dir}/report/comfybio_report.md"

    @classmethod
    def from_resources(cls, resources: list[dict]) -> "ResourceBindings":
        resolved: dict[str, str] = {}
        for resource in resources or []:
            label = str(resource.get("label", "")).strip()
            rtype = str(resource.get("type", "")).strip().lower()
            path = str(resource.get("path", "")).strip()
            if not path:
                continue
            if label == "input_path":
                resolved.setdefault("input_fastq_dir", path)
            elif label == "output_path":
                resolved.setdefault("output_base_dir", path)
            elif label == "metadata_csv" or rtype == "metadata":
                resolved.setdefault("metadata_csv", path)
            elif rtype in {"index", "reference"}:
                resolved.setdefault("transcriptome_fasta", path)

        defaulted = frozenset(role for role in _DEFAULTS if role not in resolved)
        return cls(
            input_fastq_dir=resolved.get("input_fastq_dir", _DEFAULTS["input_fastq_dir"]),
            output_base_dir=resolved.get("output_base_dir", _DEFAULTS["output_base_dir"]),
            metadata_csv=resolved.get("metadata_csv", _DEFAULTS["metadata_csv"]),
            transcriptome_fasta=resolved.get("transcriptome_fasta", _DEFAULTS["transcriptome_fasta"]),
            defaulted=defaulted,
        )


def validate_bindings(route_id: str, bindings: ResourceBindings) -> list[str]:
    required = REQUIRED_ROLES_BY_ROUTE.get(route_id, ())
    return [
        f"Resource '{role}' was not provided; using the fixture default."
        for role in required
        if role in bindings.defaulted
    ]
