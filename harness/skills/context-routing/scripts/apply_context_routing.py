import argparse


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("request")
    args = parser.parse_args()
    request = args.request.lower()
    if "star" in request or "genome alignment" in request:
        print("ALT route candidate: STAR; reason=genome-alignment-specific request")
    elif "multiqc" in request:
        print("ALT add-on candidate: MultiQC; reason=enhanced QC aggregation requested")
    else:
        print("Keep official REF route: bulk_rna_seq_salmon_ref")


if __name__ == "__main__":
    main()

