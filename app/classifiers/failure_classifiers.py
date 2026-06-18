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
        return {
            "category": "unknown_failure",
            "confidence": 0.0,
            "matched_pattern": None,
            "file": None,
            "snippet": None
        }
