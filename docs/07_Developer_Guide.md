# 07 Developer Guide

## Layer Rules

UI → Service → Repository → Google Sheet

Do not access Google Sheet directly from UI.

## Naming

- services/*_service.py
- repositories/*_repository.py
- api/routers/*.py

## Coding Style

- Type hints
- Small functions
- Single responsibility
- Dependency injection for FastAPI

## Version Strategy

Foundation
→ Service Layer
→ API Layer
→ Repository Layer
→ LINE
→ Diagnostics
