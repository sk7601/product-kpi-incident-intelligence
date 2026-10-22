# Verification evidence — 2026-10-22

- Published code CI [39723593324](https://github.com/sk7601/product-kpi-incident-intelligence/actions/runs/39723593324)
  passed: **48 tests, 98.36% core coverage**, three PostgreSQL integration cases,
  migration upgrade/downgrade and Docker Compose build/start/application health smoke.
- Windows, Python 3.13.5; NumPy 2.3.5, Pandas 2.3.3, SQLAlchemy 2.1.6.
- Full local suite before final validation additions: **46 passed**, including eight UI tests.
- Final isolated core/pipeline suite after additions: **39 passed; 98.03% core coverage**.
  Analytics98%, detection100%, investigation100%, reporting95%, validation99%.
  Coverage denominator includes these five modules only. ORM/pipeline/UI have separate checks.
- Nine final test cases outside that core run: schema test plus eight dashboard/control tests,
  previously passing. CI runs all 48 together on the published commit.
- Ruff lint, Ruff formatting, git whitespace and Compose configuration checks pass.
- Seed42: **36,723 accepted records, zero rejections**. Reproducibility, duplicate rejection,
  batch idempotency, replacement and failure-audit behaviors tested.
- PostgreSQL17.11: upgrade → downgrade → upgrade succeeds; sample loads; **3 integration tests pass**.
- Streamlit starts on localhost:8502; `/_stcore/health` returns `ok`.
- Six dashboard sections, empty/segment filters, metric/endpoint/method/severity controls pass AppTest.
- API contract tested with HTTP mocks: valid selection, invented IDs, malformed JSON, extra keys,
  rate limits, deterministic fallback and credential-safe logging. **Live API not tested**:
  OPENAI_API_KEY is absent. API credentials are optional; core reporting fully works without them.
- No tracked secret-pattern findings, local databases or .env files.
- Local Docker startup blocked by missing WSL. GitHub CI includes Compose build/start/health checks;
  the successful run above verifies Compose runtime on Ubuntu.
- Non-failing importlib metadata deprecation warnings occur in Windows UI tests; not suppressed.

## Measured synthetic detector comparison

Reproduce after loading seed42: `python scripts/evaluate.py`.

| Method | Precision | Recall | False positives | Evaluated days | Incident days |
|---|---:|---:|---:|---:|---:|
| Z-score | 1.000 | 0.286 | 0 | 76 | 7 |
| MAD | 0.700 | 1.000 | 3 | 76 | 7 |
| Isolation Forest | 0.875 | 1.000 | 1 | 60 | 7 |

These use all-endpoint daily error rates and persisted synthetic labels. The Forest also uses
mean latency. Eligibility differs with warm-up. Z-score catches onset but adapts to a sustained
incident. Results are not real operational accuracy or a held-out-seed benchmark.
