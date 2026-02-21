# Tensr Signal Agent

Signal intelligence pipeline for scouting and scoring AI transformation signals, with a FastAPI backend and React dashboard.

## Repository Structure

```
tensr-signal-agent/
├── signal_pipeline_backend/         # Backend Python package (core app logic)
│   ├── database.py
│   ├── debug.py
│   ├── orchestrator.py
│   ├── server.py
│   ├── signal_scorer.py
│   └── signal_scout.py
├── dashboard/                  # React + Vite frontend
├── config/                     # Agent/task YAML configs
├── data/                       # SQLite DB files
├── outputs/                    # Generated pipeline artifacts
├── docs/                       # Project docs and logs
└── requirements.txt            # Python dependencies
```

## Run Backend

```bash
./venv/bin/python -m uvicorn signal_pipeline_backend.server:app --reload --port 8000
```

## Run Full Pipeline

```bash
./venv/bin/python -m signal_pipeline_backend.orchestrator
```

## Run Dashboard

```bash
cd dashboard
npm run start
```
