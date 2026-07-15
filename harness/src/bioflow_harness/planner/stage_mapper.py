ROUTES_BY_DOMAIN = {
    "bulk_rna_seq": "bulk_rna_seq_salmon_ref",
    "scrna_seq": "scrna_seq_scanpy_ref",
    "variant_analysis": "variant_analysis_bwa_ref",
    "epigenomics": "atac_seq_macs3_ref",
    "metagenome": "metagenome_kraken2_ref",
    "genome_assembly": "genome_assembly_spades_ref",
}


def route_for_domain(domain: str) -> str:
    try:
        return ROUTES_BY_DOMAIN[domain]
    except KeyError as error:
        raise ValueError(f"Unsupported workflow domain: {domain}") from error
