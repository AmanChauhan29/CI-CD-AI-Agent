FAILURE_PATTERNS = {
    "dependency_failure": [
        "command not found",
        "No module named",
        "ModuleNotFoundError",
        "No matching distribution found"
    ],

    "test_failure": [
        "AssertionError",
        "FAILED",
        "failed:",
        "ERROR at setup",
        "ERROR at teardown"
    ],

    "docker_failure": [
        "docker build failed",
        "failed to solve",
        "pull access denied",
        "docker buildx build failed"
    ],

    "permission_failure": [
        "permission denied",
        "access denied",
        "forbidden"
    ],

    "terraform_failure": [
        "terraform apply failed",
        "terraform init failed"
    ],
    "no_tests_collected": [
        "no tests ran",
        "collected 0 items",
        "no tests found"
    ]
}