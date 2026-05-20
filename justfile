set shell := ["powershell.exe", "-Command"]

run:
    uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload

seed:
    python -m app.seed

frontend:
    python -m http.server 3000 --directory frontend