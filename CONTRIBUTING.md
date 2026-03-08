# Contributing to Angola News Pipeline

Thank you for your interest in contributing! This document provides guidelines for contributing to the project.

## Getting Started

1. **Fork the repository** on GitHub
2. **Clone your fork** locally:
   ```bash
   git clone https://github.com/YOUR_USERNAME/angola-news-pipeline.git
   cd angola-news-pipeline
   ```

3. **Create a branch** for your work:
   ```bash
   git checkout -b feature/your-feature-name
   # or
   git checkout -b fix/your-bug-fix
   ```

4. **Set up development environment**:
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   pip install -r requirements.txt
   npm install -g agent-browser
   ```

5. **Create `.env` from `.env.example`** and add your API keys

## Making Changes

### Code Style

- Follow PEP 8 for Python code
- Use 4 spaces for indentation
- Add docstrings for functions and modules
- Keep lines under 100 characters when possible

### Testing Changes

Before submitting:

1. **Test the full pipeline**:
   ```bash
   bash RUN_ALL.sh
   ```

2. **Test individual scripts**:
   ```bash
   python3 scripts/01-fetch-headlines.py
   python3 scripts/02-extract-final.py data/
   python3 scripts/03-score-ai.py data/
   python3 scripts/06-translate-agent.py data/
   ```

3. **Verify no credentials are exposed**:
   ```bash
   git diff --cached  # Check staged changes
   git status        # Check working directory
   ```

## Types of Contributions

### Adding a New News Source

1. Edit `config.json` and add new source to `sources` array:
   ```json
   {
     "name": "Source Name",
     "url": "https://example.com",
     "fetch_mode": "curl",
     "patterns": [...]
   }
   ```

2. Update the regex patterns based on HTML structure
3. Test extraction: `python3 scripts/02-extract-final.py data/`
4. Document the change in your PR description

### Adding an AI Scoring Provider

1. Edit `config.json` and add to `scoring.providers` array:
   ```json
   {
     "name": "provider-name",
     "enabled": true,
     "type": "openai-compat",  // or "anthropic" or "keyword"
     "base_url": "https://api.example.com/v1/",
     "model": "model-name",
     "api_key_env": "API_KEY_ENV_VAR"
   }
   ```

2. Add API key to `.env.example` and documentation
3. Test scoring: `python3 scripts/03-score-ai.py --list` (to see providers)
4. Run full pipeline to verify

### Bug Fixes

1. Create an issue describing the bug (if not already reported)
2. Create a branch: `git checkout -b fix/issue-description`
3. Make minimal changes to fix the issue
4. Test thoroughly
5. Submit a PR with detailed description

### Documentation

- Update `README.md` for user-facing changes
- Update `CLAUDE.md` for architecture/design changes
- Add docstrings for new functions

## Submitting Changes

### Commit Messages

Write clear, concise commit messages:

```
Short description (50 chars max)

More detailed explanation if needed.
- Explain the "why", not just the "what"
- Reference issues: Fixes #123
- Keep lines under 72 characters
```

Examples:
```
Add Reuters news source with Portuguese scraping

Adds Reuters as a new news source with custom regex patterns
for Portuguese news section. Handles pagination and article links.

Fixes #15
```

```
Fix translation API timeout handling

Increase timeout from 20s to 30s and add exponential backoff
for 502/522 errors. Maintains batch size of 5 for reliability.
```

### Pull Request Process

1. **Update documentation** if needed
2. **Test thoroughly** - Run full pipeline and verify outputs
3. **Push to your fork**:
   ```bash
   git push origin feature/your-feature-name
   ```

4. **Create a Pull Request** on GitHub with:
   - Clear title summarizing the change
   - Description of what changed and why
   - Link to related issues (e.g., "Fixes #123")
   - Screenshot/output if applicable

5. **Respond to feedback** promptly
6. **Keep branch up to date** with main:
   ```bash
   git fetch upstream
   git rebase upstream/main
   ```

## Review Process

PRs are reviewed for:
- ✅ Correctness - Does it work as intended?
- ✅ Testing - Is it properly tested?
- ✅ Documentation - Are changes documented?
- ✅ Code quality - Does it follow project style?
- ✅ Security - Are secrets/credentials protected?

## Common Issues

### "API quota exceeded"
- Check your API usage in provider dashboard
- Wait for quota reset
- Consider using alternative providers in `config.json`

### "Browser timeout"
- Set `AGENT_BROWSER_DEFAULT_TIMEOUT=60000`
- Check if website is blocking requests
- Consider using `fetch_mode: curl` instead

### "Translation failures"
- Check uapis.cn availability
- Adjust `BATCH_SIZE` in `06-translate-agent.py`
- Verify internet connection

## Questions?

- Open an issue for bugs
- Use Discussions for questions
- Check existing issues and documentation first

## Code of Conduct

Be respectful and constructive. We welcome contributions from people of all backgrounds and experience levels.

---

Thank you for contributing to Angola News Pipeline! 🇦🇴 📰
