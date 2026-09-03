"""Generate the anonymous HealthOps data-package demo on demand."""

from __future__ import annotations

from argparse import ArgumentParser
from pathlib import Path

from executive_health_ai.services.data_packages import build_synthetic_package


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "data" / "synthetic_health_package.zip"


def main() -> None:
    parser = ArgumentParser(description="生成不含真实健康数据的 HealthOps 演示数据包")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    output = args.output.resolve()
    allowed = (ROOT / "data").resolve()
    if output.parent != allowed:
        raise ValueError("演示数据包只能写入项目 data 目录。")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(build_synthetic_package())
    print(f"Synthetic HealthOps data package ready: {output.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
