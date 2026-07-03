"""Next Gen Agent — CLI entry point with interactive loop."""

import os
import sys

from dotenv import load_dotenv

from src.agent.end_to_end import EndToEndAgent


def main() -> None:
    load_dotenv()
    use_llm = bool(os.environ.get("DEEPSEEK_API_KEY"))

    print("=" * 50)
    print("  Next Gen Agent")
    print(f"  LLM: {'DeepSeek' if use_llm else 'stubs (no DEEPSEEK_API_KEY)'}")
    print("  Type 'exit' or Ctrl+C to quit.")
    print("=" * 50)

    agent = EndToEndAgent(use_llm=use_llm)

    try:
        while True:
            try:
                task = input("\n> ").strip()
            except (EOFError, KeyboardInterrupt):
                print("\nShutting down...")
                break

            if not task:
                continue
            if task.lower() in ("exit", "quit", "q"):
                break

            try:
                result = agent.run(task)
            except Exception as e:
                print(f"[ERROR] {e}")
                continue

            status = "OK" if result.succeeded else "FAIL"
            print(f"\n[{status}] strategy={result.strategy} attempts={result.attempts}")
            for line in result.orchestration.get("transcript", []):
                print(f"  {line}")
    finally:
        summary = agent.close()
        print(f"\nSession closed: skills_extracted={summary['skills_extracted']}, semantic→{summary['semantic_persisted']}")


if __name__ == "__main__":
    main()
