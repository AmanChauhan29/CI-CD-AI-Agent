"""
Tests for PatchQualityChecker.

Run:
    python test_patch_quality_checker.py
"""

import tempfile
import textwrap
from pathlib import Path

from patch_quality_checker import PatchQualityChecker, QualityCheckResult


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_repo(files: dict[str, str]) -> Path:
    """Create a temp directory with the given file contents."""
    tmp = Path(tempfile.mkdtemp())
    for rel_path, content in files.items():
        full = tmp / rel_path
        full.parent.mkdir(parents=True, exist_ok=True)
        full.write_text(content, encoding="utf-8")
    return tmp


def check(repo_path, patches, analysis=None, category="dependency_failure"):
    if analysis is None:
        analysis = {"root_cause": "pytest missing", "suggested_fix": "install pytest"}
    checker = PatchQualityChecker(repo_path)
    return checker.check(patches, analysis, category)


# ---------------------------------------------------------------------------
# Test cases
# ---------------------------------------------------------------------------

def test_valid_yaml_patch_passes():
    """Happy path: valid YAML, correct content, correct category."""
    workflow = textwrap.dedent("""\
        name: CI
        on: [push]
        jobs:
          build:
            runs-on: ubuntu-latest
            steps:
              - name: Install dependencies
                run: pip install -r requirements.txt
              - name: Install pytest
                run: pip install pytest
              - name: Run tests
                run: pytest
    """)
    repo = make_repo({".github/workflows/ci.yml": workflow})
    patches = [{
        "file": ".github/workflows/ci.yml",
        "action": "insert_after",
        "target": "run: pip install -r requirements.txt",
        "content": "      - name: Install pytest\n        run: pip install pytest",
    }]
    result = check(repo, patches)
    print(result.summary())
    assert result.passed, f"Expected pass, got: {result.errors}"


def test_invalid_yaml_fails():
    """Patch that produces broken YAML must fail."""
    bad_yaml = textwrap.dedent("""\
        name: CI
        jobs:
          build:
            steps:
              - name: Bad step
                run: |
              invalid_indent_here
    """)
    repo = make_repo({".github/workflows/ci.yml": bad_yaml})
    patches = [{
        "file": ".github/workflows/ci.yml",
        "action": "append",
        "content": "  garbage: [unclosed",
    }]
    # Override file with the bad content directly
    (repo / ".github/workflows/ci.yml").write_text(bad_yaml + "\n  garbage: [unclosed")
    result = check(repo, patches)
    print(result.summary())
    assert not result.passed
    assert any("YAML" in e for e in result.errors)


def test_duplicate_step_name_warning():
    """Workflow with two steps of the same name produces a warning."""
    workflow = textwrap.dedent("""\
        name: CI
        on: [push]
        jobs:
          build:
            runs-on: ubuntu-latest
            steps:
              - name: Install pytest
                run: pip install pytest
              - name: Install pytest
                run: pip install pytest==8.2.2
    """)
    repo = make_repo({".github/workflows/ci.yml": workflow})
    patches = [{
        "file": ".github/workflows/ci.yml",
        "action": "insert_after",
        "target": "run: pip install -r requirements.txt",
        "content": "      - name: Install pytest\n        run: pip install pytest",
    }]
    result = check(repo, patches)
    print(result.summary())
    assert any("Duplicate step name" in w for w in result.warnings)


def test_patch_content_not_present_warns():
    """If patch content is missing from the file, we warn."""
    workflow = textwrap.dedent("""\
        name: CI
        on: [push]
        jobs:
          build:
            runs-on: ubuntu-latest
            steps:
              - name: Install dependencies
                run: pip install -r requirements.txt
    """)
    repo = make_repo({".github/workflows/ci.yml": workflow})
    patches = [{
        "file": ".github/workflows/ci.yml",
        "action": "insert_after",
        "target": "run: pip install -r requirements.txt",
        "content": "pip install pytest",   # NOT in the file
    }]
    result = check(repo, patches)
    print(result.summary())
    assert any("not found" in w for w in result.warnings)


def test_missing_file_fails():
    """Patch that references a non-existent file after apply must error."""
    repo = make_repo({})  # empty repo
    patches = [{
        "file": ".github/workflows/ci.yml",
        "action": "append",
        "content": "pip install pytest",
    }]
    result = check(repo, patches)
    print(result.summary())
    assert not result.passed
    assert any("not found" in e for e in result.errors)


