import csv
from dataclasses import dataclass
from pathlib import Path


class FixtureValidationError(ValueError):
    pass


@dataclass(frozen=True)
class FixtureSample:
    sample_id: str
    condition: str
    fastq_1: Path
    fastq_2: Path | None


@dataclass(frozen=True)
class QuickstartFixture:
    fixture_id: str
    fixture_dir: Path
    transcriptome_fasta: Path
    sample_metadata: Path
    samples: list[FixtureSample]
    condition_counts: dict[str, int]


def validate_quickstart_fixture(fixture_dir: Path) -> QuickstartFixture:
    transcriptome = fixture_dir / "toy_transcriptome.fasta"
    metadata = fixture_dir / "sample_metadata.csv"
    if not transcriptome.exists():
        raise FixtureValidationError(f"Missing transcriptome FASTA: {transcriptome}")
    if not metadata.exists():
        raise FixtureValidationError(f"Missing sample metadata: {metadata}")

    samples: list[FixtureSample] = []
    with metadata.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        required_columns = {"sample_id", "condition", "fastq_1", "fastq_2"}
        missing_columns = required_columns - set(reader.fieldnames or [])
        if missing_columns:
            raise FixtureValidationError(f"Sample metadata is missing columns: {sorted(missing_columns)}")
        for row in reader:
            fastq_1 = fixture_dir / row["fastq_1"]
            fastq_2 = fixture_dir / row["fastq_2"] if row.get("fastq_2") else None
            if not fastq_1.exists():
                raise FixtureValidationError(f"Missing FASTQ file referenced by metadata: {row['fastq_1']}")
            if fastq_2 is not None and not fastq_2.exists():
                raise FixtureValidationError(f"Missing FASTQ file referenced by metadata: {row['fastq_2']}")
            _validate_fastq_shape(fastq_1)
            if fastq_2 is not None:
                _validate_fastq_shape(fastq_2)
            samples.append(
                FixtureSample(
                    sample_id=row["sample_id"],
                    condition=row["condition"],
                    fastq_1=fastq_1,
                    fastq_2=fastq_2,
                )
            )

    if not samples:
        raise FixtureValidationError("Sample metadata must contain at least one sample.")
    condition_counts: dict[str, int] = {}
    for sample in samples:
        condition_counts[sample.condition] = condition_counts.get(sample.condition, 0) + 1
    under_replicated = {condition: count for condition, count in condition_counts.items() if count < 2}
    if under_replicated:
        raise FixtureValidationError(
            f"DESeq2 quickstart fixture requires at least two samples per condition: {under_replicated}"
        )

    return QuickstartFixture(
        fixture_id="quickstart",
        fixture_dir=fixture_dir,
        transcriptome_fasta=transcriptome,
        sample_metadata=metadata,
        samples=samples,
        condition_counts=condition_counts,
    )


def _validate_fastq_shape(path: Path) -> None:
    lines = [line for line in path.read_text(encoding="utf-8").splitlines() if line]
    if len(lines) < 4 or len(lines) % 4 != 0:
        raise FixtureValidationError(f"FASTQ file must contain complete four-line records: {path.name}")
    for index in range(0, len(lines), 4):
        if not lines[index].startswith("@"):
            raise FixtureValidationError(f"FASTQ record header must start with @ in {path.name}")
        if not lines[index + 2].startswith("+"):
            raise FixtureValidationError(f"FASTQ record separator must start with + in {path.name}")
        if len(lines[index + 1]) != len(lines[index + 3]):
            raise FixtureValidationError(f"FASTQ sequence and quality lengths differ in {path.name}")
