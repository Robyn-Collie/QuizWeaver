# QuizWeaver Cost Control Strategy

## Overview

QuizWeaver is designed to minimize API costs during development while supporting real LLM providers for production use.

## MockLLMProvider (Default)

The default provider is `mock`, which:
- Makes zero API calls (no cost)
- Returns fabricated but realistic responses
- Supports all agent operations (Analyst, Generator, Critic)
- Is configured in `config.yaml`: `llm.provider: "mock"`

**Always use mock mode during development and testing.**

## Switching to Real Providers

### Step 1: Set Environment Variables

```bash
# For Gemini
export GEMINI_API_KEY="your-api-key"

# For Vertex AI (uses service account)
export GOOGLE_APPLICATION_CREDENTIALS="path/to/service-account.json"
```

### Step 2: Update config.yaml

```yaml
llm:
  provider: "gemini"  # or "vertex"
  model_name: "gemini-2.5-flash"
  vertex_project_id: "your-project-id"
  vertex_location: "us-central1"
```

### Step 3: Approval Gate

When using a real provider in development mode, QuizWeaver will prompt:

```
WARNING: Using real API - costs will be incurred!
Provider: gemini
Continue with real API? (yes/no):
```

You must type "yes" to proceed. Any other input falls back to mock.

## Cost Tracking

All real API calls are logged to `api_costs.log`:

```
2026-02-06T10:30:00 | gemini | gemini-2.5-flash | 1500 | 800 | $0.000705
```

View cost summary:
```bash
python main.py cost-summary
```

## Rate Limits

Configure in `config.yaml`:
```yaml
llm:
  max_calls_per_session: 50    # Max API calls before stopping
  max_cost_per_session: 5.00   # Max dollars before stopping
```

## Cost Estimates

| Operation | Model | Est. Input | Est. Output | Est. Cost |
|-----------|-------|-----------|-------------|-----------|
| Quiz Generation (1 attempt) | gemini-2.5-flash | ~2,000 tokens | ~1,500 tokens | ~$0.001 |
| Critic Review | gemini-2.5-flash | ~3,000 tokens | ~200 tokens | ~$0.001 |
| Full Pipeline (3 attempts) | gemini-2.5-flash | ~15,000 tokens | ~5,000 tokens | ~$0.005 |

For a typical workshop session generating 5 quizzes: **~$0.025**

## Recommendations

1. Use mock mode for all development and testing
2. Only switch to real providers for final quality validation
3. Set conservative rate limits for workshops
4. Monitor costs with `python main.py cost-summary`
5. Keep `llm.mode: "development"` to maintain the approval gate
