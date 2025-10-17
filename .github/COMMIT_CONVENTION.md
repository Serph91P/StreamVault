# Commit Convention für StreamVault

StreamVault verwendet [Conventional Commits](https://www.conventionalcommits.org/) für **automatisches Versioning**.

## 📋 Format

```
<type>[optional scope]: <description>

[optional body]

[optional footer(s)]
```

## 🔢 Version Bumps

### 🚨 Major Version (1.x.x → 2.0.0)
**Breaking Changes** - Inkompatible API-Änderungen

```bash
git commit -m "feat!: remove support for Python 3.10

BREAKING CHANGE: Minimum Python version is now 3.11"
```

oder:

```bash
git commit -m "BREAKING CHANGE: change database schema"
```

### ✨ Minor Version (1.0.x → 1.1.0)
**Neue Features** - Neue Funktionalität, abwärtskompatibel

```bash
git commit -m "feat: add support for YouTube recordings"
git commit -m "feature: implement automatic backup system"
git commit -m "add: new thumbnail generation service"
git commit -m "refactor: improve recording lifecycle"
git commit -m "perf: optimize database queries with indexes"
```

### 🐛 Patch Version (1.0.0 → 1.0.1)
**Bug Fixes & Minor Changes** - Bugfixes, Dokumentation, Chores

```bash
git commit -m "fix: resolve memory leak in notification manager"
git commit -m "bugfix: correct stream detection logic"
git commit -m "docs: update installation guide"
git commit -m "chore: update dependencies"
git commit -m "style: format code with black"
```

## 📝 Commit Types

| Type | Version Bump | Beschreibung | Beispiel |
|------|--------------|--------------|----------|
| `feat:` | **Minor** 🟡 | Neue Feature | `feat: add stream quality selection` |
| `feature:` | **Minor** 🟡 | Neue Feature (alternativ) | `feature: implement notifications` |
| `add:` | **Minor** 🟡 | Etwas hinzufügen | `add: support for multi-audio tracks` |
| `refactor:` | **Minor** 🟡 | Code-Umstrukturierung | `refactor: extract constants to config` |
| `perf:` | **Minor** 🟡 | Performance-Verbesserung | `perf: optimize N+1 queries` |
| `fix:` | Patch 🟢 | Bugfix | `fix: resolve connection timeout` |
| `bugfix:` | Patch 🟢 | Bugfix (alternativ) | `bugfix: correct file path handling` |
| `docs:` | Patch 🟢 | Dokumentation | `docs: update API documentation` |
| `chore:` | Patch 🟢 | Wartung, Dependencies | `chore: update Docker base image` |
| `style:` | Patch 🟢 | Code-Formatierung | `style: apply linting rules` |
| `test:` | Patch 🟢 | Tests hinzufügen | `test: add unit tests for streams` |
| `ci:` | Patch 🟢 | CI/CD Änderungen | `ci: optimize Docker build cache` |
| `BREAKING CHANGE:` | **MAJOR** 🔴 | Breaking Change | Siehe oben |

## 🎯 Beispiele aus diesem Projekt

### ✨ Features (Minor Bump: 1.0.102 → 1.1.0)
```bash
# Unser aktueller Commit für Code-Qualität
git commit -m "refactor: comprehensive code quality improvements

- Exception Handling: Fixed 31 bare except blocks
- N+1 Queries: Optimized 18 locations with joinedload()
- Memory Leaks: Fixed 5 leaks with TTLCache
- Magic Numbers: Centralized 30+ constants

New Dependencies: cachetools==5.5.0"
```

### 🐛 Fixes (Patch Bump: 1.0.102 → 1.0.103)
```bash
git commit -m "fix: resolve Docker entrypoint line ending issue

Fixed Windows CRLF line endings causing container startup failure"
```

### 🚨 Breaking Changes (Major Bump: 1.0.102 → 2.0.0)
```bash
git commit -m "feat!: migrate to PostgreSQL 16

BREAKING CHANGE: Minimum PostgreSQL version is now 16.0
Users must upgrade their database before updating"
```

## 🔄 Multi-Change Commits

Bei mehreren Changes in einem Commit: **Höchster Typ gewinnt**

```bash
# Wird als Minor behandelt (wegen refactor)
git commit -m "refactor: improve code quality

- fix: resolve memory leaks
- docs: update README
- chore: update dependencies"
```

## 🏷️ Scopes (Optional)

Scopes helfen bei der Organisation:

```bash
git commit -m "feat(api): add new recording endpoints"
git commit -m "fix(ui): resolve dashboard loading issue"
git commit -m "perf(db): add missing indexes"
git commit -m "docs(docker): update compose examples"
```

## 🤖 Automatische Versionierung

Nach dem Push zu `main`:

1. **GitHub Action** analysiert Commit-Messages
2. **Version wird berechnet**:
   - `BREAKING CHANGE` → Major bump
   - `feat:`, `refactor:`, `perf:` → Minor bump
   - Alles andere → Patch bump
3. **Docker Image** wird gebaut mit neuem Tag
4. **GitHub Release** wird erstellt mit Changelog

## 💡 Best Practices

### ✅ Gut
```bash
git commit -m "feat: add automatic thumbnail generation"
git commit -m "fix: resolve memory leak in notification service"
git commit -m "refactor: extract magic numbers to constants"
git commit -m "perf: optimize database queries with indexes"
```

### ❌ Vermeiden
```bash
git commit -m "update stuff"  # Zu vage, nur patch bump
git commit -m "changes"       # Keine Information
git commit -m "wip"          # Work in Progress sollte nicht zu main
```

## 📊 Aktuelle Version

Aktuell: **v1.0.102** (zu viele Patch-Bumps!)

Mit unserem **Code Quality Commit** wird es:
- `refactor: comprehensive code quality improvements` 
- → **v1.1.0** ✨

## 🔗 Links

- [Conventional Commits](https://www.conventionalcommits.org/)
- [Semantic Versioning](https://semver.org/)
- [GitHub Release Drafter](https://github.com/release-drafter/release-drafter)
