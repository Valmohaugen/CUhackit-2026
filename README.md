# Quantum DNS Shield

**CUhackit 2026 — Team Ransom**

Post-quantum DNS security demonstrator with real-time QRNG entropy, lattice-based cryptographic signatures, and interactive threat analysis.

## Features

- **Post-Quantum DNS Signing** — ML-DSA-65 (Dilithium), Falcon-512 via liboqs
- **Quantum Random Number Generation** — Qiskit AerSimulator with 4 generation methods and 4 entropy extractors
- **Shor's Algorithm Demo** — Live factoring of N=15 on quantum simulator
- **Migration Planning** — Cost/risk/timeline matrix across 5 deployment scenarios
- **Real-Time Dashboard** — Streamlit UI with auto-refreshing metrics, toggleable configuration
- **AWS CDK Infrastructure** — ECS Fargate, ElastiCache Redis, Lambda QRNG, ALB with HTTPS

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│  ALB (HTTP/HTTPS)                                       │
│    /api/*  → FastAPI :8000     /*  → Streamlit :8501    │
├─────────────────────────────────────────────────────────┤
│  ECS Fargate (single container)                         │
│    ├── FastAPI API server                               │
│    └── Streamlit dashboard                              │
├─────────────────────────────────────────────────────────┤
│  ElastiCache Redis          │  Lambda (every 5 min)     │
│    - Seed pool              │    - QRNG batch gen       │
│    - Config toggles         │    - S3 audit logs        │
│    - Live metrics           │                           │
└─────────────────────────────────────────────────────────┘
```

## Quick Start (Local)

```bash
# 1. Clone and install
pip install -r requirements.txt

# 2. Start Redis + app
docker-compose up --build

# 3. Fill seed pool
python scripts/local_seed_fill.py

# 4. Smoke test
bash scripts/smoke_test.sh

# 5. Run tests
pytest tests/ -v
```

Dashboard: http://localhost:8501
API: http://localhost:8000/api/health

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/health` | Health check |
| GET | `/api/config` | Get all toggle values |
| POST | `/api/config` | Update toggles |
| POST | `/api/resolve` | Resolve domain with PQ signing |
| GET | `/api/metrics/live` | Real-time query metrics |
| GET | `/api/qrng/status` | QRNG pool status |
| GET | `/api/benchmarks` | Crypto scheme benchmarks |
| GET | `/api/migration` | Migration cost/risk matrix |
| GET | `/api/entropy` | Entropy comparison (QRNG vs PRNG) |
| POST | `/api/attack/shors` | Start Shor's algorithm |
| GET | `/api/attack/shors` | Poll Shor's status |

## Configuration Toggles

All toggles are stored in Redis and controllable via the API and dashboard sidebar.

| Toggle | Redis Key | Options | Default |
|--------|-----------|---------|---------|
| Random source | `config:source` | `qrng`, `prng` | `qrng` |
| Quantum backend | `config:backend` | `aer`, `ibm` | `aer` |
| PQ signature | `config:scheme` | `ml-dsa-65`, `falcon-512`, `rsa-2048` | `ml-dsa-65` |
| Migration phase | `config:phase` | `classical`, `hybrid`, `pq_only` | `hybrid` |
| Scenario | `config:scenario` | `web`, `iot`, `enterprise`, `critical`, `financial` | `enterprise` |
| Extractor | `config:extractor` | `von_neumann`, `toeplitz`, `fft`, `parity` | `von_neumann` |
| QRNG method | `config:qrng_method` | `mod2_xor`, `iteration`, `concatenation`, `multi_run` | `multi_run` |

## AWS Deployment

### Prerequisites

```bash
aws configure                    # Set up AWS CLI
npm install -g aws-cdk           # Install CDK
cd infra && cdk bootstrap        # Bootstrap CDK
aws secretsmanager create-secret \
  --name quantum-dns/ibm-token \
  --secret-string "YOUR_IBM_TOKEN"
```

### Deploy (HTTP)

```bash
cd infra
pip install -r requirements.txt
cdk deploy
```

### Deploy (HTTPS with custom domain)

1. Request ACM certificate for your domain in `us-east-1`
2. Add DNS validation CNAME record
3. Deploy with cert ARN:

```bash
cdk deploy -c certificate_arn=arn:aws:acm:us-east-1:ACCOUNT:certificate/ID
```

4. Add CNAME record pointing your domain to the ALB DNS name (from CDK output)

## Tech Stack

- **Backend**: FastAPI, uvicorn
- **Frontend**: Streamlit
- **Crypto**: liboqs (ML-DSA-65, Falcon-512), oqs-python
- **Quantum**: Qiskit 2.x, qiskit-aer (AerSimulator)
- **State**: Redis (ElastiCache in AWS)
- **Infra**: AWS CDK, ECS Fargate, Lambda, ALB, S3, CloudWatch
- **Container**: Docker multi-stage build
