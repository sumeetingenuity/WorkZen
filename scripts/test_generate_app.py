"""
Test script to generate an app via the orchestrator using vault credentials.

Vault credentials are loaded in `secureassist.settings`, which populates
environment variables from ~/.secureassist/vault.json.
"""
import argparse
import asyncio
import os
import sys
from pathlib import Path


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate a test app via orchestrator.")
    parser.add_argument(
        "--message",
        default="I'm a lawyer and need a case management app.",
        help="User message to send to the orchestrator."
    )
    parser.add_argument(
        "--user-id",
        default="local-test-user",
        help="User ID for the orchestrator session."
    )
    parser.add_argument(
        "--session-id",
        default=None,
        help="Optional session ID to reuse an existing session."
    )
    return parser.parse_args()


async def _main() -> int:
    args = _parse_args()

    base_dir = Path(__file__).resolve().parents[1]
    if str(base_dir) not in sys.path:
        sys.path.insert(0, str(base_dir))

    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "secureassist.settings")
    try:
        import django
        django.setup()
    except Exception as exc:
        print(f"Failed to initialize Django: {exc}", file=sys.stderr)
        return 1

    from agents.orchestrator.agent import orchestrator_agent

    result = await orchestrator_agent.process(
        user_id=args.user_id,
        message=args.message,
        session_id=args.session_id
    )

    print("=== Orchestrator Response ===")
    print(result.response)
    if result.app_created:
        print(f"\nApp created: {result.app_created}")
    if result.requires_approval:
        print(f"\nApproval required. Pending task ID: {result.pending_task_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(_main()))
