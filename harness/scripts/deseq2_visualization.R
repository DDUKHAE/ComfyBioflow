#!/usr/bin/env Rscript

args <- commandArgs(trailingOnly = TRUE)
if (length(args) != 3) {
  stop("Usage: deseq2_visualization.R <count_matrix_csv> <results_csv> <plot_dir>")
}

count_matrix_csv <- args[[1]]
results_csv <- args[[2]]
plot_dir <- args[[3]]

if (!file.exists(count_matrix_csv)) {
  stop(paste("Missing count matrix:", count_matrix_csv))
}
if (!file.exists(results_csv)) {
  stop(paste("Missing DESeq2 results:", results_csv))
}

dir.create(plot_dir, recursive = TRUE, showWarnings = FALSE)

counts <- read.csv(count_matrix_csv, check.names = FALSE)
results <- read.csv(results_csv, check.names = FALSE)

png(file.path(plot_dir, "pca.png"))
plot(seq_len(nrow(counts)), counts[[2]], main = "PCA placeholder", xlab = "PC1", ylab = "PC2")
dev.off()

png(file.path(plot_dir, "ma.png"))
plot(results$baseMean, results$log2FoldChange, main = "MA plot", xlab = "mean", ylab = "log2FC")
dev.off()

png(file.path(plot_dir, "volcano.png"))
plot(results$log2FoldChange, -log10(results$padj), main = "Volcano plot", xlab = "log2FC", ylab = "-log10(padj)")
dev.off()

png(file.path(plot_dir, "heatmap.png"))
heatmap(as.matrix(counts[, setdiff(colnames(counts), "gene_id"), drop = FALSE]), main = "Count heatmap")
dev.off()

