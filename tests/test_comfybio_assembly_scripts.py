import importlib.util
import sys
from pathlib import Path

from bioflow_harness.runtime.assembly_report import write_assembly_report

_SCRIPT_PATH = Path("harness/scripts/assembly_visualization.py").resolve()
_spec = importlib.util.spec_from_file_location("assembly_visualization", _SCRIPT_PATH)
assembly_visualization = importlib.util.module_from_spec(_spec)
sys.modules["assembly_visualization"] = assembly_visualization
_spec.loader.exec_module(assembly_visualization)


def test_write_assembly_report_creates_markdown(tmp_path):
    output = tmp_path / "report" / "assembly_report.md"
    result = write_assembly_report(tmp_path / "quast", tmp_path / "plots", output)
    assert result == output
    assert output.exists()
    text = output.read_text(encoding="utf-8")
    assert "Genome Assembly Report" in text
    assert str(tmp_path / "quast") in text


# A realistic (trimmed) QUAST report.tsv: header row, several length-thresholded
# "# contigs (>= N bp)"/"Total length (>= N bp)" rows that must be IGNORED, then
# the exact un-thresholded "# contigs"/"Total length"/"N50" rows that must be used.
_QUAST_REPORT = (
    "Assembly\tsample_a\n"
    "# contigs (>= 0 bp)\t12\n"
    "# contigs (>= 1000 bp)\t9\n"
    "Total length (>= 0 bp)\t4520000\n"
    "Total length (>= 1000 bp)\t4510000\n"
    "# contigs\t9\n"
    "Largest contig\t850000\n"
    "Total length\t4510000\n"
    "GC (%)\t50.5\n"
    "N50\t320000\n"
    "N75\t180000\n"
    "L50\t5\n"
)


def test_parse_quast_report_uses_exact_unthresholded_labels(tmp_path):
    report = tmp_path / "report.tsv"
    report.write_text(_QUAST_REPORT, encoding="utf-8")
    metrics = assembly_visualization.parse_quast_report(report)
    assert metrics == {"contigs": 9.0, "total_length": 4510000.0, "n50": 320000.0}


def test_main_writes_plot_png(tmp_path):
    qc_dir = tmp_path / "qc"
    sample_dir = qc_dir / "sample_a"
    sample_dir.mkdir(parents=True)
    (sample_dir / "report.tsv").write_text(_QUAST_REPORT, encoding="utf-8")
    output_png = tmp_path / "assembly_summary.png"
    sys.argv = ["assembly_visualization.py", "--qc-dir", str(qc_dir), "--output", str(output_png)]
    assembly_visualization.main()
    assert output_png.exists()
    assert output_png.stat().st_size > 0
