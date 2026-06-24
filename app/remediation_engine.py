import time
from app.github_client import GitHubClient
from app.log_service import LogService
from app.classifiers.failure_classifiers import FailureClassifier
from app.llm.analyzer import FailureAnalyzer
from app.patch_generator.patch_applier import PatchApplier
from app.patch_generator.patch_generator import PatchGenerator
from app.patch_generator.patch_llm_generator import PatchLLMGenerator
from app.patch_generator.patch_quality_checker import PatchQualityChecker
from app.patch_generator.patch_validator import PatchValidator
from app.patch_generator.remediation_verifier import RemediationVerifier
from app.repository.git_service import GitService
from app.repository.pr_service import PullRequestService
from app.llm.hf_provider import HuggingFaceProvider
from app.incident_respository import save_incident, mark_incident_resolved
from app.analysis_repository import save_analysis
from app.repository.repo_context import RepositoryContextCollector
from app.config import (
    GITHUB_TOKEN,
    AGENT_NAME,
    REPO_OWNER,
    REPO_NAME
) 
class RemediationEngine:
    def __init__(self):
        self.client = GitHubClient()
        self.provider = HuggingFaceProvider()
        self.classifier = FailureClassifier()
        self.analyzer = FailureAnalyzer(self.provider)
        self.git_service = GitService()
        self.pr_service = PullRequestService()
        self.log_service = LogService()
        self.repo_context_collector = RepositoryContextCollector()
        self.verifier = RemediationVerifier()
        self.patch_generator = PatchLLMGenerator(self.provider)
        self.patch_validator = PatchValidator()
        self.patch_applier = PatchApplier()

    def process(self,run_id: int):
        print(
            f"Processing workflow "
            f"{run_id}"
        )
        logs = self.load_logs(run_id)
        classification  = self.classify_failure(logs)
        workflow_name = self.client.get_workflow_run(run_id).get("name")
        incident_id = save_incident(run_id,workflow_name,classification) #### need here workflow name
        repo_path = self.git_service.clone_repository(
            repo_url=f"https://github.com/{REPO_OWNER}/{REPO_NAME}.git",
            repo_name=f"{REPO_NAME}"
        )
        if repo_path: 
            self.git_service.prepare_repository(repo_path)
        
        context = self.repo_context_collector.collect(
            repo_path=repo_path
        )
        print("\nRepository Context:\n")
        print(
            f"Project Type: "
            f"{context['project_type']}"
        )
        for workflow in context["workflow_files"]:
            print(f"\nWorkflow Name: {workflow['name']}")
            print("-" * 50)
            print(workflow["content"])

        analysis_input = {
            "incident": classification,
            "repository_context": context
        }
        analysis = self.analyzer.analyze(analysis_input)
        print("\nAnalysis Result:")
        print(analysis)
        save_analysis(incident_id, analysis)
        if analysis:
            print("Analysis saved successfully.")
        verification_result = self.verifier.verify(
            str(analysis),
            context
        )
        print(f"verification_result: {verification_result}")
        patch_plan = self.patch_generator.generate(
            classification,
            analysis,
            context
        )
        patch_validate = self.patch_validator.validate(
            patch_plan
        )
        print(f"Patch validation result: {patch_validate}")
        patch_applier = self.patch_applier.apply(
            repo_path,
            patch_validate
        )
        patch_check = PatchQualityChecker(repo_path)
        quality = patch_check.check(
            patches = patch_validate.patches,
            analysis=analysis,
            failure_category=classification["category"],
            apply_results = patch_applier,
        )
        print(quality.summary())
        if not quality.passed:
            print("Patch quality check failed — skipping Git push")
        else:
            branch_name = f"fix/{classification['category']}-{run_id}"
            self.git_service.create_branch(repo_path, branch_name, base_branch="develop")
            committed = self.git_service.commit_changes(repo_path, commit_message=f"fix: {analysis['root_cause']}")
            if committed:
                self.git_service.push_branch(repo_path, branch_name)
                pr = self.pr_service.create_pull_request(
                    branch_name=branch_name,
                    title=f"Auto-fix: {analysis['root_cause']}",
                    body=analysis["suggested_fix"],
                    base_branch="develop"
                )
                print(f"PR: {pr['url']}")
                time.sleep(20)
                runs = self.client.get_workflow_runs_for_branch(branch_name)
                latest_run = max(runs, key=lambda run:run["id"])
                print(f"\n Latest PR Workflow {latest_run}")
                completed_run = (self.client.wait_for_workflow_completion(latest_run["id"]))
                print(f"\n Workflow Finished {completed_run}")
                if completed_run["conclusion"] == "success":
                    print(
                        "\nWorkflow verification succeeded."
                        "\nMerging PR..."
                    )
                    merge_result = (
                        self.pr_service.merge_pull_request(
                            pr["number"]
                        )
                    )
                    print(
                        f"Merged: "
                        f"{merge_result['merged']}"
                    )
                    if merge_result["merged"]:
                        mark_incident_resolved(
                            incident_id=incident_id,
                            pr_number=pr["number"],
                            workflow_run_id=completed_run["id"]
                        )

                        print(
                            f"Incident {incident_id} "
                            f"marked resolved"
                        )   
                else:
                    print(
                        "\nWorkflow verification failed."
                        "\nPR will remain open."
                    )       
            else:
                print("Nothing to commit — skipping push/PR")
                
        
    def load_logs(self,run_id):
        zip_content = self.client.download_workflow_logs(run_id)
        logs = self.log_service.extract_logs(zip_content)
        return logs
    
    def classify_failure(self, logs):
        result = self.classifier.classify(
            logs
        )
        print(
            "\nClassification Result:"
        )
        print(result)
        return result