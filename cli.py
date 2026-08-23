from __future__ import annotations

import argparse
import json

from agentcad.config.settings import EngineSettings
from agentcad.engine import AgentCADEngine, EngineRunStatus


def main() -> int:
    parser = argparse.ArgumentParser(description="AgentCAD v2 CLI")
    parser.add_argument("description")
    parser.add_argument("--structural", action="store_true")
    args = parser.parse_args()

    engine = AgentCADEngine(EngineSettings.from_env())
    result = engine.start(args.description, perform_structural_analysis=args.structural)

    while result.status == EngineRunStatus.NEEDS_INPUT:
        print("\nПотрібні уточнення:")
        answers = {}
        for q in result.questions:
            print("\n-", q.get("question"))
            if q.get("explanation"):
                print("  ", q["explanation"])
            answers[q["id"]] = input("> ").strip()
        result = engine.resume(result.thread_id, answers)

    print(json.dumps(result.state, ensure_ascii=False, indent=2))
    return 0 if result.status == EngineRunStatus.COMPLETED else 1


if __name__ == "__main__":
    raise SystemExit(main())
