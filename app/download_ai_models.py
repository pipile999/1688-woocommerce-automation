"""Download and verify the local LaMa ONNX weight used by the image worker."""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path

from huggingface_hub import hf_hub_download


LAMA_SHA256 = "1faef5301d78db7dda502fe59966957ec4b79dd64e16f03ed96913c7a4eb68d6"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=Path("models/lama"))
    args = parser.parse_args()
    path = Path(
        hf_hub_download(
            repo_id="Carve/LaMa-ONNX",
            filename="lama_fp32.onnx",
            local_dir=args.output_dir,
        )
    )
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if digest != LAMA_SHA256:
        raise RuntimeError(f"LaMa checksum mismatch: {digest}")
    print(path)


if __name__ == "__main__":
    main()
