# Project Structure Details

## Backend Package

- `signal_pipeline_backend/server.py`: FastAPI API and pipeline orchestration endpoints.
- `signal_pipeline_backend/orchestrator.py`: CLI pipeline coordinator (scout -> scorer).
- `signal_pipeline_backend/signal_scout.py`: Signal discovery and filtering workflow.
- `signal_pipeline_backend/signal_scorer.py`: Signal scoring workflow and ranking.
- `signal_pipeline_backend/database.py`: SQLite schema and persistence helpers.
- `signal_pipeline_backend/pipeline_profile.py`: Profile schema, validation, save/load.
- `signal_pipeline_backend/briefing_agent.py`: Briefing/persona prompt orchestration.
- `signal_pipeline_backend/debug.py`: Terminal diagnostics for latest run data.

## Data and Runtime Artifacts

- `config/`: YAML task/agent configuration.
- `data/`: SQLite database files.
- `outputs/`: Generated reports and saved profiles/personas.
- `docs/`: Human-facing docs and long-form logs.

## Frontend

- `dashboard/`: React + Vite dashboard that consumes the backend API.
