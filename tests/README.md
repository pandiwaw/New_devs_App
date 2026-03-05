# Test Suite — PropertyFlow Revenue Dashboard

Two levels of testing: **unit tests** (pytest) and **integration tests** (Bruno). Both live inside `docker-compose.yml` under the `test` profile — they only run when you ask for them.

## Quick Start

```bash
# Start the app normally (tests do NOT run)
docker compose up --build

# Run unit tests (no running app needed)
make test-unit

# Run Bruno integration tests (app must be running)
docker compose up -d --build
make test-integration

# Run all tests
make test
```

Or directly with docker compose:

```bash
docker compose --profile test run --rm unit-tests
docker compose --profile test run --rm bruno-tests
```

---

## Unit Tests (`tests/unit/`)

Pure Python tests that verify the three bug fixes at the logic level — no database, no Redis, no running app.

```
tests/unit/
├── conftest.py                              # Seed data mirroring database/seed.sql
├── test_cache_key_isolation.py              # Bug 1: Cross-tenant cache key collision
├── test_timezone_monthly_revenue.py         # Bug 2: Timezone-naive month boundaries
└── test_decimal_precision.py                # Bug 3: Float precision loss in revenue
```

### What each test file proves

**test_cache_key_isolation.py** (Bug 1) — Simulates a cache dict and proves:
- Fixed key `revenue:{tenant_id}:{property_id}` is unique per tenant
- Buggy key `revenue:{property_id}` causes tenant-b to see tenant-a's data

**test_timezone_monthly_revenue.py** (Bug 2) — The most important test file:
- `res-tz-1` check_in = Feb 29 23:30 UTC = Mar 1 00:30 in Europe/Paris
- Fixed logic: 4 reservations in March, total = $2,250 (correct)
- Buggy logic: 3 reservations in March, total = $1,000 (missing $1,250)
- Proves the exact $1,250 discrepancy Client A reported
- Also tests DST transitions and year boundaries

**test_decimal_precision.py** (Bug 3) — Proves:
- `Decimal.quantize(0.01, ROUND_HALF_UP)` prevents float artifacts
- Seed values like 333.333 + 333.333 + 333.334 sum correctly
- Direct `float()` conversion can introduce IEEE 754 drift

### Run manually (without Docker)

```bash
pip install pytest pytz
pytest tests/unit/ -v
```

---

## Bruno Integration Tests

API-level tests that hit the running application end-to-end.

```
tests/
├── bruno.json                 # Collection config
├── environments/
│   ├── local.bru              # For running Bruno locally (localhost:8000)
│   └── docker.bru             # For running Bruno inside Docker (backend:8000)
├── auth/                      # Authentication & authorization (6 tests)
├── tenant_isolation/          # Cross-tenant data leakage — Bug 1 (6 tests)
├── revenue_accuracy/          # Revenue precision & correctness — Bug 2 & 3 (9 tests)
│   └── 09_timezone_edge_case_res_tz1.bru  ← proves Bug 2 fix
├── caching/                   # Cache behavior & tenant-scoped caching (6 tests)
└── health/                    # Infrastructure & health endpoints (5 tests)
```

### Key test: `09_timezone_edge_case_res_tz1.bru`

This test specifically targets Bug 2. It queries prop-001 (Europe/Paris timezone) and asserts:
- `total_revenue == 2250.0` — proving res-tz-1 ($1,250) IS included
- `total_revenue != 1000.0` — if this were true, the timezone bug would still be present
- `reservations_count == 4` (not 3) — all four reservations are counted

### Run manually (without Docker)

```bash
npm install -g @usebruno/cli
docker-compose up --build          # start app
bru run tests/ --env local         # run all suites
```
