from __future__ import annotations

import re
import shlex
import subprocess
import tempfile
from pathlib import Path
# pyrefly: ignore [missing-import]
from comfy_api.latest import io


class _Base(io.ComfyNode):
    OUTPUT_NODE = True


class Prokka_annotate(_Base):
    """Rapid prokaryotic genome annotation with Prokka.

    Annotates bacterial, archaeal, and viral genomes using a curated protein
    database and rRNA/tRNA predictors.

    Example extra_args:
        --metagenome --compliant --centre UoM
    """

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="Prokka_annotate",
            display_name="Prokka annotate",
            category="GenomeAssembly/Annotation",
            inputs=[
                io.String.Input("assembly_path",
                    display_name="Assembly FASTA",
                    multiline=False, default=""),
                io.String.Input("output_dir",
                    display_name="Output directory",
                    multiline=False, default=""),
                io.String.Input("prefix",
                    display_name="Output file prefix",
                    multiline=False, default="PROKKA"),
                io.Combo.Input("kingdom",
                    display_name="Kingdom",
                    options=["Bacteria", "Archaea", "Viruses", "Mitochondria"],
                    default="Bacteria"),
                io.String.Input("genus",
                    display_name="Genus (optional)",
                    multiline=False, default=""),
                io.String.Input("species",
                    display_name="Species (optional)",
                    multiline=False, default=""),
                io.Boolean.Input("rfam",
                    display_name="Enable Rfam ncRNA annotation (slow)",
                    default=False),
                io.Int.Input("threads",
                    display_name="Threads",
                    default=4, min=1, max=64),
                io.String.Input("extra_args",
                    display_name="Extra Prokka arguments",
                    multiline=True, default=""),
            ],
            outputs=[
                io.String.Output("output_dir"),
                io.String.Output("gff_path"),
                io.String.Output("gbk_path"),
                io.String.Output("faa_path"),
                io.Int.Output("n_genes"),
                io.String.Output("summary_text"),
            ],
        )

    @classmethod
    def execute(
        cls, assembly_path, output_dir, prefix, kingdom, genus, species,
        rfam, threads, extra_args,
    ) -> io.NodeOutput:
        out_dir = Path(output_dir) if output_dir else Path(tempfile.mkdtemp())
        out_dir.mkdir(parents=True, exist_ok=True)

        cmd = [
            "prokka",
            "--outdir", str(out_dir),
            "--prefix", prefix,
            "--kingdom", kingdom,
            "--cpus", str(threads),
            "--force",
            assembly_path,
        ]
        if genus:
            cmd += ["--genus", genus]
        if species:
            cmd += ["--species", species]
        if rfam:
            cmd.append("--rfam")
        if extra_args.strip():
            cmd += shlex.split(extra_args)

        result = subprocess.run(cmd, capture_output=True, text=True)

        gff = str(out_dir / f"{prefix}.gff")
        gbk = str(out_dir / f"{prefix}.gbk")
        faa = str(out_dir / f"{prefix}.faa")

        if result.returncode != 0:
            err = result.stderr[:500]
            return io.NodeOutput(str(out_dir), gff, gbk, faa, 0, f"ERROR:\n{err}")

        n_genes, summary = _prokka_summary(out_dir, prefix)
        return io.NodeOutput(str(out_dir), gff, gbk, faa, n_genes, summary)


class Maker_annotate(_Base):
    """Evidence-based eukaryotic genome annotation with MAKER.

    Integrates EST/transcriptome evidence, protein homology, and ab initio
    gene predictors (AUGUSTUS, SNAP). This node generates default config
    files and runs MAKER with the provided evidence.

    Note: MAKER requires AUGUSTUS and SNAP to be configured on the system.
    For best results, pre-train gene predictors with your organism's data.
    """

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="Maker_annotate",
            display_name="MAKER annotate",
            category="GenomeAssembly/Annotation",
            inputs=[
                io.String.Input("assembly_path",
                    display_name="Assembly FASTA",
                    multiline=False, default=""),
                io.String.Input("output_dir",
                    display_name="Output directory",
                    multiline=False, default=""),
                io.String.Input("est_fasta",
                    display_name="EST/Transcriptome FASTA (optional)",
                    multiline=False, default="",
                    tooltip="EST or assembled transcriptome for evidence"),
                io.String.Input("protein_fasta",
                    display_name="Protein homology FASTA (optional)",
                    multiline=False, default="",
                    tooltip="Protein sequences from related organisms"),
                io.String.Input("repeat_lib",
                    display_name="RepeatMasker library (optional)",
                    multiline=False, default=""),
                io.Int.Input("threads",
                    display_name="Threads",
                    default=4, min=1, max=64),
                io.String.Input("extra_args",
                    display_name="Extra MAKER arguments",
                    multiline=True, default=""),
            ],
            outputs=[
                io.String.Output("output_dir"),
                io.String.Output("gff_path"),
                io.String.Output("summary_text"),
            ],
        )

    @classmethod
    def execute(
        cls, assembly_path, output_dir, est_fasta, protein_fasta,
        repeat_lib, threads, extra_args,
    ) -> io.NodeOutput:
        out_dir = Path(output_dir) if output_dir else Path(tempfile.mkdtemp())
        out_dir.mkdir(parents=True, exist_ok=True)

        # Generate default MAKER control files
        ctl_result = subprocess.run(
            ["maker", "-CTL"],
            cwd=str(out_dir),
            capture_output=True, text=True,
        )
        if ctl_result.returncode != 0:
            return io.NodeOutput(str(out_dir), "", f"ERROR (maker -CTL):\n{ctl_result.stderr[:300]}")

        # Patch maker_opts.ctl
        opts_file = out_dir / "maker_opts.ctl"
        if opts_file.exists():
            opts = opts_file.read_text()
            opts = re.sub(r"^genome=.*$", f"genome={assembly_path}", opts, flags=re.MULTILINE)
            if est_fasta:
                opts = re.sub(r"^est=.*$", f"est={est_fasta}", opts, flags=re.MULTILINE)
            if protein_fasta:
                opts = re.sub(r"^protein=.*$", f"protein={protein_fasta}", opts, flags=re.MULTILINE)
            if repeat_lib:
                opts = re.sub(r"^rmlib=.*$", f"rmlib={repeat_lib}", opts, flags=re.MULTILINE)
            opts_file.write_text(opts)

        cmd = ["maker", "-cpus", str(threads)]
        if extra_args.strip():
            cmd += shlex.split(extra_args)

        result = subprocess.run(cmd, cwd=str(out_dir), capture_output=True, text=True)

        gff_files = list(out_dir.rglob("*.gff"))
        gff_path = str(gff_files[0]) if gff_files else str(out_dir / "maker.gff")

        if result.returncode != 0:
            err = result.stderr[:500]
            return io.NodeOutput(str(out_dir), gff_path, f"ERROR:\n{err}")

        summary = "\n".join([
            "=== MAKER Annotation Summary ===",
            f"Output directory : {out_dir}",
            f"GFF output       : {gff_path}",
            "MAKER requires post-processing with maker2zff/fathom for gene model QC.",
        ])
        return io.NodeOutput(str(out_dir), gff_path, summary)


