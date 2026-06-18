from .patch_models import *
from dataclasses import dataclass


class RemediationVerifier:

    def verify(
        self,
        suggested_fix: str,
        repository_context: dict
    ) -> VerificationResult:

        fix_lower = suggested_fix.lower()

        workflow_contents = []

        for workflow in repository_context.get("workflow_files", []):
            workflow_contents.append(
                workflow.get("content", "").lower()
            )

        combined_workflows = "\n".join(workflow_contents)

        # pytest installation check
        if "pytest" in fix_lower:

            install_patterns = [
                "pip install pytest",
                "python -m pip install pytest"
            ]

            for pattern in install_patterns:
                if pattern in combined_workflows:
                    return VerificationResult(
                        already_present=True,
                        reason=f"Found existing remediation: {pattern}"
                    )

        return VerificationResult(
            already_present=False,
            reason="No matching remediation found"
        )