OFFICIAL_ROUTE_ID = "bulk_rna_seq_salmon_ref"


def route_for_domain(domain: str) -> str:
    if domain != "bulk_rna_seq":
        raise ValueError(f"Unsupported workflow domain: {domain}")
    return OFFICIAL_ROUTE_ID

