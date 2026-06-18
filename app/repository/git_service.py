import os
import shutil

from git import Repo
from git.exc import InvalidGitRepositoryError, GitCommandError

from app.config import GITHUB_TOKEN


# Fixed bot identity used for all auto-remediation commits
BOT_NAME = "AI-CICD-Agent"
BOT_EMAIL = "ai-cicd-agent@users.noreply.github.com"

# Forces every git subprocess this service runs to:
#   1. Never invoke an OS-level credential helper (credential.helper="")
#      so cached credentials (Windows Credential Manager, osxkeychain,
#      etc.) for any unrelated account can NEVER be consulted, even as
#      a fallback.
#   2. Never open an interactive prompt if auth fails
#      (GIT_TERMINAL_PROMPT=0) — fail loudly instead of hanging or
#      silently using a different identity.
# This is passed as env to every git command, NOT written to global/
# system git config, so it never affects any other tool or repo on
# the machine — only this process's git calls.
_GIT_ENV = {
    "GIT_TERMINAL_PROMPT": "0",
}

# Git config overrides applied per-command via `-c` flags rather than
# writing to ~/.gitconfig — same isolation guarantee as _GIT_ENV above.
_GIT_NO_CREDENTIAL_HELPER = ["-c", "credential.helper="]


def _with_token(repo_url):
    """
    Inject GITHUB_TOKEN into an HTTPS GitHub URL so git operations
    (clone/pull/push) authenticate using this app's own token.

    https://github.com/OWNER/REPO.git
      -> https://<token>@github.com/OWNER/REPO.git

    Combined with _GIT_NO_CREDENTIAL_HELPER and _GIT_ENV, this guarantees
    the token is the ONLY credential ever used — no OS-cached credential
    is consulted, even as a fallback.
    """

    if not repo_url.startswith("https://"):
        raise ValueError(
            "Only HTTPS GitHub URLs are supported — SSH URLs rely on "
            "the machine's local SSH agent/keys rather than "
            "GITHUB_TOKEN, which violates the token-only requirement. "
            f"Got: {repo_url!r}"
        )

    if "@" in repo_url.split("://", 1)[1].split("/", 1)[0]:
        # A credential is already embedded in the URL — don't double-inject
        return repo_url

    return repo_url.replace(
        "https://",
        f"https://{GITHUB_TOKEN}@",
        1
    )


