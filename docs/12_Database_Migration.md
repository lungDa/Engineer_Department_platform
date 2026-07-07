# 12 Database Migration

## Current

Google Sheet

## Future

PostgreSQL

## Strategy

Repository Pattern allows replacing the storage backend without modifying
Service Layer or UI.

Target Flow

UI
  ↓
Service
  ↓
Repository
  ↓
PostgreSQL
