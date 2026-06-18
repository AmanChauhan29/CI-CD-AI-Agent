import json

class FailureAnalyzer:

    def __init__(
        self,
        llm_provider
    ):
        self.llm = llm_provider

    def analyze(self, analysis_input):
        incident = analysis_input["incident"]
        repository_context = analysis_input.get(
            "repository_context",
            {}
        )
        prompt = f"""
        You are a Senior DevOps Engineer.

        Analyze the CI/CD failure.

        Use BOTH:

        1. Failure information
        2. Repository context

        before determining root cause.

        Failure Information

        Category:
        {incident['category']}

        Pattern:
        {incident['matched_pattern']}

        Snippet:
        {incident['snippet']}

        Repository Context

        Project Type:
        {repository_context.get('project_type')}

        Requirements:
        {repository_context.get('requirements_txt', '')}

        Workflow Files:
        {repository_context.get('workflow_files', [])}

        Return ONLY valid JSON.

        {{
            "root_cause": "",
            "why_it_happened": "",
            "suggested_fix": "",
            "confidence": 0
        }}
        """
        response = self.llm.generate(
            prompt
        )
        try:

            return json.loads(response)

        except Exception:

            return {
                "root_cause": "Unable to parse response",
                "suggested_fix": response,
                "confidence": 0,
                "raw_response": response
            }