def test_irrelevant_patch_warns():
    """Patch for dependency_failure that doesn't install anything should warn."""
    workflow = textwrap.dedent("""\
        name: CI
        on: [push]
        jobs:
          build:
            runs-on: ubuntu-latest
            steps:
              - name: Checkout
                uses: actions/checkout@v3
              - name: Echo message
                run: echo "hello"
    """)
    repo = make_repo({".github/workflows/ci.yml": workflow})
    patches = [{
        "file": ".github/workflows/ci.yml",
        "action": "append",
        "content": "      - name: Echo message\n        run: echo hello",
    }]
    result = check(repo, patches, category="dependency_failure")
    print(result.summary())
    assert any("may not address" in w for w in result.warnings)


def test_requirements_txt_patch_is_relevant():
    """Adding to requirements.txt is relevant for dependency_failure."""
    repo = make_repo({"requirements.txt": "flask==2.0.0\npytest==8.2.2\n"})
    patches = [{
        "file": "requirements.txt",
        "action": "append",
        "content": "pytest==8.2.2",
    }]
    result = check(repo, patches, category="dependency_failure")
    print(result.summary())
    assert result.checks.get("patch_relevance") is True


def test_dangerous_command_warns():
    """rm -rf / in patch content should be flagged."""
    workflow = textwrap.dedent("""\
        name: CI
        on: [push]
        jobs:
          build:
            runs-on: ubuntu-latest
            steps:
              - name: Dangerous
                run: rm -rf /
    """)
    repo = make_repo({".github/workflows/ci.yml": workflow})
    patches = [{
        "file": ".github/workflows/ci.yml",
        "action": "append",
        "content": "run: rm -rf /",
    }]
    result = check(repo, patches, category="command_failure")
    print(result.summary())
    assert any("rm -rf" in w for w in result.warnings)


def test_empty_run_block_errors():
    """A step with an empty run: block is an error."""
    workflow = textwrap.dedent("""\
        name: CI
        on: [push]
        jobs:
          build:
            runs-on: ubuntu-latest
            steps:
              - name: Empty step
                run:
    """)
    repo = make_repo({".github/workflows/ci.yml": workflow})
    patches = [{
        "file": ".github/workflows/ci.yml",
        "action": "append",
        "content": "      - name: Empty step\n        run:",
    }]
    result = check(repo, patches)
    print(result.summary())
    assert not result.passed
    assert any("Empty" in e and "run" in e for e in result.errors), \
        f"Expected empty run error, got errors={result.errors}"


def test_score_degrades_with_warnings():
    """Multiple warnings should reduce the score below 1.0."""
    workflow = textwrap.dedent("""\
        name: CI
        on: [push]
        jobs:
          build:
            runs-on: ubuntu-latest
            steps:
              - name: Install pytest
                run: pip install pytest
              - name: Install pytest
                run: pip install pytest
    """)
    repo = make_repo({".github/workflows/ci.yml": workflow})
    patches = [{
        "file": ".github/workflows/ci.yml",
        "action": "append",
        "content": "pip install pytest",
    }]
    result = check(repo, patches)
    print(result.summary())
    assert result.score < 1.0


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    tests = [
        test_valid_yaml_patch_passes,
        test_invalid_yaml_fails,
        test_duplicate_step_name_warning,
        test_patch_content_not_present_warns,
        test_missing_file_fails,
        test_irrelevant_patch_warns,
        test_requirements_txt_patch_is_relevant,
        test_dangerous_command_warns,
        test_empty_run_block_errors,
        test_score_degrades_with_warnings,
    ]

    passed = 0
    failed = 0
    for t in tests:
        print(f"\n{'='*60}")
        print(f"TEST: {t.__name__}")
        print('='*60)
        try:
            t()
            print(f"✓ PASSED")
            passed += 1
        except AssertionError as e:
            print(f"✗ FAILED: {e}")
            failed += 1
        except Exception as e:
            print(f"✗ ERROR:  {type(e).__name__}: {e}")
            failed += 1

    print(f"\n{'='*60}")
    print(f"Results: {passed} passed, {failed} failed out of {len(tests)} tests")
    print('='*60)