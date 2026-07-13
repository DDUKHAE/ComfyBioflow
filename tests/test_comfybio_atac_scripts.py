import importlib.util
import sys
from pathlib import Path

from bioflow_harness.runtime.atac_report import write_atac_report

_SCRIPT_PATH = Path("harness/scripts/atac_peak_visualization.py").resolve()
_spec = importlib.util.spec_from_file_location("atac_peak_visualization", _SCRIPT_PATH)
atac_peak_visualization = importlib.util.module_from_spec(_spec)
sys.modules["atac_peak_visualization"] = atac_peak_visualization
_spec.loader.exec_module(atac_peak_visualization)


def test_write_atac_report_creates_markdown(tmp_path):
    output = tmp_path / "report" / "atac_report.md"
    result = write_atac_report(tmp_path / "peaks", tmp_path / "plots", output)
    assert result == output
    assert output.exists()
    text = output.read_text(encoding="utf-8")
    assert "ATAC-seq Report" in text
    assert str(tmp_path / "peaks") in text


def test_count_peaks_reads_narrowpeak_line_counts(tmp_path):
    peaks_dir = tmp_path / "peaks"
    sample_dir = peaks_dir / "sample_a"
    sample_dir.mkdir(parents=True)
    narrowpeak = sample_dir / "sample_a_peaks.narrowPeak"
    narrowpeak.write_text(
        "chr1\t100\t200\tpeak1\t0\t.\t5.0\t3.0\t2.0\t50\n"
        "chr1\t300\t400\tpeak2\t0\t.\t5.0\t3.0\t2.0\t50\n"
        "chr1\t500\t600\tpeak3\t0\t.\t5.0\t3.0\t2.0\t50\n",
        encoding="utf-8",
    )
    counts = atac_peak_visualization.count_peaks(peaks_dir)
    assert counts == {"sample_a": 3}


def test_main_writes_plot_png(tmp_path):
    peaks_dir = tmp_path / "peaks"
    sample_dir = peaks_dir / "sample_a"
    sample_dir.mkdir(parents=True)
    (sample_dir / "sample_a_peaks.narrowPeak").write_text(
        "chr1\t100\t200\tpeak1\t0\t.\t5.0\t3.0\t2.0\t50\n", encoding="utf-8"
    )
    output_png = tmp_path / "atac_summary.png"
    sys.argv = ["atac_peak_visualization.py", "--peaks-dir", str(peaks_dir), "--output", str(output_png)]
    atac_peak_visualization.main()
    assert output_png.exists()
    assert output_png.stat().st_size > 0
