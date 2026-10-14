# CarDealersPro

> **A production-grade car dealership platform** — FastAPI + PostgreSQL + PyTorch + Docker,  (Microservices-ready, Async-first, Modular, Auditable, Auto-scalable).

[![CI/CD](https://github.com/your-org/CarDealersPro/actions/workflows/CI.yml/badge.svg)](https://github.com/your-org/CarDealersPro/actions/workflows/CI.yml)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688.svg)](https://fastapi.tiangolo.com/)
[![PyTorch](https://img.shields.io/badge/PyTorch-2.4-EE4C2C.svg)](https://pytorch.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

---

## 📖 Table of Contents

1. [What is CarDealersPro?](#-what-is-cardealerspro)
2. [High-Level Architecture](#-high-level-architecture)
3. [The End-to-End Pipeline](#-the-end-to-end-pipeline)
4. [Tech Stack](#-tech-stack)
5. [Project Structure](#-project-structure)
6. [Core Domains](#-core-domains)
7. [Machine Learning Pipeline](#-machine-learning-pipeline)
8. [Data Flow: From CSV to Frontend](#-data-flow-from-csv-to-frontend)
9. [Security Model](#-security-model)
10. [Database Design](#-database-design)
11. [API Reference](#-api-reference)
12. [Getting Started](#-getting-started)
13. [Testing](#-testing)
14. [CI/CD](#-cicd)
15. [Deployment](#-deployment)
16. [Performance & Observability](#-performance--observability)
17. [Design Decisions (Why X not Y)](#-design-decisions-why-x-not-y)
18. [Roadmap](#-roadmap)
19. [License](#-license)

---

## 🎯 What is CarDealersPro?

CarDealersPro is a **full-stack, production-grade car dealership management system** that goes beyond a typical CRUD app. It combines:

- **Inventory management** — dealers list, edit, filter, and sell cars with media uploads.
- **Finance & loans** — clients apply for loans, banks approve, disbursements are tracked, repayment schedules are auto-generated, and payments are applied using a waterfall algorithm.
- **AI-powered pricing** — a residual MLP trained on real Egyptian car market data predicts fair prices from raw features.
- **Damage inspection (planned)** — a CNN (ResNet18 backbone) will classify damage from uploaded car images.
- **Trust & ratings** — inspectors rate cars, users rate each other, with DB-level constraints preventing self-rating.
- **Multi-role RBAC** — CLIENT, DEALER, BANK, INSURANCE, INSPECTOR, ADMIN — each with its own workflows.

The system is built to **high-level standards**: async-first, layered, observable, tested, containerized, and deployed via a fully automated CI/CD pipeline.

---

## 🏗 High-Level Architecture
┌─────────────────────────────────────────────────────────────────────────┐
│ CLIENTS │
│ ┌──────────────┐ ┌──────────────┐ ┌──────────────────────┐ │
│ │ Web / SPA │ │ Mobile App │ │ Postman / cURL │ │
│ └──────┬───────┘ └──────┬───────┘ └──────────┬───────────┘ │
└─────────┼────────────────────┼───────────────────────┼──────────────────┘
│ │ │
└────────────────────┼───────────────────────┘
│ HTTPS / JSON
▼
┌─────────────────────────────────────────────────────────────────────────┐
│ EDGE (Nginx) │
│ ┌───────────────────────────────────────────────────────────────────┐ │
│ │ Rate limiting · Gzip · Real-IP (Cloudflare) · Security headers │ │
│ │ Static /media/ · Reverse proxy → FastAPI │ │
│ └──────────────────────────────────┬────────────────────────────────┘ │
└──────────────────────────────────────┼──────────────────────────────────┘
│
▼
┌─────────────────────────────────────────────────────────────────────────┐
│ APPLICATION (FastAPI + Gunicorn) │
│ │
│ ┌──────────────┐ ┌──────────────┐ ┌──────────────┐ ┌────────────┐ │
│ │ RequestID │→ │ CORS │→ │ Auth (JWT) │→ │ Routers │ │
│ │ Middleware │ │ Middleware │ │ RS256 │ │ │ │
│ └──────────────┘ └──────────────┘ └──────────────┘ └─────┬──────┘ │
│ │ │
│ ┌──────────────────────────────────────┴────┐ │
│ ▼ ▼ ▼ ▼ │
│ ┌───────────┐ ┌───────────┐ ┌───────┐ ┌────┐ │
│ │ Services │ │ ML/Infer │ │ Utils │ │Exce│ │
│ │ (business │ │ (PyTorch) │ │Filter │ │ptio│ │
│ │ logic) │ │ │ │Builder│ │ns │ │
│ └─────┬─────┘ └─────┬─────┘ └───┬───┘ └────┘ │
└───────────────────────┼────────────────────┼─────────────┼─────────────┘
│ │ │
▼ ▼ ▼
┌───────────────────────┐ ┌─────────────┐ ┌────────────┐
│ Database Layer │ │ Models │ │ Storage │
│ (3-tier engines) │ │ (.pt + │ │ (uploads) │
│ Primary | Write |Read│ │ scalers) │ │ │
└───────────┬───────────┘ └─────────────┘ └────────────┘
│
▼
┌───────────────────────┐
│ PostgreSQL 16 │
│ + Alembic migrations│
│ + ARRAY / UUID / Enums
└───────────────────────┘

text

**Key principles:**

- **Layered**: routers → services → models. Routers never touch the DB directly.
- **Async-first**: `asyncpg` + SQLAlchemy 2.0 async everywhere. No sync I/O in request paths.
- **3-tier DB access**: read-only user for GETs, write user for mutations, primary for admin/migrations. This enforces least-privilege at the database level.
- **Request tracing**: every request gets a `request_id` (contextvar) that propagates into every log line and into SQL comments.
- **ML as a service**: model loading is `lru_cache`d; inference takes a tensor, not a Pydantic model, so the ML code is HTTP-agnostic.

---

## 🔄 The End-to-End Pipeline

This is the single most important section. It explains how data moves from **raw CSV → trained model → DB → API → frontend**.
┌──────────────────────────────────────────────────────────────────────────┐
│ STAGE 1 — Data Ingestion (offline, run manually) │
├──────────────────────────────────────────────────────────────────────────┤
│ │
│ egyptian_cars.csv (Kaggle dataset, ~50k rows) │
│ │ │
│ ▼ python -m tools.ingest inspect │
│ ┌─────────────────────────────┐ │
│ │ clean_number() │ "EGP 140,000" → 140000.0 │
│ │ lowercase + strip │ "Toyota " → "toyota" │
│ │ drop rows w/o price │ │
│ └──────────────┬──────────────┘ │
│ │ │
│ ▼ python -m tools.ingest features │
│ ┌─────────────────────────────┐ │
│ │ LabelEncoder (sklearn) │ brand → brand_enc (int) │
│ │ for 5 categorical columns │ model → model_enc (int) │
│ │ │ fuel_type → fuel_type_enc(int) │
│ │ │ transmiss.→ transmission_enc │
│ │ │ body_type → body_type_enc │
│ └──────────────┬──────────────┘ │
│ │ │
│ ▼ │
│ ┌─────────────────────────────┐ │
│ │ TorchStandardScaler.fit() │ mean/std per feature (7 features) │
│ │ (pure PyTorch, no sklearn) │ │
│ └──────────────┬──────────────┘ │
│ │ │
│ ├──► data/optimized/car_features.parquet (features+price) │
│ ├──► ai_models/ai_artifacts/price_scaler.pt │
│ └──► ai_models/ai_artifacts/price_encoders.pt │
│ │
└──────────────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────────────┐
│ STAGE 2 — DB Sync (offline) │
├──────────────────────────────────────────────────────────────────────────┤
│ │
│ car_features.parquet │
│ │ │
│ ▼ python -m tools.ingest sync │
│ ┌─────────────────────────────┐ │
│ │ core/data_sync.py │ bulk INSERT ... ON CONFLICT │
│ │ UPSERT into car_features │ (car_id) DO UPDATE │
│ └──────────────┬──────────────┘ │
│ │ │
│ ▼ │
│ ┌─────────────────────────────────────────┐ │
│ │ car_features table (PostgreSQL) │ │
│ │ ───────────────────────────────────── │ │
│ │ car_id UUID (FK → cars.id) │ │
│ │ feature_vector FLOAT[] ← 7-dim │ │
│ │ predicted_price FLOAT ← target │ │
│ │ damage_score FLOAT ← placeholder │ │
│ │ last_updated TIMESTAMPTZ │ │
│ └─────────────────────────────────────────┘ │
│ │
└──────────────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────────────┐
│ STAGE 3 — Model Training (offline) │
├──────────────────────────────────────────────────────────────────────────┤
│ │
│ ▼ python -m scripts.train_price --epochs 50 │
│ │
│ ┌───────────────────────────────────────────────────────────────┐ │
│ │ 1. load_from_db() → TensorBundle(features, targets) │ │
│ │ (or load_from_parquet() as fallback) │ │
│ │ │ │
│ │ 2. StandardScalerBundle.fit(features) │ │
│ │ → scale features ONLY (target stays raw EGP) │ │
│ │ → save price_scaler.pt BEFORE training │ │
│ │ │ │
│ │ 3. make_loaders() → train / val / test (80/10/10) │ │
│ │ deterministic split via torch.Generator(seed) │ │
│ │ │ │
│ │ 4. PriceRegressor(config).to(device) │ │
│ │ Residual MLP: │ │
│ │ input_proj → [ResidualBlock × N] → final_norm → head │ │
│ │ hidden_dims=(256,256,128,128,64) │ │
│ │ GELU · LayerNorm · Dropout(0.15) │ │
│ │ │ │
│ │ 5. Trainer.fit() │ │
│ │ AdamW · CosineAnnealingLR · AMP (CUDA) │ │
│ │ HuberLoss(delta=1.0) on raw EGP │ │
│ │ EarlyStopping(patience=8) + LossCurveCallback │ │
│ │ │ │
│ │ 6. model.save(price_model.pt) │ │
│ │ payload = {config, state_dict, class_name, format_ver} │ │
│ └───────────────────────────────┬───────────────────────────────┘ │
│ │ │
│ ▼ │
│ ai_models/ai_artifacts/ │
│ ├── price_model.pt (self-describing: config + weights) │
│ ├── price_model.json (human-readable config) │
│ ├── price_scaler.pt (features mean/std) │
│ ├── price_encoders.pt (LabelEncoders for 5 categoricals) │
│ └── price_model_loss.png (loss curve) │
│ │
└──────────────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────────────┐
│ STAGE 4 — Serving (online, in FastAPI) │
├──────────────────────────────────────────────────────────────────────────┤
│ │
│ Client sends POST /ai/price-predict │
│ │ │
│ ▼ │
│ ┌─────────────────────────────────────────────────────────────┐ │
│ │ RequestIDMiddleware → set_request_id(uuid4) │ │
│ │ CORSMiddleware → origin check │ │
│ │ get_auth_user → JWT (RS256) → TokenData(user,role) │ │
│ └──────────────────────┬──────────────────────────────────────┘ │
│ │ │
│ ▼ │
│ ┌─────────────────────────────────────────────────────────────┐ │
│ │ routers/ai.py :: predict_price() │ │
│ │ - validate PricePredictRequest (7 *_enc fields) │ │
│ │ - build torch.tensor([[f1..f7]], dtype=float32) │ │
│ └──────────────────────┬──────────────────────────────────────┘ │
│ │ │
│ ▼ │
│ ┌─────────────────────────────────────────────────────────────┐ │
│ │ get_price_inference_service() ← lru_cache, loads ONCE │ │
│ │ - StandardScalerBundle.load(price_scaler.pt) │ │
│ │ - PriceRegressor.load(price_model.pt, PriceModelConfig) │ │
│ │ │ │
│ │ service.predict(x): │ │
│ │ 1. scaler.transform_features(x) │ │
│ │ 2. model(scaled) → pred_scaled │ │
│ │ 3. scaler.inverse_transform_targets(pred_scaled) │ │
│ │ 4. return {predicted_price, confidence} │ │
│ └──────────────────────┬──────────────────────────────────────┘ │
│ │ │
│ ▼ │
│ PricePredictResponse → JSON to client │
│ │
└──────────────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────────────┐
│ STAGE 5 — Frontend consumption │
├──────────────────────────────────────────────────────────────────────────┤
│ │
│ Two flows supported: │
│ │
│ (a) SIMPLE (recommended for the frontend): │
│ │
│ ① POST /ai/encode │
│ { "brand": "Toyota", "model": "Corolla", ... } │
│ → { "brand_enc": 12, "model_enc": 87, ... } │
│ │
│ ② POST /ai/price-predict │
│ { "year": 2020, "mileage": 45000, "brand_enc": 12, ... } │
│ → { "predicted_price": 675000.0, "confidence": 0.85 } │
│ │
│ (b) DIRECT (if the frontend has its own encoders): │
│ │
│ POST /ai/price-predict with *_enc fields directly │
│ │
└──────────────────────────────────────────────────────────────────────────┘

text

---

## 🛠 Tech Stack

| Layer | Technology | Why |
|---|---|---|
| **API** | FastAPI 0.115 | Async native, Pydantic v2, auto OpenAPI, dependency injection |
| **ASGI server** | Gunicorn + Uvicorn workers | Multi-worker prod, `uvloop` on Linux for ~2× throughput |
| **ORM** | SQLAlchemy 2.0 (async) | Typed queries, `select()` API, `asyncpg` driver |
| **Database** | PostgreSQL 16 | Native UUID, ARRAY, ENUM, JSONB, `ON CONFLICT` upserts |
| **Migrations** | Alembic | Versioned schema, `--autogenerate`, idempotent re-runs |
| **Auth** | JWT (RS256) + bcrypt | Asymmetric keys; public key can be shared, private stays secret |
| **ML framework** | PyTorch 2.4 | TorchScript-ready, `torch.compile`-compatible, AMP |
| **Data** | pandas, pyarrow, numpy | CSV → parquet → tensor pipeline |
| **Encoding** | scikit-learn `LabelEncoder` | Battle-tested, deterministic, pickle-safe |
| **Image (planned)** | torchvision, Pillow, OpenCV | ResNet18 backbone for damage detection |
| **Container** | Docker + Docker Compose | Multi-stage build (builder + runtime), slim base |
| **Reverse proxy** | Nginx (Alpine) | Rate limiting, gzip, real-IP, static serving |
| **CI/CD** | GitHub Actions + Docker Hub + HF Spaces | Test → build → scan → deploy |
| **Security scanning** | Trivy (SARIF to GitHub Security tab) | Block on CRITICAL, report HIGH |
| **Observability** | Structured JSON logs + `request_id` contextvar | ELK-ready (Elasticsearch/Logstash/Kibana configs included) |

---

## 📂 Project Structure
CarDealersPro/
├── app/
│ ├── core/ # Cross-cutting concerns
│ │ ├── config.py # Pydantic Settings + RSA key loader
│ │ ├── exceptions.py # AppException hierarchy (typed HTTP errors)
│ │ ├── logging_config.py # RequestIDFormatter, structured logging
│ │ ├── request_id.py # ContextVar-based request tracing
│ │ ├── security.py # JWT create/verify, get_auth_user dep
│ │ └── tasks.py # Background tasks: image/video thumbs
│ │
│ ├── routers/ # HTTP layer (thin — delegates to services)
│ │ ├── ai.py # /ai/price-predict, /ai/encode, /ai/inspect-image
│ │ ├── auth.py # /auth/login
│ │ ├── cars.py # /cars CRUD + filtering + pagination
│ │ ├── finance.py # /finance (loans, disbursements, schedules)
│ │ ├── media.py # /media (chunked upload, magic validation)
│ │ ├── ratings.py # /ratings (car ratings, inspector-only)
│ │ └── users.py # /users (register, get)
│ │
│ ├── services/ # Business logic (DB + orchestration)
│ │ ├── car_service.py # Car queries, FinanceCalculator, loan flows
│ │ ├── pagination.py # PaginatedResponse[T], generic
│ │ └── ml/ # ML subsystem (isolated, testable)
│ │ ├── config.py # FEATURE_COLUMNS, TrainingConfig, etc.
│ │ ├── data_pipeline.py # TensorBundle, TorchStandardScaler, Loaders
│ │ ├── encoders.py # Lazy-loaded LabelEncoders
│ │ ├── damage_pipeline.py
│ │ ├── models/
│ │ │ ├── base.py # CarDealersBaseModel (save/load contract)
│ │ │ └── price_regressor.py
│ │ └── training/
│ │ ├── callbacks.py # EarlyStopping, LossCurveCallback
│ │ ├── inference.py # PriceInferenceService, DamageInferenceService
│ │ └── loop.py # Trainer (AMP, clipping, scheduling)
│ │
│ ├── utils/
│ │ ├── init.py # bcrypt password hash/verify
│ │ └── filter_builder.py # Dynamic SQL filter builder (safe, typed)
│ │
│ ├── database.py # 3-tier engines (primary/write/read)
│ ├── main.py # FastAPI app, middleware, exception handlers
│ ├── models.py # SQLAlchemy ORM (10 tables)
│ └── schemas.py # Pydantic v2 request/response models
│
├── alembic/ # DB migrations
│ ├── versions/ # ~20 revision files
│ └── env.py
│
├── scripts/
│ ├── train_price.py # End-to-end training entry point
│ └── setup_rsa_keys.py # Generate JWT keypair
│
├── tools/
│ └── ingest.py # CSV → parquet → DB (with subcommands)
│
├── import_data/ # One-off data loaders (Kaggle, credits)
│
├── tests/ # pytest + httpx AsyncClient
│ ├── conftest.py # Fixtures: DB, tokens, users, cars
│ ├── test_auth.py
│ ├── test_cars.py
│ ├── test_full_finance_cycle.py
│ ├── test_media.py
│ └── test_users.py
│
├── deployment/
│ ├── nginx.conf # Reverse proxy, rate limiting, real-IP
│ └── proxy_params.conf
│
├── .github/workflows/CI.yml # test → build → scan → HF deploy
├── Dockerfile # Multi-stage (builder + slim runtime)
├── Dockerfile.hf # HF Spaces wrapper
├── docker-compose.yml # api + nginx
├── gunicorn_conf.py # Production server config
├── alembic.ini
├── pyproject.toml
├── requirements.txt # Web + auth + utilities
├── requirements-ml.txt # torch, torchvision, pandas, sklearn
├── requirements-ai.txt # Optional: litellm, openai, ...
└── README.md # ← you are here

text

---

## 🎯 Core Domains

### 1. Users & RBAC

Six roles with different capabilities:

| Role | Can do |
|---|---|
| **CLIENT** | Browse cars, apply for loans, upload profile, rate cars |
| **DEALER** | CRUD own cars, upload media, manage inventory (limited by subscription plan) |
| **BANK** | Review loan applications, disburse funds, define rates |
| **INSPECTOR** | Rate cars, upload inspection reports |
| **INSURANCE** | (planned) issue policies |
| **ADMIN** | Override ownership, update any car, view everything |

Subscription plans cap dealer inventory:
```python
SUBSCRIPTION_LIMITS = {"FREE": 10, "SILVER": 50, "GOLD": 200, "PLATINUM": 1000}
2. Cars & Media
Soft delete (is_deleted) — records never physically vanish.

Two prices: price_consumer (retail) and price_dealer (wholesale).

Media: chunked upload (never loads full file into RAM), magic-byte validation, background compression + video thumbnails.

Filtering: dynamic build_filter_query supports field, field_min, field_max, field__in, operators (>50000), and free-text search (ILIKE across multiple columns).

3. Finance 
Full loan lifecycle:

text
APPLY → UNDER_REVIEW → APPROVED → DISBURSED → REPAYING → PAID_OFF
                    ↘ REJECTED
Validation: down payment %, tenure caps, debt-to-income ratio (≤40%), income check.

Amortization: standard formula PMT = P·r / (1 − (1+r)^-n).

Repayment schedule: generated at approval — one row per installment with principal_amount, interest_amount, remaining_balance.

Waterfall payment algorithm: a single payment can span multiple overdue installments — oldest first, with grace-period-aware overdue tracking.

Row locking: SELECT ... FOR UPDATE on loan + car rows prevents race conditions during complete_finance_sale.

4. Ratings & Trust
CarRating: (user, car) composite PK; value_score ∈ [0,100] enforced by CheckConstraint.

UserRating: bidirectional trust score; CheckConstraint blocks self-rating.

5. AI / ML
Price prediction (production): residual MLP, 7 features, raw EGP target.

Damage detection (planned): ResNet18 + classification head.

🤖 Machine Learning Pipeline
Why a Residual MLP and not a plain MLP?
Pre-norm residual blocks stabilize training at depth without warmup.

ShapeChangeBlock handles dim transitions cleanly (avoids the classic "residual on non-square shapes" bug).

Final LayerNorm decouples representation scale from target scale — measurably better Huber convergence.

Designed as a stepping stone to FT-Transformer over the same 7 tabular features.

Features (order matters!)
python
FEATURE_COLUMNS = (
    "year",            # numeric
    "mileage",         # numeric
    "brand_enc",       # encoded int
    "model_enc",       # encoded int
    "fuel_type_enc",   # encoded int
    "transmission_enc",# encoded int
    "body_type_enc",   # encoded int
)
INPUT_DIM = 7
Any mismatch in this order silently corrupts predictions. Both the router (ai.py) and the training script assert against FEATURE_COLUMNS.

Why pure-PyTorch scaling?
sklearn.StandardScaler is fine, but mixing numpy-based sklearn objects with torch tensors causes subtle dtype/device bugs. TorchStandardScaler keeps everything in float32 CPU tensors, so save/load is just torch.save/torch.load — no pickle-of-numpy issues, no sklearn version pinning.

Model persistence contract (CarDealersBaseModel)
Every .pt file is self-describing:

python
{
    "config":        {...},              # dataclass asdict
    "state_dict":    {...},              # model weights
    "class_name":    "PriceRegressor",
    "format_version": 1,                 # forward-compat
}
A JSON sidecar (.json) is written alongside for human readability (and preserves Arabic characters via ensure_ascii=False).

Training loop features
AMP (CUDA only) — 2–3× faster on modern GPUs.

Gradient clipping (norm=1.0) — prevents exploding gradients.

Cosine annealing or ReduceLROnPlateau.

EarlyStopping — stops on val_loss plateau, saves best checkpoint.

Loss curve PNG — auto-exported to artifacts.

Windows-safe — raises a clear error if num_workers > 0 on win32 without if __name__ == "__main__".

🧭 Data Flow: From CSV to Frontend
Step	Command / Trigger	Output	Where
1. Inspect	python -m tools.ingest inspect	Cleaned summary	stdout
2. Features	python -m tools.ingest features	car_features.parquet + scaler + encoders	data/optimized/, ai_models/ai_artifacts/
3. Sync	python -m tools.ingest sync	rows in car_features table	PostgreSQL
4. Train	python -m scripts.train_price	price_model.pt + loss curve	ai_models/ai_artifacts/
5. Serve	FastAPI startup (first request to /ai/*)	in-memory model (loaded once)	RAM
6. Encode	POST /ai/encode	*_enc ints	HTTP
7. Predict	POST /ai/price-predict	{predicted_price, confidence}	HTTP
8. Display	Frontend renders	user sees EGP price	browser
🔐 Security Model
Concern	Mitigation
Password storage	bcrypt (cost factor default) via app/utils/__init__.py
JWT	RS256 — private key signs, public key verifies; keys stored as base64 in env for cloud, or .pem files locally
Token expiry	ACCESS_TOKEN_EXPIRE_MINUTES=60 by default
Inactive users	is_active=False → login blocked at router level
SQL injection	SQLAlchemy select() + parameterized queries; filter_builder uses getattr(model, name) + in_() only
File uploads	Extension whitelist + magic-byte validation (first 2KB) + 100MB cap + disk-space precheck
Path traversal	Filenames are UUID-renamed; storage dir is fixed
Rate limiting	Nginx: 100 r/s API, 50 r/s general, 10 concurrent conns/IP
Security headers	Nginx: X-Frame-Options, X-Content-Type-Options, CSP, Referrer-Policy
DB least-privilege	3-tier users (read/write/primary) — the read user literally cannot INSERT
Request tracing	X-Request-ID echoed back; every log line carries it
Secrets	.env never committed; .gitignore blocks *.pem, secrets/, *.key
🗄 Database Design
Tables (10)
text
users ──────┬── cars ──────┬── car_media
            │              ├── car_ratings ──┐
            │              ├── car_features  │
            │              └── loan_applications ──┬── loan_disbursements
            │                                       ├── loan_repayments
            │                                       └── repayment_schedules
            └── user_ratings                       └── transactions
Notable DB-level features
UUID primary keys with gen_random_uuid() server default.

ENUM types (userrole, mediatype, loanstatus, paymentmethod) — validated by Postgres, not just the app.

ARRAY(Float) for car_features.feature_vector — one round-trip per row.

ON DELETE SET NULL for cars.owner_id — cars survive their owner's deletion.

ON DELETE CASCADE for media, ratings, loans — clean cascade chains.

CheckConstraints: value_score ∈ [0,100], trust_score ∈ [0,100], rater_id != target_user_id.

Composite indexes for common query patterns: (brand, model, color), (client_id, status), (application_id, due_date).

Idempotent migrations — DROP INDEX IF EXISTS, DROP CONSTRAINT IF EXISTS where the name is not guaranteed.

📡 API Reference
Auth
Method	Path	Purpose
POST	/auth/login	Get JWT
Users
Method	Path	Purpose
POST	/users/	Register
GET	/users/{id}	Get profile
Cars
Method	Path	Purpose
GET	/cars/	Paginated + filtered list
GET	/cars/my_cars	Owner's inventory
GET	/cars/{id}	Detail with rating stats
POST	/cars/	Create (DEALER only)
PUT	/cars/{id}	Update
DELETE	/cars/{id}	Soft delete
Media
Method	Path	Purpose
POST	/media/upload/{car_id}	Chunked upload
GET	/media/car/{car_id}	List car media
DELETE	/media/{media_id}	Delete
Finance
Method	Path	Purpose
POST	/finance/calculate	Loan calculator
POST	/finance/applications	Apply for loan
GET	/finance/applications/{id}	Get application
PATCH	/finance/applications/{id}	Update status/rate
GET	/finance/clients/{id}/applications	Client's loans
POST	/finance/disbursements	Record disbursement
POST	/finance/repayments	Record repayment
POST	/finance/transactions	Record transaction
POST	/finance/applications/{id}/complete	Finalize sale
POST	/finance/applications/{id}/schedule	Generate schedule
GET	/finance/applications/{id}/schedule	View schedule
GET	/finance/applications/{id}/schedule/summary	Dashboard summary
POST	/finance/applications/{id}/schedule/payment	Pay installment
GET	/finance/clients/{id}/loans/summary	Aggregated view
Ratings
Method	Path	Purpose
POST	/ratings/rate-car/{car_id}	Inspector-only rating
AI
Method	Path	Purpose
POST	/ai/encode	Raw → encoded (frontend-friendly)
POST	/ai/price-predict	Encoded → price
POST	/ai/inspect-image	Damage detection (501 until trained)
Ops
Method	Path	Purpose
GET	/health	Liveness probe
GET	/	Root status
Full OpenAPI: http://localhost:8000/docs

🚀 Getting Started
Prerequisites
Python 3.11+

PostgreSQL 16+ (local or Neon/RDS)

Docker & Docker Compose (for containerized run)

Windows only: Visual Studio C++ Build Tools (for torch/asyncpg wheels)

Local (non-Docker)
bash
# 1. Clone + venv
git clone https://github.com/your-org/CarDealersPro.git
cd CarDealersPro
python -m venv .venv
.venv\Scripts\activate          # Windows
source .venv/bin/activate       # Linux/Mac

# 2. Install deps
pip install -r requirements.txt -r requirements-ml.txt

# 3. Generate JWT keys
python scripts/setup_rsa_keys.py

# 4. Configure env
copy .env.example .env          # then edit
# Required: DATABASE_PASSWORD, DATABASE_* (host/port/name/user)
# Optional: PRIVATE_KEY_BASE64/PUBLIC_KEY_BASE64 (else uses .pem files)

# 5. Migrate DB
alembic upgrade head

# 6. Ingest + train
python -m tools.ingest inspect
python -m tools.ingest features
python -m tools.ingest sync      # requires DB up
python -m scripts.train_price --device cpu --epochs 30

# 7. Run
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload --reload-dir app
Open http://localhost:8000/docs.

Docker (recommended)
bash
docker compose up -d --build

# Ingest + train inside the container
docker compose exec api python -m tools.ingest features
docker compose exec api python -m scripts.train_price --device cpu

# Logs
docker compose logs -f api
Nginx on port 80 → proxies to api:8000.

🧪 Testing
bash
# Local (needs a running Postgres on 5433 for tests)
pytest -v

# Docker (spins up an isolated test DB)
docker compose -f docker-compose.test.yml up --build
Test suite covers:

Auth — valid login, wrong password, inactive user, token shape.

Cars — CRUD, filtering, pagination, soft delete, ownership enforcement.

Media — upload with magic validation, list, delete, orphan cleanup.

Users — register, duplicate email, fetch, 401 on missing auth.

Finance (full cycle) — apply → approve → complete → schedule → pay first installment → verify is_paid. Plus validation edge cases (down payment > price, tenure=0, invalid car_id).

Fixtures in conftest.py spin up a fresh cardealerspro_test DB, generate ephemeral RSA keys, override get_write_db / get_read_db, and issue JWTs per role.

🔁 CI/CD
.github/workflows/CI.yml runs on every push/PR to main:

text
┌──────────────┐   ┌──────────────┐   ┌──────────────┐   ┌──────────────┐
│  Checkout    │→  │  Install uv  │→  │  Install     │→  │  Run pytest  │
│              │   │  + cache     │   │  reqs + ML   │   │              │
└──────────────┘   └──────────────┘   └──────────────┘   └──────┬───────┘
                                                                  │
                                                                  ▼
┌──────────────┐   ┌──────────────┐   ┌──────────────┐   ┌──────────────┐
│  Deploy HF   │←  │  Trivy scan  │←  │  Build+Push  │←  │  Buildx      │
│  Spaces      │   │  (CRITICAL)  │   │  Docker Hub  │   │  setup       │
└──────────────┘   └──────────────┘   └──────────────┘   └──────────────┘
Secrets required (GitHub → Settings → Secrets):

Name	Purpose
TEST_DB_PASSWORD	Postgres test service password
DOCKER_HUB_USERNAME / DOCKER_HUB_TOKEN	Push images
HF_TOKEN / HF_USERNAME / HF_SPACE_NAME	Deploy to Hugging Face Spaces
Trivy policy: block on CRITICAL only, ignore-unfixed=true. HIGH CVEs are uploaded as SARIF to the GitHub Security tab without breaking the build (base images routinely carry HIGH CVEs whose patches are pending upstream).

🚢 Deployment
Docker Compose (single host)
api + nginx on a shared bridge network. Nginx reads deployment/nginx.conf + proxy_params.conf as read-only mounts.

AWS (see AWS_DEPLOYMENT.md)
Two documented paths:

Elastic Beanstalk — easiest, managed infra.

ECS Fargate — full control, task definitions included.

RDS Postgres is the recommended DB. Secrets go into AWS Secrets Manager and are injected into the task definition as secrets (not environment).

Hugging Face Spaces
Dockerfile.hf is a one-liner that pulls the CI-built image:

dockerfile
FROM <DOCKER_HUB_USERNAME>/cardealerspro:<git-sha>
CI rewrites the tag on each deploy, pushing a Dockerfile-only commit to the Space repo. This keeps HF as a pure runtime and Docker Hub as the artifact registry.

Configuration via environment
env
# Database (either DATABASE_URL or the 4 DATABASE_* fields)
DATABASE_URL=postgresql://user:pass@host:5432/db

# JWT
ALGORITHM=RS256
ACCESS_TOKEN_EXPIRE_MINUTES=60
PRIVATE_KEY_BASE64=...
PUBLIC_KEY_BASE64=...

# App
CORS_ORIGINS=https://app.example.com,http://localhost:3000
ENABLE_AI=false
LOG_LEVEL=info
WEB_CONCURRENCY=4
MPLBACKEND=Agg
⚡ Performance & Observability
Performance
Async everywhere — no blocking I/O in request paths.

3-tier connection pools — separate pool sizes for read (20+40) / write (10+20) / primary (15+30).

pool_pre_ping + pool_recycle=3600 — avoids stale connections on long-lived hosts.

NullPool in tests — no background asyncpg tasks that would break teardown.

Chunked uploads — 1MB chunks; RAM usage is O(chunk) not O(file).

Nginx gzip — JSON/JS/CSS compressed; images/videos explicitly skipped (already compressed).

uvloop on Linux — ~2× throughput vs. default asyncio loop.

AMP in training — FP16 forward/backward on CUDA with FP32 master weights.

lru_cache model singletons — one load per process, not per request.

Observability
Structured logs — one line per event, JSON-friendly, carries request_id.

X-Request-ID in every response — trace from client to DB log.

SQL comments — every query is prefixed with /* Request_id: <uuid> */ so slow-query logs point back to the HTTP request.

ELK-ready — filebeat.yml, filebeat_env.yml, start_elk.* scripts included. Filebeat tails both app logs and Postgres JSON logs, ships to Elasticsearch, visualized in Kibana.

Health endpoints — /health for liveness, wired into both Docker HEALTHCHECK and Nginx.

🧠 Design Decisions (Why X not Y)
Decision	Rationale
FastAPI over Flask/Django	Native async + Pydantic + OpenAPI auto-generation; no adapter overhead
SQLAlchemy 2.0 async over raw asyncpg	Typed ORM + migrations + relationship loading, without giving up async
3-tier DB users over a single user	A bug in a read path literally cannot mutate data — enforced by Postgres GRANTs
Alembic over create_all	Production schema evolution must be versioned and reversible
JWT RS256 over HS256	Public key can verify without the private key — enables distributed auth
Residual MLP over plain MLP	Pre-norm residuals stabilize deep training; ShapeChangeBlocks handle dim changes cleanly
Pure-PyTorch scaler over sklearn	No numpy/sklearn/torch dtype fights; .pt in, .pt out
weights_only=False for encoders only	LabelEncoder isn't a tensor — restricted loading is impossible; we only load files we produced
Trivy blocks on CRITICAL only	HIGH in base images is noise; CRITICAL with a fix is a real blocker
/ai/encode endpoint	Lets the frontend send human values without shipping encoders to the browser
Loss on raw EGP, not scaled target	HuberLoss(delta=1.0) is robust to outliers; scaling the target would require un-scaling in every consumer
Idempotent migrations	Old migrations get re-run on fresh DBs; IF EXISTS prevents spurious failures
slots=True dataclasses for configs	Prevents accidental attribute additions; smaller memory footprint
🗺 Roadmap
Near-term
□ Train and ship the damage-detection model (ResNet18).
□ Real confidence intervals for price predictions (MC dropout or quantile regression).
□ Prometheus metrics endpoint (/metrics).
□ Rate limiting at the FastAPI level (currently only Nginx).
Mid-term
□ WebSocket notifications for loan status changes.
□ Multi-currency support (EGP/USD/EUR scaffolding exists).
□ Admin dashboard (aggregated analytics).
□ Feature store for ML retraining.
Long-term
□ Migrate price model to FT-Transformer (feature tokenizer + attention).
□ Event-driven architecture (Kafka/RabbitMQ) for disbursements.
□ Multi-region deployment with read replicas.
□ GraphQL gateway on top of the REST API.
📄 License
MIT — see LICENSE.

🙏 Acknowledgements
Kaggle Egyptian Cars dataset.

PyTorch team for torch.compile, AMP, and the excellent docs.

FastAPI + SQLAlchemy async ecosystem.

The  engineering principles that shaped the layout, testing strategy, and deployment pipeline.