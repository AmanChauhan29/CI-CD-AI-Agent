from app.github_client import GitHubClient
from app.incident_respository import save_incident
from app.log_service import LogService
from app.classifiers.failure_classifiers import FailureClassifier
from database.db import init_db
from app.llm.analyzer import FailureAnalyzer
from app.analysis_repository import save_analysis   
from app.repository.git_service import GitService
from app.repository.pr_service import PullRequestService
from app.patch_generator.patch_generator import PatchGenerator
from app.patch_generator.patch_llm_generator import (
    PatchLLMGenerator
)
from app.patch_generator.patch_quality_checker import PatchQualityChecker
import shutil
from pathlib import Path
from app.patch_generator.patch_applier import (
    PatchApplier
)
from app.patch_generator.patch_validator import (
    PatchValidator
)
from app.patch_generator.remediation_verifier import (
    RemediationVerifier
)
from app.repository.repo_context import (
    RepositoryContextCollector
)
from app.config import (
    GITHUB_TOKEN,
    AGENT_NAME,
    REPO_OWNER,
    REPO_NAME
)
from app.llm.hf_provider import (
    HuggingFaceProvider
)


init_db()
client = GitHubClient()

failed_runs = client.get_failed_runs()

if not failed_runs:
    print("No failures found")
    exit()

run_id = failed_runs[0]["id"]

zip_content = client.download_workflow_logs(
    run_id
)

log_service = LogService()

logs = log_service.extract_logs(
    zip_content
)


# for file_name, content in logs.items():

#     print(f"\n===== {file_name} =====")

#     print(content[-3000:])

classifier = FailureClassifier()
result = classifier.classify(logs)
print("\nClassification Result:")
print(result)
incident_id = save_incident(
    run_id,
    failed_runs[0]["name"],
    result
)

print("\nIncident saved successfully")
is_unknown_failure = (
    result["category"] == "unknown_failure"
)

if is_unknown_failure:
    print(
        "\nClassification returned 'unknown_failure'. "
        "Will perform LLM analysis and generate recommendations "
        "but will NOT auto-remediate or create a PR."
    )
provider = HuggingFaceProvider()

analyzer = FailureAnalyzer(provider)

# analysis = analyzer.analyze(result)

git_service = GitService()
pr_service = PullRequestService()


repo_path = git_service.clone_repository(
    repo_url=f"https://github.com/{REPO_OWNER}/{REPO_NAME}.git",
    repo_name=f"{REPO_NAME}"
)
git_service.prepare_repository(
    repo_path
)
branch_name = f"fix/{result['category']}-{run_id}" 
git_service.create_branch(repo_path, branch_name, base_branch="develop")

collector = RepositoryContextCollector()

context = collector.collect(
    repo_path
)
print("\nRepository Context:\n")

print(
    f"Project Type: "
    f"{context['project_type']}"
)

print(
    f"Workflow Files: "
    f"{len(context['workflow_files'])}"

)
print("\n===== WORKFLOW CONTENT =====")

for workflow in context["workflow_files"]:
    print(f"\nWorkflow Name: {workflow['name']}")
    print("-" * 50)
    print(workflow["content"])
    # if "requirements_txt" in context:
    #     print("\n===== REQUIREMENTS.TXT =====")
    #     print(context["requirements_txt"])

analysis_input = {
    "incident": result,
    "repository_context": context
}

analysis = analyzer.analyze(
    analysis_input
)

print("\nAnalysis Result:")
print(analysis)

save_analysis(
    incident_id,
    analysis
)

print("\nAnalysis saved successfully")
if is_unknown_failure:

    print("\n===== UNKNOWN FAILURE ANALYSIS =====")

    print(f"Run ID: {run_id}")
    print(f"Workflow: {failed_runs[0]['name']}")
    print(f"Incident ID: {incident_id}")

    print("\nRoot Cause:")
    print(analysis.get("root_cause"))

    print("\nWhy It Happened:")
    print(analysis.get("why_it_happened"))

    print("\nRecommended Solution:")
    print(analysis.get("suggested_fix"))

    print(
        "\nUnknown failure detected. "
        "Skipping patch generation, repository modification, "
        "git push, and PR creation."
    )

    exit()
    
verifier = RemediationVerifier()
verification = verifier.verify(
    str(analysis),
    context
)
print("\nVerification Result:")
print(verification)
generator = PatchLLMGenerator(
    provider
)

patch_plan = generator.generate(
    result,
    analysis,
    context
)
validator = PatchValidator()

validated_patch_plan = (
    validator.validate(
        patch_plan
    )
)
print("\nGenerated Patch Plan:")

for patch in validated_patch_plan.patches:
    print(patch)

applier = PatchApplier()

print("\n===== PATCH DEBUG =====")

for patch in validated_patch_plan.patches:
    print("FILE:", patch.file)
    print("ACTION:", patch.action)
    print("CONTENT REPR:", repr(patch.content))
    print("CONTENT:", patch.content)
# requirements_file = (
#     Path(repo_path)
#     / "requirements.txt"
# )

# with open(
#     requirements_file,
#     "rb"
# ) as f:

#     raw = f.read(100)

# print("\n===== FILE ENCODING DEBUG =====")
# print(raw[:50])
apply_result=applier.apply(
    repo_path,
    validated_patch_plan
)
checker = PatchQualityChecker(repo_path)
quality = checker.check(
    patches=validated_patch_plan.patches,
    analysis=analysis,          # from LLMAnalyzer
    failure_category=result["category"],  # from FailureClassifier
    apply_results=apply_result,
)
print(quality.summary())
if not quality.passed:
    print("Patch quality check failed — skipping Git push")
else:
    committed = git_service.commit_changes(
        repo_path,
        commit_message=f"fix: {analysis['root_cause']}"
    )
    if committed:
        git_service.push_branch(repo_path, branch_name)

        pr = pr_service.create_pull_request(
            branch_name=branch_name,
            title=f"Auto-fix: {analysis['root_cause']}",
            body=analysis["suggested_fix"],
            base_branch="develop"
        )
        print(f"PR: {pr['url']}")
    else:
        print("Nothing to commit — skipping push/PR")