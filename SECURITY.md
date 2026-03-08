# Security Policy

## Handling Sensitive Information

This project handles sensitive information including API keys and database records. Please follow these guidelines:

### API Keys and Secrets

- **Never commit `.env` files** - Use `.env.example` as template
- **Use GitHub Secrets** for automated runs via GitHub Actions
- **Rotate API keys regularly** if exposed
- All API keys should have minimal required permissions

### Database Files

The following files contain persistent data and should be protected:
- `data/articles-db.json` - Central article database (safe to commit)
- `data/sent-history.json` - Push history (safe to commit)
- `data/runs/` - Temporary run data (excluded by `.gitignore`)

### Telegram Configuration

If using Telegram push notifications:
- Store `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` in GitHub Secrets
- Never commit these credentials to version control
- Use a dedicated bot token (not your personal account token)

## Best Practices

### Local Development

1. Copy `.env.example` to `.env`
2. Fill in your own API keys in `.env`
3. Ensure `.gitignore` is properly configured
4. Never commit `.env` or sensitive files
5. Verify with `git status` before committing

```bash
cp .env.example .env
# Edit .env with your credentials
echo ".env" >> .gitignore  # Already done, but verify
git status  # Check no sensitive files are staged
```

### GitHub Actions

1. Add secrets in Settings → Secrets and variables → Actions
2. Use `${{ secrets.KEY_NAME }}` in workflow files
3. Never hardcode credentials in workflow files
4. Keep secret names consistent with `.env` variable names

Required Secrets:
- `GEMINI_API_KEY` - Google Gemini API key
- `ZHIPU_API_KEY` - GLM/Zhipu API key
- `ANTHROPIC_AUTH_TOKEN` - Anthropic/Claude API key
- `TELEGRAM_BOT_TOKEN` - (Optional) Telegram bot token
- `TELEGRAM_CHAT_ID` - (Optional) Telegram chat ID

### Credential Monitoring

If you suspect credentials have been exposed:

1. **Immediately revoke** the exposed key in the API provider's dashboard
2. **Generate a new key**
3. **Update GitHub Secrets** with the new key
4. **Check git history** to ensure the key isn't in commits

To search git history for potential credential leaks:
```bash
# Search for common patterns
git log --all -S "ZHIPU_API_KEY" --oneline
git log --all -S "GEMINI_API_KEY" --oneline
git log --all -S "ANTHROPIC_AUTH_TOKEN" --oneline
```

## Data Privacy

- The project only stores article metadata (title, URL, score, translation)
- No personal user data is collected
- Database files contain no personally identifiable information
- Web scraping follows website terms of service (news sites typically allow automated access)

## Reporting Security Issues

If you discover a security vulnerability:

1. **Do not open a public GitHub issue**
2. **Email security details privately** to the project maintainer
3. Include:
   - Description of the vulnerability
   - Steps to reproduce (if applicable)
   - Potential impact
   - Suggested fix (if you have one)

We will:
- Acknowledge receipt within 48 hours
- Investigate the issue
- Release a fix and update dependencies as needed
- Credit you in security advisory (if desired)

## Dependencies Security

- Regularly update dependencies: `pip install --upgrade -r requirements.txt`
- Check for known vulnerabilities: `pip-audit`
- Pin versions in `requirements.txt` to ensure consistency across environments

## Compliance

This project respects:
- Website terms of service for web scraping
- API provider rate limits and terms
- Local laws regarding web content aggregation
- Data retention requirements (auto-cleanup after 30 days)
