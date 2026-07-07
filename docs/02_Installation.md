# 02 Installation

## Requirements

- Python 3.11+
- Git
- Google Service Account
- Render account
- LINE Developers account (optional)

## Install

```bash
git clone <repo>
cd Engineer_Department_platform
pip install -r requirements.txt
```

Run UI

```bash
streamlit run app.py
```

Run API

```bash
uvicorn api.main:app --reload
```
