#!/usr/bin/env Rscript

args <- commandArgs(trailingOnly = TRUE)
if (length(args) != 3) {
  stop("Usage: deseq2_analysis.R <count_matrix_csv> <sample_metadata_csv> <results_csv>")
}

count_matrix_csv <- args[[1]]
sample_metadata_csv <- args[[2]]
results_csv <- args[[3]]

if (!file.exists(count_matrix_csv)) {
  stop(paste("Missing count matrix:", count_matrix_csv))
}
if (!file.exists(sample_metadata_csv)) {
  stop(paste("Missing sample metadata:", sample_metadata_csv))
}

suppressPackageStartupMessages({
  library(DESeq2)
})

counts <- read.csv(count_matrix_csv, check.names = FALSE)
metadata <- read.csv(sample_metadata_csv, check.names = FALSE)
rownames(counts) <- counts$gene_id
count_values <- as.matrix(counts[, setdiff(colnames(counts), "gene_id"), drop = FALSE])
storage.mode(count_values) <- "integer"
rownames(metadata) <- metadata$sample_id
metadata <- metadata[colnames(count_values), , drop = FALSE]

dds <- DESeqDataSetFromMatrix(countData = count_values, colData = metadata, design = ~ condition)
dds <- tryCatch(
  DESeq(dds, quiet = TRUE, sfType = "poscounts"),
  error = function(error) {
    message("Falling back to gene-wise dispersion estimates for tiny fixture data: ", conditionMessage(error))
    dds <- estimateSizeFactors(dds, type = "poscounts")
    dds <- estimateDispersionsGeneEst(dds, quiet = TRUE)
    dispersions(dds) <- mcols(dds)$dispGeneEst
    nbinomWaldTest(dds, quiet = TRUE)
  }
)
res <- as.data.frame(results(dds))
res$gene_id <- rownames(res)
dir.create(dirname(results_csv), recursive = TRUE, showWarnings = FALSE)
write.csv(res[, c("gene_id", setdiff(colnames(res), "gene_id"))], results_csv, row.names = FALSE)
