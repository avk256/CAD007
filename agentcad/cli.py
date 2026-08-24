from __future__ import annotations

import argparse
import json

from agentcad.engine.agentcad_engine import AgentCADEngine


def main() -> None:
    parser = argparse.ArgumentParser(description="AgentCAD v3: natural-language CAD/CAE with deterministic CadQuery execution")
    parser.add_argument("description", nargs="+", help="Natural-language engineering request")
    parser.add_argument("--fem", action="store_true", help="Also plan and run linear-static CalculiX analysis")
    args = parser.parse_args()

    result = AgentCADEngine().start(" ".join(args.description), perform_structural_analysis=args.fem)
    print(result.model_dump_json(indent=2))


if __name__ == "__main__":
    main()
