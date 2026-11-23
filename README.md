# Stargo RevOps take-home

Draft. Setup, architecture and usage sections are written in Phase 9.

## Deviations from the plan

- **LLM model.** The plan named Groq `llama-3.3-70b-versatile`. Groq no longer serves it
  (HTTP 404, "model does not exist"), so the app uses Groq `openai/gpt-oss-120b`. The
  provider choice (Groq, decision Q11) is unchanged. Set with `LLM_MODEL` in `.env`.
