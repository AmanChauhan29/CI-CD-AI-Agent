from app.patch_generator.patch_models import (
    PatchPlan
)


class PatchValidator:
    ALLOWED_ACTIONS = [
        "add",
        "append",
        "insert_after",
        "insert_before",
        "create",
        "modify"
    ]

    def validate(
        self,
        patch_plan: PatchPlan
    ):

        valid_patches = []
        for patch in patch_plan.patches:
            if patch.action not in self.ALLOWED_ACTIONS:
                print(
                    f"Rejected patch action: "
                    f"{patch.action}"
                )
                continue

            if len(patch.content) > 500:
                print(
                    f"Rejected large patch: "
                    f"{patch.file}"
                )
                continue

            valid_patches.append(
                patch
            )

        return PatchPlan(
            patches=valid_patches
        )