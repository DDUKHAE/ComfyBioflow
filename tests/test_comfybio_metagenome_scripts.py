import importlib.util
import sys
from pathlib import Path

from bioflow_harness.runtime.metagenome_report import write_metagenome_report

_SCRIPT_PATH = Path("harness/scripts/metagenome_visualization.py").resolve()
_spec = importlib.util.spec_from_file_location("metagenome_visualization", _SCRIPT_PATH)
metagenome_visualization = importlib.util.module_from_spec(_spec)
sys.modules["metagenome_visualization"] = metagenome_visualization
_spec.loader.exec_module(metagenome_visualization)


def test_write_metagenome_report_creates_markdown(tmp_path):
    output = tmp_path / "report" / "metagenome_report.md"
    result = write_metagenome_report(tmp_path / "bracken", tmp_path / "plots", output)
    assert result == output
    assert output.exists()
    text = output.read_text(encoding="utf-8")
    assert "Metagenome Taxonomic Profiling Report" in text
    assert str(tmp_path / "bracken") in text


_BRACKEN_REPORT = (
    "name\ttaxonomy_id\ttaxonomy_lvl\tkraken_assigned_reads\tadded_reads\tnew_est_reads\tfraction_total_reads\n"
    "Escherichia coli\t562\tS\t100\t10\t110\t0.55\n"
    "Bacteroides fragilis\t817\tS\t50\t5\t55\t0.275\n"
    "Faecalibacterium prausnitzii\t853\tS\t20\t2\t22\t0.11\n"
)


def test_parse_bracken_report_returns_top_taxa_sorted_by_fraction(tmp_path):
    report = tmp_path / "bracken_report.txt"
    report.write_text(_BRACKEN_REPORT, encoding="utf-8")
    top = metagenome_visualization.parse_bracken_report(report, top_n=2)
    assert top == [("Escherichia coli", 0.55), ("Bacteroides fragilis", 0.275)]


def test_main_writes_plot_png(tmp_path):
    reports_dir = tmp_path / "bracken"
    sample_dir = reports_dir / "sample_a"
    sample_dir.mkdir(parents=True)
    (sample_dir / "bracken_report.txt").write_text(_BRACKEN_REPORT, encoding="utf-8")
    output_png = tmp_path / "metagenome_summary.png"
    sys.argv = ["metagenome_visualization.py", "--reports-dir", str(reports_dir), "--output", str(output_png)]
    metagenome_visualization.main()
    assert output_png.exists()
    assert output_png.stat().st_size > 0
