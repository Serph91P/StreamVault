# Copilot Instructions

This directory contains path-specific instructions for GitHub Copilot to provide context-aware code suggestions and assistance.

## Files

- **`frontend.instructions.md`** - Vue 3, TypeScript, SCSS guidelines for PWA development
- **`backend.instructions.md`** - Python, FastAPI, SQLAlchemy patterns and best practices
- **`api.instructions.md`** - REST API endpoint design and error handling
- **`migrations.instructions.md`** - Database migration patterns and conventions
- **`docker.instructions.md`** - Docker and docker-compose configuration

## Usage

These instructions are automatically loaded by GitHub Copilot based on the file you're editing. They provide:

- Code patterns and best practices
- Common pitfalls to avoid
- Repository-specific conventions
- Examples of correct vs incorrect implementations

## Modifying Instructions

When updating instructions:

1. Keep them concise and actionable
2. Use examples with ✅ CORRECT and ❌ WRONG patterns
3. Focus on repository-specific conventions, not general programming advice
4. Update the `applyTo` glob pattern if file structure changes
