from pathlib import Path


class RepositoryContextCollector:

    IMPORTANT_FILES = [
        "requirements.txt",
        "pyproject.toml",
        "Dockerfile",
        "package.json",
        "pom.xml"
    ]

    def collect(
        self,
        repo_path
    ):
        repo_path = Path(repo_path)

        context = {
            "project_type": "unknown",
            "workflow_files": [],
        }

        workflow_dir = (
            repo_path /
            ".github" /
            "workflows"
        )

        if workflow_dir.exists():

            for file in workflow_dir.glob("*"):
                context["workflow_files"].append(
                    {
                        "name": file.name,
                        "path": str(
                            file.relative_to(
                                repo_path
                            )
                        ),
                        "content": file.read_text(
                            encoding="utf-8",
                            errors="ignore"
                        )
                    }
                )

        for filename in self.IMPORTANT_FILES:

            file_path = repo_path / filename

            if file_path.exists():

                context[
                    filename.replace(".", "_")
                ] = file_path.read_text(
                    encoding="utf-8",
                    errors="ignore"
                )

        context["project_type"] = (
            self.detect_project_type(context)
        )

        return context

    def detect_project_type(
        self,
        context
    ):
        if "requirements_txt" in context:
            return "python"

        if "pyproject_toml" in context:
            return "python"

        if "package_json" in context:
            return "nodejs"

        if "pom_xml" in context:
            return "java"

        return "unknown"