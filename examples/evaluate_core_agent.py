import argparse
import asyncio
import json
from pathlib import Path

from src.agents.agent import LLMAgent
from src.agents.eval import BehaviorEvaluator, load_evaluation_dataset
from src.agents.legacy.understanding.rules import RuleBasedUnderstanding

DEFAULT_DATASET = Path("src/agents/eval/datasets/readiness_v1.json")


async def run(dataset_path: Path, *, real_model: bool = False) -> int:
    dataset = load_evaluation_dataset(dataset_path)
    agent = LLMAgent() if real_model else LLMAgent(understanding_service=RuleBasedUnderstanding())
    report = await BehaviorEvaluator().evaluate_conversations(
        agent,
        dataset.scenarios,
        dataset_version=dataset.version,
    )
    print(json.dumps(report.model_dump(mode="json"), ensure_ascii=False, indent=2))
    return 0 if report.ready else 1


def main() -> int:
    parser = argparse.ArgumentParser(description="Run deterministic Core Agent readiness evaluation")
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument(
        "--real-model",
        action="store_true",
        help="Use the configured LLM adapters; default evaluation is offline.",
    )
    args = parser.parse_args()
    return asyncio.run(run(args.dataset, real_model=args.real_model))


if __name__ == "__main__":
    raise SystemExit(main())
