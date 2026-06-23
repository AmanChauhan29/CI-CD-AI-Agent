from app.classifiers.patterns import FAILURE_PATTERNS

class FailureClassifier:
    def classify(self, logs):

        for file_name, content in logs.items():

            content_lower = content.lower()

            for category, patterns in FAILURE_PATTERNS.items():

                for pattern in patterns:

                    if pattern.lower() in content_lower:

                        index = content_lower.find(
                            pattern.lower()
                        )

                        snippet = content[
                            max(0, index - 150):
                            index + 300
                        ]

                        return {
                            "category": category,
                            "confidence": 0.90,
                            "matched_pattern": pattern,
                            "file": file_name,
                            "snippet": snippet
                        }
        largest_file = None
        largest_content = ""
        for file_name, content in logs.items():
            if len(content) > len(largest_content):
                largest_file = file_name
                largest_content = content
        error_keywords = [
            "error",
            "failed",
            "exception",
            "traceback",
            "exit code"
        ]

        snippet = None

        content_lines = (
            largest_content.splitlines()
        )

        for index, line in enumerate(content_lines):

            lower_line = line.lower()

            if any(
                keyword in lower_line
                for keyword in error_keywords
            ):

                start = max(
                    0,
                    index - 5
                )

                end = min(
                    len(content_lines),
                    index + 15
                )

                snippet = "\n".join(
                    content_lines[start:end]
                )

                break

        if snippet is None:

            snippet = largest_content[-1000:]

        return {
            "category": "unknown_failure",
            "confidence": 0.0,
            "matched_pattern": None,
            "file": largest_file,
            "snippet": snippet
        }
