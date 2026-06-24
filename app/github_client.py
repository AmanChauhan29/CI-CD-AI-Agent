import time

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
    def get_workflow_run(self, run_id):
        url = (
            f"{self.base_url}"
            f"/repos/{REPO_OWNER}/{REPO_NAME}"
            f"/actions/runs/{run_id}"
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
    
    def get_workflow_runs_for_branch(
        self,
        branch_name
    ):

        runs = self.get_workflow_runs()

        matching_runs = []

        for run in runs["workflow_runs"]:

            if run["head_branch"] == branch_name:

                matching_runs.append(
                    {
                        "id": run["id"],
                        "status": run["status"],
                        "conclusion": run["conclusion"],
                        "name": run["name"]
                    }
                )

        return matching_runs
    
    def wait_for_workflow_completion(
        self,
        run_id,
        poll_interval=10,
        timeout=600
    ):

        start_time = time.time()

        while True:

            run = self.get_workflow_run(
                run_id
            )

            status = run["status"]

            conclusion = run["conclusion"]

            print(
                f"Workflow {run_id} | "
                f"status={status} "
                f"conclusion={conclusion}"
            )

            if status == "completed":

                return run

            if (
                time.time() - start_time
            ) > timeout:

                raise TimeoutError(
                    f"Workflow {run_id} "
                    f"did not complete "
                    f"within {timeout} seconds"
                )

            time.sleep(
                poll_interval
            )


    def get_latest_workflow_run_for_branch(
        self,
        branch_name
    ):
        runs = self.get_workflow_runs_for_branch(
            branch_name
        )

        if not runs:
            return None

        return max(
            runs,
            key=lambda run: run["id"]
        )