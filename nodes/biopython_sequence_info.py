import json
from pathlib import Path


class BiopythonSequenceInfoNode:
    RETURN_TYPES = ("STRING", "STRING")
    RETURN_NAMES = ("output_path", "summary_json")
    FUNCTION = "summarize"
    CATEGORY = "ComfyBIO/Utilities"

    @classmethod
    def INPUT_TYPES(cls) -> dict:
        return {
            "required": {
                "fasta_path": ("STRING", {"default": ""}),
                "output_path": ("STRING", {"default": "sequence_info.json"}),
            }
        }

    def summarize(self, fasta_path: str, output_path: str) -> tuple[str, str]:
        records = _read_fasta(Path(fasta_path))
        summary = {
            "sequence_count": len(records),
            "total_bases": sum(record["length"] for record in records),
            "records": records,
        }
        summary_json = json.dumps(summary, indent=2)
        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(summary_json, encoding="utf-8")
        return str(out), summary_json


def _read_fasta(path: Path) -> list[dict[str, str | int]]:
    if not path.exists():
        raise FileNotFoundError(f"FASTA path does not exist: {path}")
    records: list[dict[str, str | int]] = []
    current_id: str | None = None
    current_sequence: list[str] = []
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith(">"):
            if current_id is not None:
                sequence = "".join(current_sequence)
                records.append({"id": current_id, "length": len(sequence)})
            current_id = line[1:].split()[0]
            current_sequence = []
        else:
            current_sequence.append(line)
    if current_id is not None:
        sequence = "".join(current_sequence)
        records.append({"id": current_id, "length": len(sequence)})
    return records

