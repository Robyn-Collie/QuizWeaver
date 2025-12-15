# Implementation Plan - Phase 3: Vertex AI Integration & Agnosticism Refactor

[Overview]
This phase focuses on refactoring the LLM interaction layer to be provider-agnostic and implementing support for Google Cloud Vertex AI. The goal is to remove hard dependencies on `google.generativeai` within the agent logic and allow users to choose between Google AI Studio (API Key) and Vertex AI (Enterprise/Cloud Identity) via configuration. This enhances the system's flexibility and enterprise readiness.

[Types]
- No new database types, but `LLMProvider` interface is extended.
- `prepare_image_context`: New abstract method in `LLMProvider`.

[Files]
- `requirements.txt`: Add `google-cloud-aiplatform`.
- `config.yaml`: Add `vertex_project_id`, `vertex_location` to `llm` section.
- `src/llm_provider.py`:
    - Update `LLMProvider` interface.
    - Implement `VertexAIProvider`.
    - Update `GeminiProvider` to implement new interface methods.
    - Update `get_provider` factory.
- `src/agents.py`: Remove `google.generativeai` import; use provider abstraction for image handling.
- `README.md`: Update with Vertex AI setup instructions.

[Functions]
- `src/llm_provider.py`:
    - `LLMProvider.prepare_image_context`: Abstract method.
    - `VertexAIProvider.__init__`: Initialize Vertex AI client.
    - `VertexAIProvider.generate`: Handle Vertex AI generation logic.
    - `VertexAIProvider.prepare_image_context`: Convert images to Vertex `Part` objects.
    - `get_provider`: Logic to instantiate `VertexAIProvider`.
- `src/agents.py`:
    - `generate_questions`: Use `provider.prepare_image_context` instead of `genai.upload_file`.

[Classes]
- `VertexAIProvider`: New concrete implementation of `LLMProvider`.

[Dependencies]
- `google-cloud-aiplatform`: Required for Vertex AI support.

[Implementation Order]
1.  **Update Dependencies**: Add `google-cloud-aiplatform` to `requirements.txt`. (Completed)
2.  **Update Configuration**: Add Vertex AI fields to `config.yaml`. (Completed)
3.  **Refactor Provider Interface**: Update `LLMProvider` and existing Gemini implementations. (Completed)
4.  **Implement Vertex Provider**: Add `VertexAIProvider` class. (Completed)
5.  **Refactor Agents**: Decouple `src/agents.py` from `google.generativeai`. (Completed)
6.  **Update Documentation**: Update `README.md` and this plan. (Completed)
7.  **Verification**: Verify the system runs with the new configuration options. (Next Step)
