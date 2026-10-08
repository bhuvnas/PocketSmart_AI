# PocketSmart AI — Complete project

A responsive FastAPI + HTML/CSS/JS budgeting app based on the PocketSmart AI project document. Includes registered users, password hashing, signed sessions, SQLite history, home/party/jewelry planners, optional Gemini image analysis for jewelry, budget enforcement and offline demo estimates.

## One-click Windows setup

1. Install **Python 3.10 or later** from https://www.python.org/downloads/ and select **Add Python to PATH**.
2. Extract the ZIP. Open the extracted **PocketSmartAI_Complete** folder.
3. Double-click **RUN_WINDOWS.bat**. The first run installs libraries and needs internet access.
4. Open http://127.0.0.1:8000 (normally opens automatically).
5. Register a user, choose a planner, generate recommendations and check History.

**Important:** Do not run the `.bat` while it is inside the ZIP. Extract everything first. Leave the terminal open while using the app.

## Gemini AI integration

By default the app is in **demo mode** so it works without any API credentials. To enable real Gemini calls:

1. Visit https://aistudio.google.com/apikey and create your API key.
2. Open `.env` in VS Code (created automatically by the launcher, or copy `.env.example` to `.env`).
3. Fill `GEMINI_API_KEY=your_actual_key_here` and optionally choose a model with `GEMINI_MODEL=gemini-2.5-flash`. Model availability depends on the account; check AI Studio for the models enabled for your key.
4. Restart RUN_WINDOWS.bat. Real Gemini recommendations are labelled **Gemini AI**. If the API is unavailable or the key is invalid, it explicitly falls back to **Demo estimates**.

The document refers to the older Gemini 1.5 Flash Pro naming and mixes Flask/FastAPI. This implementation uses **FastAPI**, consistent with the detailed backend milestones and routing screenshots. It uses Google's HTTPS generateContent API directly, avoiding the deprecated `google.generativeai` library. External merchant URLs are search links only, **not** live inventory API integrations, and prices are estimated.

## VS Code setup (manual)

Open folder in VS Code, then Terminal > New Terminal. Windows PowerShell:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env   # only if .env does not already exist
.\.venv\Scripts\python.exe app.py
```

On macOS/Linux:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
cp .env.example .env
.venv/bin/python app.py
```

Run `http://127.0.0.1:8000`. Swagger API docs: http://127.0.0.1:8000/docs. Health: http://127.0.0.1:8000/health.

## Suggested end-to-end tests

- Register, log out, then log back in.
- Home planner: ₹30,000, 4 lights, 2 fans, 2 furniture pieces.
- Party planner: ₹50,000 for 50 birthday guests.
- Jewelry planner: ₹10,000, Wedding, Traditional, optionally upload a JPG/PNG/WEBP image under 5 MB.
- Verify item costs never exceed budget; click shopping links, review /history, confirm that other users cannot see your records.
- Automated tests: `python -m pytest -q` (inside the environment).

## Folder structure

```
PocketSmartAI_Complete/
├── app.py                  # FastAPI, login, registration, planners, history
├── services/planner.py     # Gemini API, normalization, shopping links, offline mode
├── templates/              # Responsive Jinja2 HTML pages
├── static/style.css        # Modern responsive styles
├── tests/test_app.py       # Automated tests
├── data/                   # Local SQLite DB created on first run
├── .env.example            # Safe config template
├── requirements.txt
├── RUN_WINDOWS.bat
└── README.md
```

## Safety / deployment notes

Run locally for college demos. For production: set a long random SECRET_KEY, enforce HTTPS/secure cookies, use a database-backed rate limiter, CSRF protection for forms, user/password recovery, secrets management, and a managed production server. Never commit `.env`. User uploads are read into memory and not saved. The Gemini API requires an internet connection and may have usage costs or rate limits.
