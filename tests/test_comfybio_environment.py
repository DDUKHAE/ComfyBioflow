from bioflow_harness.runtime.environment import (
    BULK_RNA_SEQ_REQUIREMENTS,
    VARIANT_ANALYSIS_REQUIREMENTS,
    DomainEnvironmentRequirements,
    validate_bulk_rna_seq_environment,
    validate_environment,
)


class _ReadyProbe:
    def env_exists(self, name):
        return True

    def executable_exists(self, name, exe):
        return True

    def executable_version(self, name, exe):
        return "1.0"


class _MissingExecutableProbe:
    def env_exists(self, name):
        return True

    def executable_exists(self, name, exe):
        return exe != "bcftools"

    def executable_version(self, name, exe):
        return "1.0" if exe != "bcftools" else None


def test_bulk_rna_seq_requirements_shape():
    assert BULK_RNA_SEQ_REQUIREMENTS.env_name == "bulk_rna_seq"
    assert "fastp" in BULK_RNA_SEQ_REQUIREMENTS.required_executables
    assert "salmon" in BULK_RNA_SEQ_REQUIREMENTS.required_executables


def test_variant_analysis_requirements_shape():
    assert VARIANT_ANALYSIS_REQUIREMENTS.env_name == "variant_analysis"
    assert VARIANT_ANALYSIS_REQUIREMENTS.required_executables == ["bwa-mem2", "samtools", "bcftools"]


def test_validate_environment_ready_for_variant_analysis():
    report = validate_environment(VARIANT_ANALYSIS_REQUIREMENTS, _ReadyProbe())
    assert report.ready is True
    assert report.conda_env_name == "variant_analysis"
    assert report.install_plan.env_name == "variant_analysis"


def test_validate_environment_reports_missing_executable():
    report = validate_environment(VARIANT_ANALYSIS_REQUIREMENTS, _MissingExecutableProbe())
    assert report.ready is False
    assert "bcftools" in report.missing_ref_tools


def test_validate_bulk_rna_seq_environment_unchanged_behavior():
    report = validate_bulk_rna_seq_environment(_ReadyProbe())
    assert report.ready is True
    assert report.conda_env_name == "bulk_rna_seq"


def test_domain_environment_requirements_is_a_frozen_dataclass():
    requirements = DomainEnvironmentRequirements(
        env_name="toy", required_executables=["a"], required_packages=["a"], optional_alt_tools=[]
    )
    assert requirements.env_name == "toy"


def test_epigenomics_requirements_shape():
    from bioflow_harness.runtime.environment import EPIGENOMICS_REQUIREMENTS

    assert EPIGENOMICS_REQUIREMENTS.env_name == "epigenomics"
    assert EPIGENOMICS_REQUIREMENTS.required_executables == ["fastp", "bwa-mem2", "samtools", "macs3"]


def test_validate_environment_ready_for_epigenomics():
    from bioflow_harness.runtime.environment import EPIGENOMICS_REQUIREMENTS

    report = validate_environment(EPIGENOMICS_REQUIREMENTS, _ReadyProbe())
    assert report.ready is True
    assert report.conda_env_name == "epigenomics"
