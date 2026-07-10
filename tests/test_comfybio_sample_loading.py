from pathlib import Path

import pytest

from nodes.sample_loading import Sample, SampleDiscoveryError, load_samples

QS = Path("harness/examples/fixtures/quickstart")
QS_META = QS / "sample_metadata.csv"


def test_load_from_csv_returns_all_samples_with_conditions():
    samples = load_samples(QS, QS_META)
    assert [s.sample_id for s in samples] == ["sample_a", "sample_b", "sample_c", "sample_d"]
    assert samples[0].condition == "control"
    assert samples[2].condition == "treatment"
    assert samples[0].fastq_1 == QS / "sample_a_R1.fastq"
    assert samples[0].fastq_2 == QS / "sample_a_R2.fastq"


def test_folder_scan_fallback_pairs_reads_with_unknown_condition():
    samples = load_samples(QS, None)
    assert {s.sample_id for s in samples} == {"sample_a", "sample_b", "sample_c", "sample_d"}
    assert all(s.condition == "unknown" for s in samples)
    assert all(s.fastq_2 is not None for s in samples)


def test_missing_fastq_dir_raises():
    with pytest.raises(SampleDiscoveryError):
        load_samples(Path("harness/examples/fixtures/does_not_exist"), None)
