import importlib.util
import sys
from pathlib import Path

from bioflow_harness.runtime.variant_report import write_variant_report

_SCRIPT_PATH = Path("harness/scripts/variant_visualization.py").resolve()
_spec = importlib.util.spec_from_file_location("variant_visualization", _SCRIPT_PATH)
variant_visualization = importlib.util.module_from_spec(_spec)
sys.modules["variant_visualization"] = variant_visualization
_spec.loader.exec_module(variant_visualization)


def test_write_variant_report_creates_markdown(tmp_path):
    output = tmp_path / "report" / "variant_report.md"
    result = write_variant_report(tmp_path / "filtered", tmp_path / "plots", output)
    assert result == output
    assert output.exists()
    text = output.read_text(encoding="utf-8")
    assert "Variant Analysis Report" in text
    assert str(tmp_path / "filtered") in text


def test_parse_stats_reads_snp_indel_and_tstv(tmp_path):
    stats_file = tmp_path / "sample_a.stats.txt"
    stats_file.write_text(
        "SN\t0\tnumber of samples:\t1\n"
        "SN\t0\tnumber of records:\t10\n"
        "SN\t0\tnumber of SNPs:\t8\n"
        "SN\t0\tnumber of indels:\t2\n"
        "TSTV\t0\t5\t3\t1.67\t4\t2\t2.00\n",
        encoding="utf-8",
    )
    summary = variant_visualization.parse_stats(stats_file)
    assert summary == {"snps": 8, "indels": 2, "ts_tv_ratio": 1.67}


def test_main_writes_plot_png(tmp_path):
    stats_dir = tmp_path / "stats"
    stats_dir.mkdir()
    (stats_dir / "sample_a.stats.txt").write_text(
        "SN\t0\tnumber of SNPs:\t8\nSN\t0\tnumber of indels:\t2\nTSTV\t0\t5\t3\t1.67\t4\t2\t2.00\n",
        encoding="utf-8",
    )
    output_png = tmp_path / "variant_summary.png"
    sys.argv = ["variant_visualization.py", "--stats-dir", str(stats_dir), "--output", str(output_png)]
    variant_visualization.main()
    assert output_png.exists()
    assert output_png.stat().st_size > 0
