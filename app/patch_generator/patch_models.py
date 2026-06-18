from dataclasses import dataclass, field


@dataclass
class PatchInstruction:

    file: str

    action: str

    content: str

    target: str = ""


@dataclass
class PatchPlan:

    patches: list[PatchInstruction] = field(
        default_factory=list
    )

@dataclass
class VerificationResult:
    already_present: bool
    reason: str

from dataclasses import dataclass

@dataclass
class QualityResult:
    passed: bool
    reason: str