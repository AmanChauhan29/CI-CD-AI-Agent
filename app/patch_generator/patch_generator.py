from app.patch_generator.patch_models import (
    PatchInstruction,
    PatchPlan
)


class PatchGenerator:

    def generate(
        self,
        classification,
        analysis,
        repository_context
    ):

        category = classification["category"]

        if category == "dependency_failure":

            patches = self.handle_dependency_failure(
                analysis,
                repository_context
            )

            return PatchPlan(
                patches=patches
            )

        return PatchPlan()

    def handle_dependency_failure(
        self,
        analysis,
        repository_context
    ):

        patches = []

        requirements = repository_context.get(
            "requirements_txt",
            ""
        )

        if "pytest" not in requirements.lower():

            patches.append(
                PatchInstruction(
                    file="requirements.txt",
                    action="append",
                    content="\npytest\n"
                )
            )

        return patches