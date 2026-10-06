<!-- English or Spanish are both fine. Read CONTRIBUTING.md first. Target branch: staging. -->

### What changed

<!-- What this pull request does and why. Link the issue: "Closes #123". -->

### API contract

<!-- Delete this section if no route, field, status code or permission changed. Otherwise:
what changed, and what a client built on this base has to do. -->

### How it was checked

- [ ] `uv run black --check .`
- [ ] `uv run python manage.py makemigrations --check --dry-run`
- [ ] `uv run python manage.py test`
- [ ] Tests added or updated (a fix comes with a test that fails without it)
- [ ] `requirements*.txt` regenerated, if a dependency changed
- [ ] `.env.example` and the README variables table updated, if a setting was added
- [ ] Docs updated in English and Spanish

### Notes for the reviewer

<!-- Trade-offs, anything worth a closer look. -->