class GitService:

    def __init__(
        self,
        workspace="workspace"
    ):
        self.workspace = workspace

        os.makedirs(
            workspace,
            exist_ok=True
        )

    def _repo(self, repo_path):
        """
        Open a Repo with this service's isolated git environment applied,
        so every subsequent .git.<command>() call on it is forced to use
        GIT_TERMINAL_PROMPT=0 and no credential helper.
        """

        repo = Repo(repo_path)

        repo.git.update_environment(
            **_GIT_ENV
        )

        return repo

    def clone_repository(
        self,
        repo_url,
        repo_name
    ):

        destination = os.path.join(
            self.workspace,
            repo_name
        )

        authed_url = _with_token(repo_url)

        if os.path.exists(destination):

            try:

                repo = self._repo(destination)

                # Repo already exists on disk — force its remote to use
                # our token-embedded URL, overriding anything previously
                # set (e.g. from before this fix existed).
                repo.remotes.origin.set_url(authed_url)

                print(
                    f"Repository already exists: "
                    f"{destination}"
                )

                return destination

            except InvalidGitRepositoryError:

                print(
                    f"Invalid repository found. "
                    f"Removing {destination}"
                )

                shutil.rmtree(
                    destination,
                    ignore_errors=True
                )

        print(
            f"Cloning repository into "
            f"{destination}"
        )

        Repo.clone_from(
            authed_url,
            destination,
            env=_GIT_ENV,
            multi_options=_GIT_NO_CREDENTIAL_HELPER,
            allow_unsafe_options=True
        )

        return destination

    def prepare_repository(
        self,
        repo_path
    ):

        try:

            repo = self._repo(repo_path)

        except InvalidGitRepositoryError:

            print(
                f"Not a valid git repository: "
                f"{repo_path}"
            )

            return

        print(
            "\nPreparing repository..."
        )

        base_branch = "develop"

        # A previous run may have left the working copy checked out on a
        # stray feature/fix branch with no upstream tracking (e.g.
        # fix/<category>-<run_id>). Always return to the known base
        # branch BEFORE pulling, so 'git pull' always has tracking info
        # and never fails with "no tracking information for the current
        # branch".
        repo.git.checkout(
            base_branch
        )

        repo.git.reset(
            "--hard"
        )

        repo.git.clean(
            "-fd"
        )

        self._pull_origin(repo, base_branch)

        print(
            "Repository prepared"
        )

    # ------------------------------------------------------------------
    # Phase 10 — Branch Creation
    # ------------------------------------------------------------------

    def create_branch(
        self,
        repo_path,
        branch_name,
        base_branch="main"
    ):
        """
        Create a new branch off base_branch and check it out.

        Goal: isolate the auto-remediation patch on its own branch so it
        never touches main directly.

        If branch_name already exists locally (e.g. a retry of the same
        incident), it is checked out and reset to base_branch rather than
        failing — this keeps re-runs idempotent.
        """

        repo = self._repo(repo_path)

        print(
            f"\nCreating branch '{branch_name}' "
            f"from '{base_branch}'..."
        )

        # Make sure we start from a clean, up to date base branch
        repo.git.checkout(base_branch)
        self._pull_origin(repo, base_branch)

        existing_branches = [
            head.name for head in repo.heads
        ]

        if branch_name in existing_branches:

            print(
                f"Branch '{branch_name}' already exists locally. "
                f"Resetting it to '{base_branch}'."
            )

            repo.git.checkout(branch_name)
            repo.git.reset(
                "--hard",
                base_branch
            )

        else:

            repo.git.checkout(
                "-b",
                branch_name
            )

        print(
            f"On branch '{branch_name}'"
        )

        return branch_name

    # ------------------------------------------------------------------
    # Phase 11 — Commit Changes
    # ------------------------------------------------------------------

    def commit_changes(
        self,
        repo_path,
        commit_message
    ):
        """
        Stage all changes and commit them using a fixed bot identity.

        Returns True if a commit was made, False if there was nothing
        to commit (e.g. the patch produced no actual file changes).
        """

        repo = self._repo(repo_path)

        repo.git.add(
            A=True
        )

        if not repo.is_dirty(
            untracked_files=True
        ):

            print(
                "No changes to commit — "
                "working tree is clean."
            )

            return False

        author = f"{BOT_NAME} <{BOT_EMAIL}>"

        print(
            f"\nCommitting changes as {author}..."
        )

        repo.git.commit(
            "-m",
            commit_message,
            author=author
        )

        print(
            f"Committed: {commit_message}"
        )

        return True

    # ------------------------------------------------------------------
    # Phase 12 — Push Branch
    # ------------------------------------------------------------------

    def push_branch(
        self,
        repo_path,
        branch_name
    ):
        """
        Push branch_name to origin, force-pushing only that branch
        (force-with-lease) so re-running the agent on the same incident
        overwrites a previous attempt rather than failing.

        Authenticates exclusively via the token embedded in the remote
        URL (set by clone_repository) plus an explicitly disabled
        credential helper — no OS-cached credential is ever consulted.
        """

        repo = self._repo(repo_path)

        print(
            f"\nPushing branch '{branch_name}' to origin..."
        )

        try:

            repo.git.execute(
                [
                    "git",
                    *_GIT_NO_CREDENTIAL_HELPER,
                    "push",
                    "--force-with-lease",
                    "origin",
                    branch_name
                ]
            )

        except GitCommandError as exc:

            print(
                f"Push failed for branch "
                f"'{branch_name}': {exc}"
            )

            raise

        print(
            f"Pushed branch '{branch_name}'"
        )

        return branch_name

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _pull_origin(self, repo, branch_name):
        """
        Pull a specific branch from origin with the credential helper
        explicitly disabled, guaranteeing the token-embedded remote URL
        is the only credential source — never an OS-cached one.

        Pulling a named branch (not a bare 'git pull') avoids relying on
        the current branch having upstream tracking configured, the same
        issue that caused 'There is no tracking information for the
        current branch' previously.
        """

        repo.git.execute(
            [
                "git",
                *_GIT_NO_CREDENTIAL_HELPER,
                "pull",
                "origin",
                branch_name
            ]
        )