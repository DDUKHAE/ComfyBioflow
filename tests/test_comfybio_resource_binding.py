from bioflow_harness.comfy.resource_binding import ResourceBindings, validate_bindings


def test_from_resources_maps_roles():
    bindings = ResourceBindings.from_resources(
        [
            {"label": "input_path", "type": "path", "path": "/data/fastq"},
            {"label": "output_path", "type": "path", "path": "/data/out"},
            {"label": "metadata_csv", "type": "metadata", "path": "/data/meta.csv"},
            {"label": "transcriptome", "type": "index", "path": "/data/tx.fasta"},
        ]
    )
    assert bindings.input_fastq_dir == "/data/fastq"
    assert bindings.metadata_csv == "/data/meta.csv"
    assert bindings.transcriptome_fasta == "/data/tx.fasta"
    assert bindings.salmon_quant_dir == "/data/out/salmon_quant"
    assert bindings.count_matrix == "/data/out/deseq2/count_matrix.csv"
    assert bindings.defaulted == frozenset()


def test_from_resources_falls_back_to_fixture_defaults():
    bindings = ResourceBindings.from_resources([])
    assert bindings.input_fastq_dir == "harness/examples/fixtures/quickstart"
    assert "input_fastq_dir" in bindings.defaulted
    assert "transcriptome_fasta" in bindings.defaulted


def test_validate_bindings_warns_on_missing_required():
    bindings = ResourceBindings.from_resources(
        [{"label": "input_path", "type": "path", "path": "/data/fastq"}]
    )
    warnings = validate_bindings("bulk_rna_seq_salmon_ref", bindings)
    joined = " ".join(warnings)
    assert "metadata_csv" in joined
    assert "transcriptome_fasta" in joined
    assert "input_fastq_dir" not in joined
