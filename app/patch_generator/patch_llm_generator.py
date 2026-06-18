import json

from app.patch_generator.patch_models import (
    PatchInstruction,
    PatchPlan
)


class PatchLLMGenerator:

    def __init__(self, llm_provider):
        self.llm = llm_provider

    def generate(
        self,
        classification,
        analysis,
        repository_context
    ):

        prompt = f"""
You are a Senior DevOps Engineer generating surgical patch operations to fix a CI/CD failure.

Rules:
- Never rewrite an entire file.
- Never return the full content of a file.
- Return only the minimal change required to fix the issue.
- Analyse the repository context carefully before deciding which file and action to use.

Allowed actions and how to use them:

  append
    Adds content at the end of the file.
    - file: path to the file
    - content: the text to append
    - target: leave empty ""

  insert_after
    Inserts content on a new line immediately after the target line.
    - file: path to the file
    - target: exact line that already exists in the file (copy it verbatim)
    - content: the new text to insert after that line

  insert_before
    Inserts content on a new line immediately before the target line.
    - file: path to the file
    - target: exact line that already exists in the file (copy it verbatim)
    - content: the new text to insert before that line

  modify
    Replaces an existing block of text with new text.
    Use this when a line or block needs to be changed, not just added near.
    - file: path to the file
    - target: the exact existing text to find and replace (copy it verbatim from the file)
    - content: the new text that will replace the target

  create
    Creates a new file with the given content.
    - file: path to the new file
    - content: full content of the new file
    - target: leave empty ""

Repository Context:

{repository_context}

Failure Classification:

{classification}

Analysis:

{analysis}

Return ONLY valid JSON. No explanation. No markdown. No code fences.

Schema:

{{
    "patches": [
        {{
            "file": "",
            "action": "",
            "target": "",
            "content": ""
        }}
    ]
}}
"""

        response = self.llm.generate(prompt)
        print("\n===== RAW PATCH RESPONSE =====")
        print(response)
        print("==============================\n")

        try:

            start = response.find("{")
            end = response.rfind("}") + 1

            data = json.loads(
                response[start:end]
            )

            patches = []

            for patch in data["patches"]:

                patches.append(
                    PatchInstruction(
                        file=patch["file"],
                        action=patch["action"],
                        content=patch["content"],
                        target=patch.get("target", "")
                    )
                )

            return PatchPlan(
                patches=patches
            )

        except Exception as e:

            print(f"Patch generation failed: {e}")
            return PatchPlan()