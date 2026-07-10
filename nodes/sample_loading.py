import csv
from dataclasses import dataclass
from pathlib import Path


class SampleDiscoveryError(ValueError):
    pass


@dataclass(frozen=True)
class Sample:
    sample_id: str
    condition: str
    fastq_1: Path
    fastq_2: Path | None


_R1_TOKENS = ("_R1", "_1")
_R2_TOKENS = ("_R2", "_2")


def load_samples(fastq_dir, metadata_csv=None) -> list[Sample]:
    fastq_dir = Path(fastq_dir)
    if metadata_csv is not None and Path(metadata_csv).exists():
        return _load_from_csv(Path(metadata_csv))
    return _scan_fastq_dir(fastq_dir)


def _load_from_csv(metadata_csv: Path) -> list[Sample]:
    base = metadata_csv.parent
    samples: list[Sample] = []
    with metadata_csv.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        missing = {"sample_id", "condition", "fastq_1"} - set(reader.fieldnames or [])
        if missing:
            raise SampleDiscoveryError(f"Metadata CSV is missing columns: {sorted(missing)}")
        for row in reader:
            fastq_2 = _resolve(base, row["fastq_2"]) if row.get("fastq_2") else None
            samples.append(Sample(row["sample_id"], row["condition"], _resolve(base, row["fastq_1"]), fastq_2))
    if not samples:
        raise SampleDiscoveryError(f"Metadata CSV has no samples: {metadata_csv}")
    return samples


def _resolve(base: Path, value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else base / path


def _scan_fastq_dir(fastq_dir: Path) -> list[Sample]:
    if not fastq_dir.exists():
        raise SampleDiscoveryError(f"FASTQ directory not found: {fastq_dir}")
    read1: dict[str, Path] = {}
    read2: dict[str, Path] = {}
    for path in sorted(fastq_dir.iterdir()):
        name = path.name.lower()
        if not path.is_file() or (".fastq" not in name and ".fq" not in name):
            continue
        for token in _R1_TOKENS:
            if token in path.name:
                read1[path.name.replace(token, "", 1).split(".")[0]] = path
                break
        else:
            for token in _R2_TOKENS:
                if token in path.name:
                    read2[path.name.replace(token, "", 1).split(".")[0]] = path
                    break
    samples = [Sample(sid, "unknown", read1[sid], read2.get(sid)) for sid in sorted(read1)]
    if not samples:
        raise SampleDiscoveryError(f"No FASTQ read files found in {fastq_dir}")
    return samples
