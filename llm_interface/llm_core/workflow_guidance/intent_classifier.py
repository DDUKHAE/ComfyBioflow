from __future__ import annotations

_INTENT_KEYWORDS: list[tuple[str, tuple[str, ...]]] = [
    ("searchio_analysis", ("searchio", "blast xml", "query result", "hsp", "search result")),
    ("blast_search", ("blast", "homology", "similarity search", "database search")),
    ("phylogeny", ("phylogeny", "phylogenetic", "evolutionary tree", "tree from aligned")),
    ("pairwise_alignment", ("pairwise alignment", "pairwise align", "global alignment", "local alignment", "best alignment", "sequence alignment")),
    ("multiple_alignment", ("multiple alignment", "msa", "align sequences", "aligned sequences", "alignment file", "summarize the alignment")),
    ("entrez_fetch", ("entrez", "pubmed", "ncbi fetch", "efetch", "esearch")),
    ("sequence_annotation_edit", ("add feature", "edit annotation", "annotate record", "sequence annotation edit")),
    ("annotation", ("annotation", "annotate", "feature table", "genbank annotation")),
    ("pdb_chain_analysis", ("pdb chain", "chain sequence", "extract chain from pdb")),
    ("pdb_structure_basic", ("pdb structure", "protein structure", "pdb file", "structure info")),
    ("kegg_pathway_basic", ("kegg pathway", "kegg api", "pathway list", "enzyme entry")),
    ("uniprot_lookup", ("uniprot", "protein lookup", "uniprot search")),
    ("motif_scan_basic", ("motif", "consensus motif", "motif scan", "pssm")),
    ("popgen_basic", ("popgen", "genepop", "population genetics", "loci summary")),
    ("cluster_basic", ("cluster", "distance matrix", "hierarchical clustering", "csv clustering")),
    ("graphics_basic", ("genome diagram", "graphics", "genbank diagram", "seqrecord diagram")),
    ("sequence_objects_basic", ("translate sequence", "sequence length", "sequence objects", "protein translation")),
    ("kegg_enzyme_file_basic", ("kegg enzyme file", "enzyme parse", "enzyme read")),
            ("fasta_parse", ("fasta", "parse sequences", "sequence ids", "summarize sequence")),
]


def classify_intent(goal: str) -> str:
    text = (goal or "").strip().lower()
    for intent, keywords in _INTENT_KEYWORDS:
        if any(keyword in text for keyword in keywords):
            return intent
    return "general_biopython"
