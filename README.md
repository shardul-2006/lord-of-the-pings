# RAG-Shield

Provenance-aware trust layer for document RAG. Work in progress, built phase by phase per
`docs/RAG_SHIELD_CLAUDE_CODE_PLAN.md`. Product description: `docs/RAG_SHIELD_PRODUCT_OVERVIEW.md`.

```bash
python -m venv .venv && source .venv/Scripts/activate   # Windows Git Bash
pip install -e ".[dev]"
bash scripts/verify_phase.sh 8
```

## Run the demo
```bash
python scripts/make_fixtures.py                 # sample documents
streamlit run app/streamlit_app.py              # UI
pip install uvicorn && uvicorn app.api:create_app --factory --port 8000   # REST API
```

## Real LLM (optional)
Tests always use the deterministic `MockLLM`. For a real model the prototype uses a local
Llama 3.1 8B through Ollama (no API key; documents stay on the machine):
```bash
ollama pull llama3.1:8b
export RAG_SHIELD_LLM=ollama RAG_SHIELD_LLM_MODEL=llama3.1:8b
python -m rag_shield.cli compare data/fixtures/smoke_poisoned.pdf --llm real
```
The model's content digest is recorded in every trace. OpenAI-compatible APIs are also
supported (`RAG_SHIELD_LLM=openai`, `OPENAI_API_KEY`).
