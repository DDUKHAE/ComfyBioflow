#!/usr/bin/env Rscript

args <- commandArgs(trailingOnly = TRUE)
if (length(args) != 2) {
  stop("Usage: tximport_import.R <salmon_quant_dir> <count_matrix_csv>")
}

salmon_quant_dir <- args[[1]]
output_csv <- args[[2]]
sample_dirs <- list.dirs(salmon_quant_dir, recursive = FALSE, full.names = TRUE)

if (length(sample_dirs) == 0) {
  stop(paste("No sample quantification directories found:", salmon_quant_dir))
}

counts <- NULL
for (sample_dir in sample_dirs) {
  sample_id <- basename(sample_dir)
  quant_file <- file.path(sample_dir, "quant.sf")
  if (!file.exists(quant_file)) {
    stop(paste("Missing salmon quant file:", quant_file))
  }
  quant <- read.delim(quant_file, check.names = FALSE)
  sample_counts <- data.frame(gene_id = quant$Name)
  sample_counts[[sample_id]] <- quant$NumReads
  if (is.null(counts)) {
    counts <- sample_counts
  } else {
    counts <- merge(counts, sample_counts, by = "gene_id", all = TRUE)
  }
}

dir.create(dirname(output_csv), recursive = TRUE, showWarnings = FALSE)
write.csv(counts, output_csv, row.names = FALSE, quote = FALSE)
