# Contributing to StreamVault

Thank you for your interest in contributing to StreamVault! This document provides guidelines and information for contributors.

## 📋 Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
- [Development Setup](#development-setup)
- [Making Changes](#making-changes)
- [Submitting Changes](#submitting-changes)
- [Code Style](#code-style)
- [Testing](#testing)
- [Documentation](#documentation)

## 🤝 Code of Conduct

By participating in this project, you agree to maintain a respectful and inclusive environment for everyone. Please be kind, considerate, and constructive in all interactions.

## 🚀 Getting Started

### Prerequisites

- Python 3.12+
- Node.js 18+
- Docker and Docker Compose
- Git

### Fork and Clone

1. Fork the repository on GitHub
2. Clone your fork locally:
```bash
git clone https://github.com/yourusername/StreamVault.git
cd StreamVault
```

## 🛠️ Development Setup

### Backend Setup

1. **Create a virtual environment**:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

2. **Install dependencies**:
```bash
pip install -r requirements.txt
```

3. **Set up environment variables**:
```bash
cp .env.example .env
# Edit .env with your configuration
```

4. **Start database**:
```bash
docker-compose up -d db
```

5. **Run migrations**:
```bash
python -m app.migrations_init
```

6. **Start development server**:
```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Frontend Setup

1. **Navigate to frontend directory**:
```bash
cd app/frontend
```

2. **Install dependencies**:
```bash
npm install
```

3. **Start development server**:
```bash
npm run dev
```

## 🔄 Making Changes

### Branch Naming

Use descriptive branch names:
- `feature/add-youtube-support`
- `bugfix/fix-audio-sync`
- `docs/update-api-reference`
- `refactor/improve-error-handling`

### Commit Messages

Follow conventional commit format:
```
type(scope): description

[optional body]

[optional footer]
```

Examples:
- `feat(api): add YouTube platform support`
- `fix(recording): resolve audio sync issues with proxy`
- `docs(readme): update installation instructions`
- `refactor(frontend): simplify video player component`

## 📤 Submitting Changes

### Pull Request Process

1. **Create a feature branch**:
```bash
git checkout -b feature/your-feature-name
```

2. **Make your changes** following the code style guidelines

3. **Test your changes** thoroughly

4. **Commit your changes**:
```bash
git add .
git commit -m "feat: add your feature description"
```

5. **Push to your fork**:
```bash
git push origin feature/your-feature-name
```

6. **Create a Pull Request** on GitHub

### Pull Request Guidelines

- **Clear Title**: Use a descriptive title
- **Detailed Description**: Explain what changes you made and why
- **Link Issues**: Reference any related issues
- **Screenshots**: Include screenshots for UI changes
- **Testing**: Describe how you tested your changes

## 🎨 Code Style

### Python (Backend)

- Follow **PEP 8** style guidelines
- Use **Black** for code formatting
- Use **isort** for import sorting
- Maximum line length: 88 characters

```bash
# Format code
black app/
isort app/

# Check style
flake8 app/
```

### JavaScript/Vue.js (Frontend)

- Follow **ESLint** configuration
- Use **Prettier** for code formatting
- Use **TypeScript** where possible

```bash
# Format code
npm run format

# Check style
npm run lint
```

### General Guidelines

- **Clear variable names**: Use descriptive names
- **Comments**: Add comments for complex logic
- **Error handling**: Always handle errors gracefully
- **Type hints**: Use type hints in Python code
- **Documentation**: Update documentation for new features

## 🧪 Testing

### Backend Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=app

# Run specific test file
pytest tests/test_recording_service.py
```

### Frontend Tests

```bash
cd app/frontend

# Run unit tests
npm run test

# Run e2e tests
npm run test:e2e
```

### Integration Tests

```bash
# Start test environment
docker-compose -f docker-compose.test.yml up -d

# Run integration tests
pytest tests/integration/
```

## 📚 Documentation

### API Documentation

- API documentation is auto-generated from FastAPI schemas
- Update docstrings and type hints for new endpoints
- Test API endpoints in the interactive docs at `/docs`

### User Documentation

- Update relevant sections in `README.md`
- Add new configuration options to the documentation
- Include examples for new features

### Code Documentation

- Add docstrings to all functions and classes
- Include parameter descriptions and return types
- Provide usage examples for complex functions

## 🐛 Reporting Issues

### Bug Reports

Include the following information:
- **Environment**: OS, Python version, Docker version
- **Steps to reproduce**: Clear step-by-step instructions
- **Expected behavior**: What should happen
- **Actual behavior**: What actually happens
- **Logs**: Relevant log output
- **Screenshots**: If applicable

### Feature Requests

Include the following information:
- **Use case**: Why is this feature needed?
- **Proposed solution**: How should it work?
- **Alternatives**: Any alternative solutions considered?
- **Additional context**: Any other relevant information

## 🏷️ Labels

We use the following labels for issues and PRs:

- `bug`: Something isn't working
- `enhancement`: New feature or request
- `documentation`: Documentation improvements
- `good first issue`: Good for newcomers
- `help wanted`: Extra attention is needed
- `question`: Further information is requested
- `wontfix`: This will not be worked on

## 🎯 Areas for Contribution

We welcome contributions in these areas:

### High Priority
- **Bug fixes**: Always appreciated!
- **Documentation**: Improve existing docs or add new ones
- **Testing**: Add tests for uncovered code
- **Performance**: Optimize slow operations

### New Features
- **Multi-platform support**: YouTube, Facebook Gaming, etc.
- **Cloud storage**: S3, Google Drive integration
- **Mobile apps**: React Native or Flutter
- **Analytics**: Recording statistics and insights

### Infrastructure
- **CI/CD**: Improve GitHub Actions workflows
- **Docker**: Optimize container images
- **Monitoring**: Add health checks and metrics
- **Security**: Security audits and improvements

## 📞 Getting Help

If you need help contributing:

1. **Check existing documentation** first
2. **Search existing issues** for similar questions
3. **Create a new issue** with the `question` label
4. **Join discussions** in GitHub Discussions

## 🙏 Recognition

Contributors will be recognized in:
- `README.md` contributors section
- Release notes for significant contributions
- GitHub contributors page

Thank you for contributing to StreamVault! 🎉
