import requests
import zipfile
import tempfile
import os

from app.config import (
    GITHUB_TOKEN,
    AGENT_NAME,
    REPO_OWNER,
    REPO_NAME
)

class GitHubClient:

    def __init__(self):
        self.base_url = "https://api.github.com"

        self.headers = {
            "Authorization": f"Bearer {GITHUB_TOKEN}",
            "Accept": "application/vnd.github+json"
        }

    def get_workflow_runs(self):

        url = (
            f"{self.base_url}"
            f"/repos/{REPO_OWNER}/{REPO_NAME}"
            "/actions/runs"
        )

        response = requests.get(
            url,
            headers=self.headers
        )

        response.raise_for_status()

        return response.json()
    
    def print_workflow_runs(self):

        data = self.get_workflow_runs()

        for run in data["workflow_runs"]:

            print(
                f"Name: {run['name']}"
            )

            print(
                f"Run ID: {run['id']}"
            )

            print(
                f"Status: {run['status']}"
            )

            print(
                f"Conclusion: {run['conclusion']}"
            )

            print("-" * 50)

    def get_failed_runs(self):

        runs = self.get_workflow_runs()

        failed_runs = []

        for run in runs["workflow_runs"]:

            if run["conclusion"] == "failure":

                failed_runs.append(
                    {
                        "id": run["id"],
                        "name": run["name"],
                        "branch": run["head_branch"]
                    }
                )

        return failed_runs
    
    def download_workflow_logs(self, run_id):

        url = (
            f"{self.base_url}"
            f"/repos/{REPO_OWNER}/{REPO_NAME}"
            f"/actions/runs/{run_id}/logs"
        )

        response = requests.get(
            url,
            headers=self.headers,
            allow_redirects=True
        )

        response.raise_for_status()

        return response.content