from github import Github
from github.GithubException import GithubException

from app.config import (
    GITHUB_TOKEN,
    REPO_OWNER,
    REPO_NAME
)


class PullRequestService:
    """
    Creates Pull Requests for auto-remediation branches using PyGithub.

    Reuses the same GITHUB_TOKEN / REPO_OWNER / REPO_NAME that
    GitHubClient already uses, so there is a single source of truth
    for GitHub credentials in this project.
    """

    def __init__(self):

        self.client = Github(GITHUB_TOKEN)

        self.repo = self.client.get_repo(
            f"{REPO_OWNER}/{REPO_NAME}"
        )

    def create_pull_request(
        self,
        branch_name,
        title,
        body,
        base_branch="main"
    ):
        """
        Open a PR from branch_name into base_branch.

        Goal: turn a pushed fix branch into a reviewable Pull Request.

        If a PR already exists for this branch (e.g. a retry), returns
        the existing PR instead of failing — keeps re-runs idempotent.

        Returns a dict: {"number": int, "url": str, "created": bool}
        """

        existing = self._find_existing_pr(
            branch_name,
            base_branch
        )

        if existing is not None:

            print(
                f"PR already exists for branch "
                f"'{branch_name}': #{existing.number} "
                f"({existing.html_url})"
            )

            return {
                "number": existing.number,
                "url": existing.html_url,
                "created": False
            }

        print(
            f"\nCreating PR: '{branch_name}' -> '{base_branch}'..."
        )

        try:

            pr = self.repo.create_pull(
                title=title,
                body=body,
                head=branch_name,
                base=base_branch
            )

        except GithubException as exc:

            print(
                f"PR creation failed for branch "
                f"'{branch_name}': {exc.data}"
            )

            raise

        print(
            f"Created PR #{pr.number}: {pr.html_url}"
        )

        return {
            "number": pr.number,
            "url": pr.html_url,
            "created": True
        }

    def _find_existing_pr(
        self,
        branch_name,
        base_branch
    ):
        """
        Look for an open PR already targeting base_branch from
        branch_name, to avoid creating duplicate PRs on re-runs.
        """

        head_ref = f"{REPO_OWNER}:{branch_name}"

        open_pulls = self.repo.get_pulls(
            state="open",
            base=base_branch,
            head=head_ref
        )

        for pr in open_pulls:

            return pr

        return None