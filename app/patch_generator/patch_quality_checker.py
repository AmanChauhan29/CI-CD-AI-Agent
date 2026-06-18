"""
app/patch_generator/patch_quality_checker.py

Validates patch quality AFTER PatchApplier has written files to disk.

Flow:
    PatchGenerator
        ↓
    PatchValidator       ← rejects dangerous/oversized patches (pre-apply)
        ↓
    PatchApplier         ← writes files to disk
        ↓
    PatchQualityChecker  ← validates the on-disk result (post-apply)
        ↓
    GitService           ← branch / commit / push
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from app.patch_generator.patch_models import PatchInstruction

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Result model
# ---------------------------------------------------------------------------

@dataclass
class QualityCheckResult:
    passed: bool
    score: float                    # 0.0 – 1.0
    checks: dict[str, bool]        # individual check outcomes
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    def summary(self) -> str:
        status = "PASSED" if self.passed else "FAILED"
        return (
            f"[QualityCheck] {status}  score={self.score:.2f}\n"
            + "\n".join(f"  ✓ {k}" if v else f"  ✗ {k}"
                        for k, v in self.checks.items())
            + (("\nWARNINGS:\n" + "\n".join(f"  ! {w}" for w in self.warnings))
               if self.warnings else "")
            + (("\nERRORS:\n" + "\n".join(f"  ✗ {e}" for e in self.errors))
               if self.errors else "")
        )


# ---------------------------------------------------------------------------
# Relevance rules
# Maps failure category → what the patch must contain
# ---------------------------------------------------------------------------

RELEVANCE_RULES: dict[str, dict[str, Any]] = {
    "dependency_failure": {
        # patch must install something  OR  add to requirements file
        "workflow_keywords": ["pip install", "npm install", "apt-get install",
                              "apk add", "yarn add", "gem install"],
        "file_keywords":     ["requirements", "package.json", "Gemfile",
                              "pyproject.toml", "pom.xml"],
        "description": "patch must install a dependency or update a dependency file",
    },
    "test_failure": {
        "workflow_keywords": ["pytest", "npm test", "jest", "go test",
                              "mvn test", "unittest"],
        "file_keywords":     ["test_", "_test.py", ".test.js", "spec."],
        "description": "patch must touch test configuration or test files",
    },
    "command_failure": {
        "workflow_keywords": ["run:", "shell:", "chmod", "export", "PATH"],
        "file_keywords":     [],
        "description": "patch must fix a shell command or PATH issue",
    },
}


# ---------------------------------------------------------------------------
# Checker
# ---------------------------------------------------------------------------

class PatchQualityChecker:
    """
    Validates patched files on disk after PatchApplier has run.

    Usage:
        checker = PatchQualityChecker(repo_path)
        result  = checker.check(patch_plan.patches, analysis, category)
        if not result.passed:
            logger.error(result.summary())

    NOTE: `patches` must be a list of PatchInstruction objects
    (i.e. patch_plan.patches), not the PatchPlan wrapper itself,
    and not plain dicts.
    """

    # Minimum score to consider the patch acceptable
    PASS_THRESHOLD = 0.6

    def __init__(self, repo_path: str | Path):
        self.repo_path = Path(repo_path)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def check(
        self,
        patches: list[PatchInstruction],
        analysis: dict,
        failure_category: str,
        apply_results: list | None = None,
    ) -> QualityCheckResult:
        """
        Run all quality checks for the given patches.

        Args:
            patches:          list of PatchInstruction objects
                              (pass patch_plan.patches, not patch_plan itself)
            analysis:         LLM analysis dict
                              e.g. {"root_cause": "...", "suggested_fix": "..."}
            failure_category: classifier output
                              e.g. "dependency_failure"
            apply_results:    optional list of ApplyResult from
                              PatchApplier.apply(), in the same order as
                              `patches`. If provided, any entry with
                              success=False is treated as a hard error —
                              this catches cases where PatchApplier
                              silently failed to modify a file (e.g. a
                              'modify' or 'insert_after' target wasn't
                              found) that file-content checks alone can
                              miss, since they can false-positive when
                              unrelated existing text happens to satisfy
                              a substring match even though nothing
                              actually changed.
        """
        checks: dict[str, bool] = {}
        warnings: list[str] = []
        errors: list[str] = []

        if apply_results is not None:
            for i, result in enumerate(apply_results):
                patch_label = (
                    patches[i].file if i < len(patches) else f"patch[{i}]"
                )
                checks[f"{patch_label}:apply_succeeded"] = result.success
                if not result.success:
                    errors.append(
                        f"PatchApplier failed to apply '{result.action}' "
                        f"on {result.file}: {result.reason}"
                    )

        for patch in patches:
            file_rel = patch.file
            file_path = self.repo_path / file_rel

            # 1. File exists on disk after apply
            exists = self._check_file_exists(file_path, errors)
            checks[f"{file_rel}:file_exists"] = exists
            if not exists:
                continue   # remaining checks are meaningless without the file

            # 2. YAML validity (only for .yml / .yaml)
            if file_rel.endswith((".yml", ".yaml")):
                yaml_ok, yaml_errs = self._check_yaml_valid(file_path)
                checks[f"{file_rel}:yaml_valid"] = yaml_ok
                if not yaml_ok:
                    errors.extend(yaml_errs)
                else:
                    # 3. Duplicate step detection (workflow files only)
                    dup_ok, dup_warns = self._check_no_duplicate_steps(file_path)
                    checks[f"{file_rel}:no_duplicate_steps"] = dup_ok
                    warnings.extend(dup_warns)

                    # 4. No empty run blocks
                    empty_ok, empty_errs = self._check_no_empty_run_blocks(file_path)
                    checks[f"{file_rel}:no_empty_run_blocks"] = empty_ok
                    errors.extend(empty_errs)

                    # 5. Patch content actually landed in the file
                    content_ok, content_warns = self._check_patch_content_present(
                        file_path, patch
                    )
                    checks[f"{file_rel}:patch_content_present"] = content_ok
                    warnings.extend(content_warns)

            else:
                # Non-YAML file: just confirm patch content is present
                content_ok, content_warns = self._check_patch_content_present(
                    file_path, patch
                )
                checks[f"{file_rel}:patch_content_present"] = content_ok
                warnings.extend(content_warns)

        # 6. Relevance check — does the patch address the failure category?
        relevance_ok, relevance_warns = self._check_relevance(
            patches, failure_category
        )
        checks["patch_relevance"] = relevance_ok
        warnings.extend(relevance_warns)

        # 7. Command sanity (surface-level shell lint)
        sanity_ok, sanity_warns = self._check_command_sanity(patches)
        checks["command_sanity"] = sanity_ok
        warnings.extend(sanity_warns)

        # ------------------------------------------------------------------
        # Score: weighted average of check outcomes
        # Errors are hard failures; warnings reduce score.
        # ------------------------------------------------------------------
        score = self._compute_score(checks, errors, warnings)
        passed = score >= self.PASS_THRESHOLD and len(errors) == 0

        return QualityCheckResult(
            passed=passed,
            score=score,
            checks=checks,
            warnings=warnings,
            errors=errors,
        )

    # ------------------------------------------------------------------
    # Individual checks
    # ------------------------------------------------------------------

    def _check_file_exists(
        self, file_path: Path, errors: list[str]
    ) -> bool:
        if not file_path.exists():
            errors.append(f"File not found after patch apply: {file_path}")
            return False
        return True

    def _check_yaml_valid(
        self, file_path: Path
    ) -> tuple[bool, list[str]]:
        errors: list[str] = []
        try:
            content = file_path.read_text(encoding="utf-8")
            yaml.safe_load(content)
            return True, []
        except yaml.YAMLError as exc:
            errors.append(f"YAML parse error in {file_path.name}: {exc}")
            return False, errors
        except UnicodeDecodeError as exc:
            errors.append(f"Encoding error reading {file_path.name}: {exc}")
            return False, errors

    def _check_no_duplicate_steps(
        self, file_path: Path
    ) -> tuple[bool, list[str]]:
        """
        Parse the workflow YAML and look for steps with the same `name`
        or identical `run` commands within the same job.

        NOTE: this operates on the parsed YAML structure (plain dicts),
        which is unrelated to PatchInstruction — .get() here is correct.
        """
        warnings: list[str] = []
        try:
            content = yaml.safe_load(file_path.read_text(encoding="utf-8"))
        except Exception:
            return True, []   # YAML check already caught this

        if not isinstance(content, dict):
            return True, []

        jobs = content.get("jobs", {})
        if not isinstance(jobs, dict):
            return True, []

        for job_name, job in jobs.items():
            if not isinstance(job, dict):
                continue
            steps = job.get("steps", [])
            if not isinstance(steps, list):
                continue

            seen_names: set[str] = set()
            seen_runs:  set[str] = set()

            for step in steps:
                if not isinstance(step, dict):
                    continue

                name = (step.get("name") or "").strip()
                run  = (step.get("run") or "").strip()

                if name:
                    if name in seen_names:
                        warnings.append(
                            f"Duplicate step name '{name}' in job '{job_name}'"
                        )
                    seen_names.add(name)

                if run:
                    # Normalise whitespace before comparing
                    run_norm = " ".join(run.split())
                    if run_norm in seen_runs:
                        warnings.append(
                            f"Duplicate run command in job '{job_name}': "
                            f"{run[:60]!r}"
                        )
                    seen_runs.add(run_norm)

        passed = len(warnings) == 0
        return passed, warnings

    def _check_no_empty_run_blocks(
        self, file_path: Path
    ) -> tuple[bool, list[str]]:
        """
        NOTE: operates on parsed YAML (plain dicts) — .get() is correct here.
        """
        errors: list[str] = []
        try:
            content = yaml.safe_load(file_path.read_text(encoding="utf-8"))
        except Exception:
            return True, []

        if not isinstance(content, dict):
            return True, []

        for job_name, job in (content.get("jobs", {}) or {}).items():
            if not isinstance(job, dict):
                continue
            for step in (job.get("steps", []) or []):
                if not isinstance(step, dict):
                    continue
                if "run" in step and not str(step["run"] or "").strip():
                    errors.append(
                        f"Empty 'run:' block in job '{job_name}', "
                        f"step '{step.get('name', '<unnamed>')}'"
                    )

        return len(errors) == 0, errors

    def _check_patch_content_present(
        self, file_path: Path, patch: PatchInstruction
    ) -> tuple[bool, list[str]]:
        """
        Verify that the key content from the patch actually exists in the file.
        Uses a fuzzy substring check — whitespace normalised.
        """
        warnings: list[str] = []
        try:
            file_text = file_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            # File may be UTF-16; try chardet
            try:
                import chardet
                raw = file_path.read_bytes()
                detected = chardet.detect(raw)
                enc = detected.get("encoding") or "utf-8"
                file_text = raw.decode(enc)
            except Exception:
                warnings.append(
                    f"Could not read {file_path.name} to verify content"
                )
                return False, warnings

        patch_content = (patch.content or "").strip()
        if not patch_content:
            return True, []   # nothing to verify

        # Check both the first AND last non-empty, non-comment lines.
        # Checking only the first line is a false-positive risk for
        # multi-line patches: e.g. a 'modify' patch like
        #   "- name: pytest RUN TESTS\n  run: pytest tests/"
        # has its actual change on the LAST line ('pytest tests/'),
        # while the first line ('- name: pytest RUN TESTS') is
        # unchanged boilerplate that already existed in the file even
        # when the modify silently failed to apply.
        candidate_lines = [
            stripped
            for line in patch_content.splitlines()
            if (stripped := line.strip()) and not stripped.startswith("#")
        ]

        if not candidate_lines:
            return True, []

        key_phrases = [candidate_lines[0]]
        if candidate_lines[-1] != candidate_lines[0]:
            key_phrases.append(candidate_lines[-1])

        file_norm = " ".join(file_text.split())

        missing = [
            phrase for phrase in key_phrases
            if " ".join(phrase.split()) not in file_norm
        ]

        if missing:
            for phrase in missing:
                warnings.append(
                    f"Expected content not found in {file_path.name}: "
                    f"{phrase[:80]!r}"
                )
            return False, warnings

        return True, []

    def _check_relevance(
        self, patches: list[PatchInstruction], failure_category: str
    ) -> tuple[bool, list[str]]:
        """
        Check that at least one patch is relevant to the failure category.
        """
        warnings: list[str] = []
        rules = RELEVANCE_RULES.get(failure_category)

        if rules is None:
            # Unknown category — pass with a warning
            warnings.append(
                f"No relevance rules defined for category '{failure_category}'; "
                "skipping relevance check"
            )
            return True, warnings

        workflow_kws = rules["workflow_keywords"]
        file_kws     = rules["file_keywords"]

        for patch in patches:
            file_rel = patch.file
            content  = patch.content or ""

            # Does the patched file name match?
            if any(kw in file_rel for kw in file_kws):
                return True, []

            # Does the patch content contain a relevant keyword?
            if any(kw in content for kw in workflow_kws):
                return True, []

            # Does the file name itself match a workflow path?
            if ".github/workflows" in file_rel:
                if any(kw in content for kw in workflow_kws):
                    return True, []

        warnings.append(
            f"Patch may not address '{failure_category}'. "
            f"Expected: {rules['description']}"
        )
        return False, warnings

    def _check_command_sanity(
        self, patches: list[PatchInstruction]
    ) -> tuple[bool, list[str]]:
        """
        Surface-level sanity checks on shell commands.
        Scans both the patch content AND the final on-disk file content,
        so dangerous commands introduced by the patch are caught even when
        they end up outside the literal patch content string.
        """
        warnings: list[str] = []

        DANGER_PATTERNS = [
            (r"rm\s+-rf\s+/(\s|$)",     "Destructive 'rm -rf /' detected"),
            (r">\s*/dev/sd[a-z]",       "Direct disk write detected"),
            (r"curl\s+.*\|\s*bash",     "Piping curl to bash (supply-chain risk)"),
            (r"wget\s+.*\|\s*sh",       "Piping wget to sh (supply-chain risk)"),
            (r"chmod\s+777",            "chmod 777 — overly permissive"),
            (r"echo\s+.*>>\s*/etc/",   "Writing to /etc (system file mutation)"),
        ]

        seen_messages: set[str] = set()

        def _scan(text: str) -> None:
            for pattern, message in DANGER_PATTERNS:
                if re.search(pattern, text) and message not in seen_messages:
                    warnings.append(f"Command sanity: {message}")
                    seen_messages.add(message)

        for patch in patches:
            # Check the literal patch content string
            _scan(patch.content or "")

            # Also check the full on-disk file after patching
            file_path = self.repo_path / patch.file
            if file_path.exists():
                try:
                    _scan(file_path.read_text(encoding="utf-8"))
                except UnicodeDecodeError:
                    pass  # encoding issues caught elsewhere

        return len(warnings) == 0, warnings

    # ------------------------------------------------------------------
    # Scoring
    # ------------------------------------------------------------------

    def _compute_score(
        self,
        checks: dict[str, bool],
        errors:   list[str],
        warnings: list[str],
    ) -> float:
        if not checks:
            return 0.0

        base_score = sum(checks.values()) / len(checks)

        # Each error kills 0.2 of the score
        error_penalty   = min(len(errors)   * 0.20, 0.60)
        # Each warning kills 0.05
        warning_penalty = min(len(warnings) * 0.05, 0.20)

        return max(0.0, round(base_score - error_penalty - warning_penalty, 3))