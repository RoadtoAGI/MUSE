"""Phase Pipeline: deterministic Phase 0->7 sequencing."""
from __future__ import annotations

import re
import time
from dataclasses import dataclass
from pathlib import Path

from open_muse.skills.loader import SkillDef, discover_skills
from open_muse.deliverables.storage import DeliverableStore
from open_muse.deliverables.validator import validate_deliverable
from open_muse.core.agent_loop import AgentLoop
from open_muse.core.types import Message


@dataclass
class PhaseResult:
    """Result of running a single phase."""
    phase_name: str
    stage: str
    success: bool
    errors: list[str]


class PhasePipeline:
    """Orchestrates Phase 0->7 execution."""

    PHASE_PATTERN = re.compile(r"^phase(\d+)-")

    def __init__(self, skills_dir: Path, output_dir: Path, logger=None):
        self._skills_dir = Path(skills_dir)
        self._output_dir = Path(output_dir)
        self._store = DeliverableStore(output_dir=self._output_dir)
        self._logger = logger

        all_skills = discover_skills(self._skills_dir)
        self.phases = sorted(
            [s for s in all_skills if self.PHASE_PATTERN.match(s.name)],
            key=lambda s: int(self.PHASE_PATTERN.match(s.name).group(1)),
        )

    @staticmethod
    def get_stage(phase_name: str) -> str:
        """Determine stage from phase name."""
        match = re.match(r"^phase(\d+)-", phase_name)
        if not match:
            return "unknown"
        n = int(match.group(1))
        if n <= 5:
            return "design"
        elif n == 6:
            return "generation"
        else:
            return "revision"

    def run(
        self,
        agent_loop: AgentLoop,
        user_request: str,
        mode: str = "auto",
        max_retries: int = 2,
    ) -> list[PhaseResult]:
        """Execute all phases sequentially."""
        results = []

        for skill in self.phases:
            stage = self.get_stage(skill.name)
            phase_result = self._run_phase(
                skill=skill, stage=stage, agent_loop=agent_loop,
                user_request=user_request, max_retries=max_retries,
            )
            results.append(phase_result)
            if not phase_result.success:
                break

        return results

    def _run_phase(
        self,
        skill: SkillDef,
        stage: str,
        agent_loop: AgentLoop,
        user_request: str,
        max_retries: int,
    ) -> PhaseResult:
        """Run a single phase with validation and retry."""
        system_prompt = self._build_system_prompt(skill, user_request)
        context_msg = self._build_context_message(skill)

        messages = [context_msg]
        t0 = time.monotonic()

        for attempt in range(max_retries + 1):
            if self._logger:
                self._logger.phase_start(skill.name, stage, attempt=attempt + 1)

            # Generation/revision phases need much higher token limit for full story output
            phase_max_tokens = 32768 if stage in ("generation", "revision") else 8192

            agent_loop.run(
                system_prompt=system_prompt,
                messages=messages,
                allowed_tools=skill.allowed_tools if skill.allowed_tools else None,
                tool_choice="required",
                max_tokens=phase_max_tokens,
            )

            errors = self._validate(skill, stage)
            if not errors:
                if self._logger:
                    self._logger.phase_end(skill.name, stage, success=True,
                                           duration_s=time.monotonic() - t0)
                return PhaseResult(phase_name=skill.name, stage=stage, success=True, errors=[])

            if self._logger:
                self._logger.validation_fail(errors, attempt=attempt + 1)

            if attempt < max_retries:
                if self._logger:
                    self._logger.retry(attempt=attempt + 2, reason="validation_failed")
                error_feedback = (
                    f"Deliverable validation failed (attempt {attempt + 1}/{max_retries + 1}):\n"
                    + "\n".join(f"- {e}" for e in errors)
                    + "\n\nPlease fix these issues and call write_deliverable again."
                )
                messages = [Message(role="user", content=error_feedback)]

        if self._logger:
            self._logger.phase_end(skill.name, stage, success=False,
                                   duration_s=time.monotonic() - t0)
        return PhaseResult(phase_name=skill.name, stage=stage, success=False, errors=errors)

    def _build_system_prompt(self, skill: SkillDef, user_request: str) -> str:
        deliverable_name = skill.name.replace("-", "_")
        stage = self.get_stage(skill.name)
        fmt = "yaml" if stage == "design" else "md"

        return (
            f"You are a creative writing agent executing phase: {skill.name}\n\n"
            f"User's writing request: {user_request}\n\n"
            f"## Skill Instructions\n\n{skill.prompt}\n\n"
            f"## REQUIRED OUTPUT\n"
            f"When you have completed this phase, you MUST call the `write_deliverable` tool "
            f"to save your work. Do NOT just respond with text.\n"
            f"- name: `{deliverable_name}`\n"
            f"- format: `{fmt}`\n"
            f"Only call `read_deliverable` first if you need context from a previous phase."
        )

    def _build_context_message(self, skill: SkillDef) -> Message:
        available = self._store.list_available()
        if available:
            context = f"Available deliverables from prior phases: {', '.join(available)}\n"
            context += "Use read_deliverable to load any you need."
        else:
            context = "This is the first phase. No prior deliverables available."
        return Message(role="user", content=context)

    def _validate(self, skill: SkillDef, stage: str) -> list[str]:
        deliverable_name = skill.name.replace("-", "_")
        data = self._store.read(deliverable_name)

        # Always require the deliverable file to exist
        if data is None:
            return [f"Deliverable not written: call write_deliverable(name='{deliverable_name}', ...)"]

        # If skill declares required fields, validate them too
        if skill.required_deliverables and stage == "design" and isinstance(data, dict):
            return validate_deliverable(data, skill.required_deliverables)

        return []
