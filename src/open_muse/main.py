# src/open_muse/main.py
"""Open-MUSE entry point."""
from __future__ import annotations

import argparse
import sys
import time
from datetime import datetime
from pathlib import Path

from open_muse.config import load_config
from open_muse.llm.client import LLMClient
from open_muse.llm.providers import resolve_provider
from open_muse.skills.loader import discover_skills
from open_muse.tools.registry import ToolRegistry
from open_muse.tools.skill_tools import make_load_skill_handler, make_load_reference_handler
from open_muse.tools.deliverable_tools import make_write_deliverable_handler, make_read_deliverable_handler
from open_muse.deliverables.storage import DeliverableStore
from open_muse.core.agent_loop import AgentLoop
from open_muse.pipeline.runner import PhasePipeline
from open_muse.logging import RunLogger


def main():
    parser = argparse.ArgumentParser(description="Open-MUSE: AI creative writing agent")
    parser.add_argument("request", help="Writing request / prompt")
    parser.add_argument("--config", default="config.yaml", help="Config file path")
    parser.add_argument("--benchmark", default="writing-bench", help="Benchmark name (e.g. writing-bench, conStory-bench)")
    parser.add_argument("--query-id", default="test", help="Query ID (e.g. 188); defaults to 'test' for smoke runs")
    parser.add_argument("--timestamp", default=None, help="Run timestamp (YYYYMMDD_HHMMSS); auto-generated if omitted")
    parser.add_argument("--model", default=None, help="Override model name")
    args = parser.parse_args()

    config = load_config(Path(args.config))
    model = args.model or config.default_model

    timestamp = args.timestamp or datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = Path("results") / args.benchmark / "open-muse" / model / timestamp / args.query_id
    config.output_dir = output_dir

    provider = resolve_provider(model, config.providers)
    if provider is None:
        print(f"Error: no provider found for model '{model}'")
        sys.exit(1)

    # Batch log lives one level up from query_id (at the timestamp dir)
    batch_log_path = output_dir.parent / "batch.jsonl"
    logger = RunLogger(query_log_dir=output_dir, batch_log_path=batch_log_path)

    llm_client = LLMClient(base_url=provider.base_url, api_key=provider.api_key)
    store = DeliverableStore(output_dir=config.output_dir)
    skills = discover_skills(config.skills_dir)

    registry = ToolRegistry()
    registry.register(
        name="load_skill",
        description="Load a skill's full instructions by name. Available skills: "
                    + ", ".join(f"{s.name} ({s.description[:50]})" for s in skills),
        parameters={
            "type": "object",
            "properties": {"name": {"type": "string", "description": "Skill name"}},
            "required": ["name"],
        },
        handler=make_load_skill_handler(skills),
    )
    registry.register(
        name="load_reference",
        description="Load a reference file from a skill's references/ directory",
        parameters={
            "type": "object",
            "properties": {
                "skill": {"type": "string", "description": "Skill name"},
                "path": {"type": "string", "description": "File path within references/"},
            },
            "required": ["skill", "path"],
        },
        handler=make_load_reference_handler(config.skills_dir),
    )
    registry.register(
        name="write_deliverable",
        description="Write a phase deliverable (YAML for design, Markdown for generation/revision)",
        parameters={
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Deliverable name (e.g. phase0_story_conception)"},
                "content": {"type": "string", "description": "Deliverable content"},
                "format": {"type": "string", "enum": ["yaml", "md"], "description": "Output format"},
            },
            "required": ["name", "content", "format"],
        },
        handler=make_write_deliverable_handler(store),
    )
    registry.register(
        name="read_deliverable",
        description="Read a deliverable from a previous phase",
        parameters={
            "type": "object",
            "properties": {"name": {"type": "string", "description": "Deliverable name"}},
            "required": ["name"],
        },
        handler=make_read_deliverable_handler(store),
    )

    agent_loop = AgentLoop(client=llm_client, registry=registry, model=model, logger=logger)
    pipeline = PhasePipeline(skills_dir=config.skills_dir, output_dir=config.output_dir,
                             logger=logger)

    logger.run_start(model=model, query_id=args.query_id,
                     num_phases=len(pipeline.phases),
                     request_preview=args.request)
    t0 = time.monotonic()
    results = pipeline.run(agent_loop=agent_loop, user_request=args.request)

    success = all(r.success for r in results)
    logger.run_end(success=success, duration_s=time.monotonic() - t0,
                   phases_done=sum(1 for r in results if r.success))

    if success:
        # Copy final story: prefer phase7 if it's a full story, otherwise use phase6
        story_path = output_dir / "story.md"
        p7 = store.read("phase7_integration")
        p6 = store.read("phase6_scene_development")
        # Phase 7 may be a review report (short) or a revised story (long)
        # Use phase7 only if it's substantially longer than a review report
        if p7 and isinstance(p7, str) and len(p7) > 5000:
            story_path.write_text(p7, encoding="utf-8")
        elif p6 and isinstance(p6, str):
            story_path.write_text(p6, encoding="utf-8")
        print(f"\nStory written to: {story_path}")
    else:
        for r in results:
            if not r.success:
                for err in r.errors:
                    print(f"  ERROR [{r.phase_name}] {err}")
        sys.exit(1)


if __name__ == "__main__":
    main()