class RepeatMasker_mask(_Base):
    """Repeat masking with RepeatMasker.

    Identifies and masks transposable elements and repetitive sequences
    using the Repbase library.

    Example extra_args:
        -nolow -noint -xsmall
    """

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="RepeatMasker_mask",
            display_name="RepeatMasker mask",
            category="GenomeAssembly/Annotation",
            inputs=[
                io.String.Input("assembly_path",
                    display_name="Assembly FASTA",
                    multiline=False, default=""),
                io.String.Input("output_dir",
                    display_name="Output directory",
                    multiline=False, default=""),
                io.String.Input("species",
                    display_name="Species",
                    multiline=False, default="human",
                    tooltip="Species name for repeat library lookup"),
                io.Int.Input("threads",
                    display_name="Threads",
                    default=4, min=1, max=64),
                io.Combo.Input("engine",
                    display_name="Search engine",
                    options=["rmblast", "wublast", "crossmatch", "abblast"],
                    default="rmblast"),
                io.String.Input("extra_args",
                    display_name="Extra RepeatMasker arguments",
                    multiline=True, default=""),
            ],
            outputs=[
                io.String.Output("output_dir"),
                io.String.Output("masked_path"),
                io.String.Output("out_path"),
                io.String.Output("summary_text"),
            ],
        )

    @classmethod
    def execute(
        cls, assembly_path, output_dir, species, threads, engine, extra_args,
    ) -> io.NodeOutput:
        out_dir = Path(output_dir) if output_dir else Path(tempfile.mkdtemp())
        out_dir.mkdir(parents=True, exist_ok=True)

        cmd = [
            "RepeatMasker",
            "-species", species,
            "-engine", engine,
            "-pa", str(threads),
            "-dir", str(out_dir),
            assembly_path,
        ]
        if extra_args.strip():
            cmd += shlex.split(extra_args)

        result = subprocess.run(cmd, capture_output=True, text=True)

        asm_name = Path(assembly_path).name
        masked = str(out_dir / f"{asm_name}.masked")
        out_file = str(out_dir / f"{asm_name}.out")

        if result.returncode != 0:
            err = result.stderr[:500]
            return io.NodeOutput(str(out_dir), masked, out_file, f"ERROR:\n{err}")

        summary = _repeatmasker_summary(out_dir, asm_name)
        return io.NodeOutput(str(out_dir), masked, out_file, summary)


# ── Summary helpers ──────────────────────────────────────────────────────────

def _prokka_summary(out_dir: Path, prefix: str) -> tuple[int, str]:
    txt_path = out_dir / f"{prefix}.txt"
    lines = ["=== Prokka Annotation Summary ==="]
    n_genes = 0
    if txt_path.exists():
        for line in txt_path.read_text().splitlines():
            lines.append("  " + line.strip())
            m = re.search(r"^CDS\s+:\s+(\d+)", line.strip())
            if m:
                n_genes = int(m.group(1))
    else:
        lines.append("Summary .txt not found.")
    return n_genes, "\n".join(lines)


def _repeatmasker_summary(out_dir: Path, asm_name: str) -> str:
    tbl_path = out_dir / f"{asm_name}.tbl"
    lines = ["=== RepeatMasker Summary ==="]
    if tbl_path.exists():
        for line in tbl_path.read_text().splitlines()[:30]:
            if line.strip():
                lines.append("  " + line.rstrip())
    else:
        lines.append("Summary table (.tbl) not found.")
    return "\n".join(lines)
