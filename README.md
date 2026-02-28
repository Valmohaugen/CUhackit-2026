# Quantum DNS Shield

**CUhackit 2026 — Team Ransom | Clemson University**

Post-quantum DNS security demonstrator combining **lattice-based cryptographic signatures**, **quantum random number generation**, and **interactive threat analysis** — built to show why migrating to post-quantum cryptography matters *today*.

---

## Why We Built This

### The Problem

The internet's security stack is built on a mathematical assumption: factoring very large numbers is computationally infeasible. RSA and elliptic curve cryptography (ECC) — the algorithms protecting DNS, TLS, and digital signatures — derive their security entirely from this assumption.

In 1994, Peter Shor proved that a quantum computer could factor large integers in **polynomial time** [[1]](#references). Today's quantum computers are not yet powerful enough to threaten RSA-2048, but resource estimates project that a quantum computer with ~20 million noisy physical qubits could break RSA-2048 in ~8 hours [[2]](#references). Current gate-based systems have surpassed 1,000 noisy physical qubits (e.g., IBM Condor at 1,121 qubits), with multi-thousand-qubit systems in development. The timeline to a cryptographically relevant quantum computer (CRQC) is estimated at **2030–2040** [[3]](#references).

This creates an urgent problem today — not in a decade:

**Harvest-Now, Decrypt-Later (HNDL)**: Nation-state adversaries are already recording encrypted internet traffic with the intent to decrypt it once quantum computers mature. Any data encrypted with RSA or ECC that must remain secret for more than 5–10 years is at risk *right now*. Medical records, government intelligence, financial data, and long-lived TLS sessions are all being harvested.

DNS is a particularly high-value target. DNS signing keys (DNSSEC), resolver-to-authoritative-server communication, and zone transfer records all use RSA or ECDSA. An attacker who records DNSSEC-signed zone data today can forge DNS responses tomorrow — enabling man-in-the-middle attacks on all downstream TLS sessions.

### Our Solution

NIST finalized three post-quantum cryptographic standards in 2024 (FIPS 203, 204, 205) designed to resist both classical and quantum attacks. Quantum DNS Shield demonstrates a **practical migration path** for DNS security:

1. **Post-quantum DNS signing** — We perform real DNS resolution signed with NIST-standardized lattice-based and hash-based signature schemes (ML-DSA-65, Falcon-512, SLH-DSA-SHA2-128s), replacing the quantum-vulnerable RSA-2048 baseline. Lattice problems like Learning With Errors (LWE) have no known quantum speedup — Shor's algorithm exploits periodic structure in modular exponentiation, which lattices fundamentally lack.

2. **Quantum Random Number Generation** — We generate cryptographic seeds using Qiskit quantum circuits. Unlike classical PRNGs (which are deterministic given a seed), quantum measurement outcomes are fundamentally unpredictable by the laws of physics. This provides **information-theoretic** randomness guarantees for nonce generation in PQ signature schemes.

3. **Live threat analysis** — The Attack Theater demonstrates Shor's algorithm on a real quantum simulator, shows the HNDL threat timeline, and performs security margin analysis — quantifying how much protection each scheme provides against quantum attack.

4. **Crypto-agility** — The dashboard lets you switch between schemes, sources, and configurations in real time, demonstrating that PQ migration does not require redesigning the system — only swapping the cryptographic module.

> **The core thesis**: post-quantum migration for DNS cannot wait until quantum computers arrive. The HNDL threat exists today, NIST standards are final, and the performance overhead is acceptable. This project demonstrates all three points interactively.

## Features

- **Post-Quantum DNS Signing** — ML-DSA-65 (FIPS 204), Falcon-512 (selected for FIPS 206), SLH-DSA-SHA2-128s (FIPS 205) via liboqs, with RSA-2048 classical baseline and cached verifier instances for reduced latency
- **Quantum Random Number Generation** — Qiskit AerSimulator with 4 entropy extractors (Von Neumann, Toeplitz, FFT, Parity); optional IBM Quantum hardware backend
- **Generalized Shor's Algorithm** — Factors arbitrary semiprimes (N=15, 21, 33, 35, 55, 77, 91+) using UnitaryGate-based modular exponentiation, multi-base QPE, circuit visualization, and measurement histograms
- **Quantum Attack Timing** — Side-by-side comparison of Shor's attack time vs. post-quantum scheme defense, showing which schemes beat quantum attacks and by how much
- **Security Margin Analysis** — Real signing speed vs estimated quantum attack time per scheme with NIST security levels
- **HNDL Threat Model** — Color-coded threat matrix mapping attacks to schemes with data shelf-life urgency analysis
- **Quantum Readiness Score** — 0-100% readiness indicator per query combining PQ scheme, QRNG seed source, and pool health
- **Scheme Comparison Charts** — Auto-loading charts under DNS Resolver comparing all schemes across keygen/sign/verify timing, key/signature sizes, and QRNG vs PRNG latency
- **Per-Step Latency Breakdown** — DNS lookup, signing, verification, and seed fetch timing
- **Latency Distribution** — P50/P95/P99 percentile analysis with histograms across schemes
- **QRNG vs PRNG Entropy Comparison** — Shannon entropy, chi-squared, serial correlation, and runs test with numeric values alongside all charts
- **Side-by-Side Comparison** — Resolve the same domain across multiple scheme/source combinations with numeric latency captions
- **AI Assistant** — GPT-4o-mini-powered chatbot tab with context-aware responses using benchmark and entropy data
- **Real-Time Dashboard** — Streamlit with auto-refreshing live metrics (5-second interval), Enter-key form submission, configurable toggles
- **AWS CDK Infrastructure** — ECS Fargate, ElastiCache Redis, ALB, CloudFront, S3 audit, CloudWatch, SNS alerting (QRNG runs as in-process background task)

## Intended Architecture

The system was designed for deployment on AWS as a fully managed, containerized application. Even where we were unable to complete the full cloud deployment within the hackathon window, the architecture below reflects what we built toward and what every component in the codebase is wired to support. Locally, the entire stack runs via Docker Compose (FastAPI + Streamlit + Redis).

```
┌──────────────────────────────────────────────────────────────┐
│                        AWS Cloud                              │
│                                                               │
│  ┌────────────┐                                              │
│  │ CloudFront │  HTTPS termination + CDN                     │
│  └─────┬──────┘                                              │
│        ▼                                                      │
│  ┌──────────┐    ┌─────────────────────────────────────┐     │
│  │   ALB    │───→│        ECS Fargate (1-2 tasks)      │     │
│  │  (HTTP)  │    │  ┌──────────┐   ┌──────────────┐   │     │
│  │          │    │  │ FastAPI  │   │  Streamlit   │   │     │
│  │ /api/* → │    │  │  :8000   │   │    :8501     │   │     │
│  │ /* →     │    │  │          │   │              │   │     │
│  └──────────┘    │  │ (QRNG    │   │              │   │     │
│                  │  │  backgnd │   │              │   │     │
│                  │  │  task)   │   │              │   │     │
│                  │  └────┬─────┘   └──────┬───────┘   │     │
│                  └───────┼────────────────┼───────────┘     │
│                          │                │                  │
│                   ┌──────┴────────────────┘                  │
│                   ▼                                           │
│            ┌────────────┐                                    │
│            │ ElastiCache│                                    │
│            │   Redis    │                                    │
│            │            │                                    │
│            │ - Seed pool│                                    │
│            │ - Config   │                                    │
│            │ - Metrics  │                                    │
│            └────────────┘                                    │
│                                                               │
│  ┌────────────┐  ┌──────────────┐  ┌───────────────────┐    │
│  │  S3 Bucket │  │   Secrets    │  │    CloudWatch     │    │
│  │  (audit)   │  │   Manager    │  │ Dashboard + SNS   │    │
│  └────────────┘  └──────────────┘  └───────────────────┘    │
└──────────────────────────────────────────────────────────────┘
```

### Component Breakdown

| Component | Service | Role |
|-----------|---------|------|
| **CloudFront** | AWS CloudFront | Terminates HTTPS, caches static assets, provides DDoS protection. Routes all traffic to the ALB over HTTP internally. |
| **Application Load Balancer** | AWS ALB | Path-based routing: `/api/*` requests go to FastAPI on port 8000; all other requests go to the Streamlit dashboard on port 8501. |
| **ECS Fargate** | AWS ECS (Fargate launch type) | Runs the application container without managing servers. Auto-scales between 1 and 2 tasks based on CPU utilization (60% threshold). Each task gets 2 vCPU and 4 GB memory. |
| **FastAPI** | Python (uvicorn) | Async REST API handling DNS resolution with PQ signing, cryptographic benchmarks, Shor's algorithm simulation, entropy comparison, migration analysis, and AI chatbot queries. Also runs the QRNG seed generation as a background task every 5 minutes. |
| **Streamlit** | Python (Streamlit) | Interactive 5-tab dashboard: DNS Resolver, Attack Theater, Benchmarks, Live Metrics, and AI Chat. Communicates with FastAPI via synchronous HTTP calls. |
| **ElastiCache Redis** | AWS ElastiCache (Redis 7) | Single source of truth for all runtime state: the QRNG seed pool (up to 50,000 seeds), configuration toggles, live query metrics, benchmark cache, and Shor's algorithm results. Locally, a Docker Redis container fills this role. |
| **QRNG Background Task** | In-process (FastAPI) | Every 5 minutes, generates quantum random seeds by running 100-qubit Hadamard circuits on Qiskit's AerSimulator (or IBM Quantum hardware if configured). Applies entropy extraction (Von Neumann, Toeplitz, FFT, or Parity), validates Shannon entropy, packs bits into 32-byte seeds, and pushes them to Redis. |
| **S3 Bucket** | AWS S3 | Stores audit provenance records for each QRNG batch — timestamps, entropy values, backend used, seed count. 30-day lifecycle policy auto-deletes old records. |
| **Secrets Manager** | AWS Secrets Manager | Securely stores the IBM Quantum API token, Redis AUTH password, and OpenAI API key — kept out of environment variables and source code. |
| **CloudWatch + SNS** | AWS CloudWatch, SNS | Monitoring dashboard tracking QRNG pool size, ALB request count, ECS CPU utilization, and task count. SNS alerts fire when the seed pool drops below 100 seeds or errors spike. |

### How They Work in Concert

When a user opens the dashboard and resolves a domain, here is the end-to-end flow through every layer:

1. **User request** — The user types a domain (e.g., `example.com`) into the Streamlit dashboard and presses Enter.
2. **Dashboard to API** — Streamlit sends a `POST /api/resolve` request to FastAPI with the domain name, selected PQ scheme, and random source preference.
3. **Seed fetch** — FastAPI reads the `config:source` toggle from Redis. If set to `qrng`, it pops a 32-byte quantum seed from the `qrng_seed_pool` list. If the pool is empty or `prng` is selected, it falls back to `os.urandom(32)`.
4. **DNS lookup** — A standard DNS A-record query is sent to the upstream resolver. The response IP addresses are captured.
5. **PQ signing** — The response payload (domain + IPs + timestamp) is serialized and signed with the configured post-quantum scheme (ML-DSA-65, Falcon-512, or SLH-DSA-SHA2-128s) via liboqs. The signer instance is cached in memory to avoid repeated keygen.
6. **Verification** — The signature is immediately verified against the public key using a cached verifier instance, producing a `verified: true/false` result.
7. **Metrics logging** — Per-step latency (seed fetch, DNS lookup, signing, verification) and the full result are logged to Redis for the live metrics feed.
8. **Response** — FastAPI returns the signed DNS result with a quantum readiness score (0–100%) to Streamlit, which renders it with latency breakdowns and signature details.

Meanwhile, **in the background**, the QRNG task runs every 5 minutes to keep the seed pool warm — ensuring that quantum-sourced randomness is always available for the next request.

## How It Works

### End-to-End DNS Query Flow

When a user queries a domain through the dashboard, the system executes a multi-stage pipeline:

```
User → [1] Submit domain → [2] Fetch seed → [3] DNS lookup → [4] Sign response → [5] Verify → [6] Display
```

1. **Submit Domain** — The user enters a domain name (e.g., `example.com`) in the DNS Resolver panel and presses Enter or clicks Resolve.

2. **Fetch Seed** — The API reads the current `config:source` toggle from Redis. If `qrng`, it pops a 32-byte quantum seed from the `qrng_seed_pool` list. If the pool is empty or `prng` is selected, it falls back to `os.urandom(32)`. The seed is used to initialize the signing key.

3. **DNS Lookup** — A standard DNS A-record query is sent to the upstream resolver (system default). The response IP addresses are captured.

4. **Sign Response** — The response payload (domain + IPs + timestamp) is serialized and signed using the configured PQ scheme (ML-DSA-65, Falcon-512, SLH-DSA-SHA2-128s, or RSA-2048). The signer is created via the `create_signer()` factory which attempts liboqs first, then falls back to HMAC-SHA256.

5. **Verify Signature** — The signature is immediately verified against the public key using a cached verifier instance (saves ~0.1-0.5ms per call). The `verified` boolean is included in the response.

6. **Display Results** — The dashboard renders quantum readiness badges, per-step latency metrics, the signature preview, and updates the live metrics feed.

Each step is individually timed, giving a complete latency breakdown: `seed_fetch_ms`, `dns_lookup_ms`, `sign_ms`, `verify_ms`, and total `latency_ms`.

## Research Background

### Post-Quantum Cryptography

Lattice-based cryptography builds on the hardness of problems like **Learning With Errors (LWE)** [[5]](#references) and the **Shortest Vector Problem (SVP)** [[11]](#references). No known quantum algorithm solves these efficiently, making lattices the foundation for NIST's post-quantum standards.

### Mathematical Foundations

**Learning With Errors (LWE)** [[5]](#references): Given $(A, b = As + e)$ where $A \in \mathbb{Z}_q^{m \times n}$, $s \in \mathbb{Z}_q^n$, and $e \leftarrow \chi$ (discrete Gaussian noise), recover the secret $s$. This is computationally equivalent to finding the closest vector in a lattice — no known quantum algorithm solves it efficiently.

$$\text{LWE}: \quad b = As + e \pmod{q}, \quad e \sim \chi_\sigma$$

**Shortest Vector Problem (SVP)** [[11]](#references): Find the shortest non-zero vector $v \in \Lambda$ minimizing $\|v\|$. The best known quantum algorithms require $2^{\Omega(n)}$ time, providing no significant speedup over classical approaches.

Security reduction: Breaking ML-DSA requires solving Module-LWE, which reduces to worst-case lattice problems [[5, 19]](#references).

| Scheme | Standard | Basis | NIST Level | Signature Size |
|--------|----------|-------|-----------|----------------|
| **ML-DSA-65** | FIPS 204 [[7]](#references) | Module-LWE [[6]](#references) | 3 | 3,309 B |
| **Falcon-512** | Selected for FIPS 206 (FN-DSA) [[8]](#references) | NTRU [[9]](#references) | 1 | 666 B |
| **SLH-DSA-SHA2-128s** | FIPS 205 [[10]](#references) | SPHINCS+ [[12]](#references) | 1 | 7,856 B |

### Quantum Threats

Shor's algorithm [[1]](#references) factors large integers in polynomial time, breaking RSA and ECC. Resource estimates suggest ~4,000 logical qubits and ~20 million physical qubits to break RSA-2048 in ~8 hours [[2]](#references). The **HNDL** threat means data recorded today may be decryptable in 5-15 years [[3, 4]](#references).

**Shor's Algorithm** [[1]](#references) uses quantum phase estimation (QPE) and the Quantum Fourier Transform to find the period $r$ of the modular exponentiation function $f(x) = a^x \bmod N$:

$$\text{QFT}|x\rangle = \frac{1}{\sqrt{N}}\sum_{k=0}^{N-1} e^{2\pi i x k / N}|k\rangle$$

Once $r$ is found such that $a^r \equiv 1 \pmod{N}$, factors are extracted via $\gcd(a^{r/2} \pm 1, N)$. The algorithm requires $O(n^2 \log n \log\log n)$ quantum gates for an $n$-bit integer [[1, 2]](#references).

**Grover's Algorithm** provides a quadratic speedup for brute-force search: $O(2^{n/2})$ vs classical $O(2^n)$, effectively halving symmetric key lengths. AES-128 is reduced to 64-bit security; AES-256 remains 128-bit secure.

### Shor's Algorithm Deep Dive

Our implementation generalizes Shor's beyond the canonical N=15 textbook demo by constructing **modular multiplication unitaries programmatically** via Qiskit's `UnitaryGate`.

**How it works:**

1. **Choose a coprime base** — For a given semiprime N, we find up to 5 coprime bases $a$ where $\gcd(a, N) = 1$ and $2 \leq a < \min(N, 30)$.

2. **Build the permutation matrix** — For each base $a$ and power $2^k$, we compute $a^{2^k} \bmod N$ and construct the unitary:

$$U_{a,k}|x\rangle = |a^{2^k} \cdot x \bmod N\rangle \quad \text{for } x < N$$

States $|x\rangle$ with $x \geq N$ are mapped to themselves (identity). This creates a permutation matrix that is wrapped in a `UnitaryGate` and controlled on a counting qubit.

3. **Quantum Phase Estimation** — 8 counting qubits are prepared in superposition via Hadamard gates, and each applies its controlled-$U_{a,2^k}$ gate to the work register. An inverse QFT extracts the phase.

4. **Classical post-processing** — Measured phases are converted to fractions via continued fraction expansion (`Fraction.limit_denominator(N)`), yielding candidate periods $r$. Factors are computed via $\gcd(a^{r/2} \pm 1, N)$.

5. **Multi-base retry** — If the first base fails (e.g., $r$ is odd or $a^{r/2} \equiv -1$), the next coprime base is tried.

**Supported semiprimes and qubit requirements:**

| N | Factors | Work Qubits | Total Qubits | Shots |
|---|---------|-------------|--------------|-------|
| 15 | 3 × 5 | 4 | 12 | 2,048 |
| 21 | 3 × 7 | 5 | 13 | 4,096 |
| 33 | 3 × 11 | 6 | 14 | 8,192 |
| 35 | 5 × 7 | 6 | 14 | 8,192 |
| 55 | 5 × 11 | 6 | 14 | 8,192 |
| 77 | 7 × 11 | 7 | 15 | 16,384 |
| 91 | 7 × 13 | 7 | 15 | 16,384 |

Work qubits = $\lceil \log_2(N) \rceil$. Total = 8 counting + work qubits. Shots scale with N to improve convergence probability.

### Quantum Random Number Generation

Quantum measurement outcomes are fundamentally unpredictable [[13]](#references). Our QRNG pipeline applies Hadamard gates to put qubits in superposition, measures them, and extracts high-quality entropy using Von Neumann debiasing [[14]](#references) and Toeplitz universal hashing [[15, 16]](#references).

**Hadamard Gate**: Puts a qubit into equal superposition:

$$H|0\rangle = \frac{|0\rangle + |1\rangle}{\sqrt{2}}, \quad P(0) = P(1) = \frac{1}{2}$$

**Shannon Entropy** measures randomness quality:

$$H(X) = -\sum_{i} p_i \log_2 p_i$$

Ideal binary source: $H = 1.0$ bit. **Min-entropy** provides a worst-case bound: $H_\infty(X) = -\log_2(\max_i p_i)$.

**Von Neumann Extraction** [[14]](#references): Pairs of bits are examined — (0,1)→0, (1,0)→1, equal pairs discarded. Output rate with input bias $p$: $R = 2p(1-p)$ unbiased bits per pair.

**Toeplitz Hashing** [[15, 16]](#references): Universal-2 hash family with collision probability $\Pr[h(x) = h(y)] \leq 1/|R|$ for $x \neq y$. By the **Leftover Hash Lemma**, extracted bits are $\epsilon$-close to uniform if output length $\leq H_\infty(X) - 2\log(1/\epsilon)$.

**Statistical Tests** used for validation:
- **Chi-squared**: $\chi^2 = \sum_{i=0}^{255} \frac{(O_i - E_i)^2}{E_i}$ where $O_i$ = observed byte frequency, $E_i = n/256$
- **Serial correlation**: $C = \frac{\sum_{i=0}^{n-2}(x_i - \bar{x})(x_{i+1} - \bar{x})}{\sum_{i=0}^{n-1}(x_i - \bar{x})^2}$, ideal $C \approx 0$

### Post-Quantum DNS

Retrofitting PQ signatures into DNS protocols is an active research area [[17]](#references). This project demonstrates PQ-signed DNS responses with configurable scheme selection.

## QRNG Pipeline

The Lambda QRNG generator runs every 5 minutes, producing quantum random seeds and pushing them to a Redis pool. The pipeline:

1. **Generate raw bits** — A 100-qubit circuit with Hadamard gates is run for 4,096 shots on AerSimulator (or IBM QPU). Qubits are processed in chunks of 30 to manage memory. This produces ~409,600 raw bits per invocation.

2. **Apply entropy extraction** — One of 4 configurable extractors processes the raw bits:

| Extractor | Throughput | Bias Elimination | Guarantee |
|-----------|-----------|-----------------|-----------|
| **Von Neumann** | ~25% (varies with bias) | Perfect (zero bias) | By construction [[14]](#references) |
| **Toeplitz** | ~100% (block-aligned) | Near-perfect (ε-close) | Leftover Hash Lemma [[15]](#references) |
| **FFT-Toeplitz** | ~100% (block-aligned) | Good (frequency scrambling) | Toeplitz base + FFT whitening |
| **Parity** | 25% (fixed) | Partial | XOR reduces bias: $p_{out} = \frac{1-(1-2p)^k}{2}$ |

3. **Validate entropy** — Shannon entropy is computed over the extracted bits to verify quality.

4. **Pack into seeds** — Extracted bits are grouped into 32-byte (256-bit) seeds.

5. **Push to Redis** — Seeds are appended to `qrng_seed_pool` with `RPUSH`, capped at 50,000 seeds via `LTRIM`.

6. **Audit log** — If `AUDIT_BUCKET` is set, a JSON provenance record is written to S3 with timestamps, entropy values, and configuration.

## Quick Start (Local)

```bash
# 1. Clone and install
pip install -r requirements.txt

# 2. Start Redis + app
docker-compose up --build

# 3. Fill seed pool (in a separate terminal)
python scripts/local_seed_fill.py

# 4. Smoke test
bash scripts/smoke_test.sh

# 5. Run tests
pytest tests/ -v
```

- **Dashboard:** http://localhost:8501
- **API:** http://localhost:8000/api/health

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/health` | Health check (verifies Redis connectivity) |
| GET | `/api/config` | Get all toggle values |
| POST | `/api/config` | Update toggles (partial update, non-None fields only) |
| POST | `/api/resolve` | Resolve domain with PQ signing |
| GET | `/api/metrics/live` | Real-time query metrics (last 50 queries) |
| GET | `/api/metrics/history` | Historical query data (up to 1000, newest first) |
| GET | `/api/qrng/status` | QRNG pool status (size, last fill, entropy, backend) |
| GET | `/api/benchmarks` | Crypto scheme benchmarks (cached 5 min in Redis) |
| GET | `/api/migration` | Migration cost/risk matrix with recommendations |
| GET | `/api/entropy` | Entropy comparison (QRNG vs PRNG statistical tests) |
| POST | `/api/attack/shors` | Start Shor's algorithm (background task) |
| GET | `/api/attack/shors` | Poll Shor's status and result |
| GET | `/api/attack/security-margin` | Security margin analysis per scheme |
| POST | `/api/chatbot` | AI assistant (requires OPENAI_API_KEY) |

### API Examples

**Resolve a domain with PQ signing:**

```bash
curl -X POST http://localhost:8000/api/resolve \
  -H "Content-Type: application/json" \
  -d '{"domain": "example.com", "scheme": "ml-dsa-65", "source": "qrng"}'
```

Response:

```json
{
  "domain": "example.com",
  "ip_addresses": ["93.184.216.34"],
  "signature": "a3f8c1...(hex)...",
  "scheme": "ML-DSA-65",
  "verified": true,
  "seed_source": "qrng",
  "latency_ms": 12.4,
  "timestamp": "2026-02-28T10:30:00+00:00",
  "seed_fetch_ms": 0.3,
  "dns_lookup_ms": 8.1,
  "sign_ms": 3.2,
  "verify_ms": 0.8,
  "client_ip": "127.0.0.1"
}
```

**Run Shor's algorithm:**

```bash
# Start factoring N=35
curl -X POST http://localhost:8000/api/attack/shors \
  -H "Content-Type: application/json" \
  -d '{"n": 35}'

# Poll for result
curl http://localhost:8000/api/attack/shors
```

Response (when complete):

```json
{
  "status": "done",
  "result": {
    "factored": true,
    "factors": [5, 7],
    "n": 35,
    "qubits_used": 14,
    "shots": 8192,
    "time_seconds": 18.8,
    "circuit_depth": 247,
    "method": "quantum",
    "bases_tried": [2, 3, 4, 6, 8],
    "n_work_qubits": 6,
    "total_unique_outcomes": 256,
    "circuit_text": "...(ASCII circuit diagram)...",
    "measurement_counts": {"00000000": 512, "01000000": 489, ...}
  }
}
```

**Get entropy comparison:**

```bash
curl http://localhost:8000/api/entropy
```

Response:

```json
{
  "qrng_shannon_entropy": 0.9998,
  "prng_shannon_entropy": 0.9999,
  "qrng_chi_squared": 245.3,
  "prng_chi_squared": 251.7,
  "qrng_chi_squared_p": 0.612,
  "prng_chi_squared_p": 0.487,
  "qrng_serial_correlation": 0.000142,
  "prng_serial_correlation": -0.000089,
  "qrng_runs_test_p": 0.834,
  "prng_runs_test_p": 0.721,
  "sample_size": 10000
}
```

**Get security margin analysis:**

```bash
curl http://localhost:8000/api/attack/security-margin
```

## Configuration Toggles

All toggles are stored in Redis and controllable via the API and dashboard horizontal control bar.

| Toggle | Redis Key | Options | Default |
|--------|-----------|---------|---------|
| Random source | `config:source` | `qrng`, `prng` | `qrng` |
| Quantum backend | `config:backend` | `aer`, `ibm` | `aer` |
| PQ signature | `config:scheme` | `ml-dsa-65`, `falcon-512`, `slh-dsa-128`, `rsa-2048` | `ml-dsa-65` |
| Migration phase | `config:phase` | `classical`, `hybrid`, `pq_only` | `hybrid` |
| Scenario | `config:scenario` | `web`, `iot`, `enterprise`, `critical`, `financial` | `enterprise` |
| Extractor | `config:extractor` | `von_neumann`, `toeplitz`, `fft`, `parity` | `von_neumann` |
| QRNG method | `config:qrng_method` | `mod2_xor`, `iteration`, `concatenation`, `multi_run` | `multi_run` |

## Dashboard

The Streamlit dashboard has 5 main tabs with a clean, sidebar-free layout:

- **DNS Resolver** — Query real domains with Enter-key submission, view PQ-signed responses with quantum readiness score, per-step latency breakdown, comprehensive scheme comparison charts (auto-loaded timing, sizes, QRNG vs PRNG), and side-by-side manual comparison (domain auto-shared between panels)
- **Attack Theater** — Generalized Shor's algorithm (factors N=15 to 91+) with circuit visualization, measurement histograms, quantum attack timing comparison, HNDL timeline with color-coded urgency, threat model matrix, and security margin analysis
- **Benchmarks** — Keygen/sign/verify timing with fastest-scheme recommendation, latency distribution histograms with P50/P95/P99, QRNG vs PRNG entropy comparison with numeric values alongside all charts
- **Live Metrics** — Auto-refreshing query feed (5-second interval), QRNG pool status, quantum circuit visualization, entropy extraction pipeline, historical time-series charts
- **AI Chat** — GPT-4o-mini assistant with context from recent benchmarks and entropy data

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `REDIS_HOST` | `localhost` | Redis server hostname |
| `REDIS_PORT` | `6379` | Redis server port |
| `REDIS_PASSWORD` | *(empty)* | Redis AUTH password (optional) |
| `IBM_QUANTUM_TOKEN` | *(empty)* | IBM Quantum Platform API token; leave empty for simulator-only |
| `OPENAI_API_KEY` | *(empty)* | OpenAI API key for AI chatbot (GPT-4o-mini) |
| `AWS_REGION` | `us-east-1` | AWS region for Lambda/S3 deployments |
| `AUDIT_BUCKET` | *(empty)* | S3 bucket for QRNG audit logs; empty disables S3 logging |
| `LOG_LEVEL` | `DEBUG` | Python logging level (DEBUG, INFO, WARNING, ERROR) |
| `API_HOST` | `localhost` | FastAPI server host |
| `API_PORT` | `8000` | FastAPI server port |
| `DASHBOARD_PORT` | `8501` | Streamlit dashboard port |
| `API_URL` | `http://localhost:8000` | Internal URL for Streamlit → FastAPI communication |

## Project Structure

```
CUhackit-2026/
├── src/
│   ├── api/                    # FastAPI backend
│   │   ├── app.py              # App factory, middleware, router registration
│   │   ├── models/schemas.py   # Pydantic request/response models
│   │   └── routes/             # Endpoint handlers
│   │       ├── health.py       # GET /api/health
│   │       ├── config_routes.py# GET/POST /api/config
│   │       ├── resolve.py      # POST /api/resolve
│   │       ├── metrics.py      # GET /api/metrics/live, history, qrng/status
│   │       ├── benchmarks.py   # GET /api/benchmarks
│   │       ├── entropy.py      # GET /api/entropy
│   │       ├── attack.py       # POST/GET /api/attack/shors, security-margin
│   │       ├── migration.py    # GET /api/migration
│   │       └── chatbot.py      # POST /api/chatbot
│   ├── config/                 # Settings, toggles, Redis keys, defaults
│   │   ├── redis_keys.py       # All Redis key constants
│   │   └── toggles.py          # Toggle definitions and validation
│   ├── dashboard/              # Streamlit frontend
│   │   ├── app.py              # Main entry point, CSS theme, tab layout
│   │   ├── utils.py            # Synchronous httpx wrapper for API calls
│   │   └── components/         # Panel renderers
│   │       ├── resolver_panel.py       # DNS query + results
│   │       ├── scheme_overview_panel.py # Auto-loading scheme comparison charts
│   │       ├── comparison_panel.py     # Manual side-by-side comparison
│   │       ├── attack_panel.py         # Shor's demo + HNDL + security margins
│   │       ├── benchmark_panel.py      # Timing, distribution, entropy
│   │       ├── metrics_panel.py        # Auto-refresh live feed
│   │       ├── chatbot_panel.py        # AI chat interface
│   │       └── sidebar.py             # Horizontal control bar
│   ├── modules/                # Core business logic
│   │   ├── attack_theater.py   # Shor's algorithm, HNDL, security margins
│   │   ├── benchmarks.py       # Scheme timing, statistical tests
│   │   ├── chatbot.py          # OpenAI GPT-4o-mini integration
│   │   ├── dns_resolver.py     # PQ-signed DNS resolution pipeline
│   │   ├── migration_matrix.py # Migration cost/risk analysis (5 scenarios)
│   │   ├── pq_crypto.py        # liboqs signature wrapper + factories
│   │   └── seed_pool.py        # QRNG seed pool (Redis-backed)
│   └── lambda_handler/         # QRNG seed generator (reused as library by FastAPI)
│       └── handler.py          # 100-qubit circuit, 4 extractors, S3 audit
├── infra/                      # AWS CDK infrastructure
│   └── stacks/quantum_dns_stack.py
├── tests/                      # pytest test suite
├── scripts/                    # Utility scripts
│   ├── local_seed_fill.py      # Fill QRNG pool locally
│   └── smoke_test.sh           # Quick health check
├── docker-compose.yml          # Local development (app + redis)
├── Dockerfile                  # Multi-stage build
├── .env.example                # Environment variable template
└── requirements.txt
```

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

### QRNG Seed Generation

QRNG seed generation runs as a **background task inside the FastAPI container** (not a separate Lambda function). The handler code in `src/lambda_handler/handler.py` is reused as a library — called every 5 minutes by an asyncio background loop in the API server:

1. Runs a 100-qubit Hadamard circuit for 4,096 shots (chunked into 30-qubit sub-circuits for memory efficiency)
2. Applies the configured entropy extractor (Von Neumann, Toeplitz, FFT, or Parity)
3. Validates extracted entropy via Shannon entropy computation
4. Packs bits into 32-byte seeds and pushes to Redis (capped at 50,000)
5. Writes audit provenance to S3 (if `AUDIT_BUCKET` is configured)

If `IBM_QUANTUM_TOKEN` is set, the generator selects the least-busy IBM QPU for true quantum randomness, falling back to AerSimulator on failure.

### Monitoring

The CDK stack defines:
- **CloudWatch Dashboard** — QRNG pool size, ALB request count, ECS CPU utilization, task count
- **SNS Alerts** — Pool critically low (<100 seeds), error spikes

## Testing

```bash
pytest tests/ -v
```

The test suite covers:
- API endpoints (health, config, migration, benchmarks)
- DNS resolution with PQ signatures
- QRNG seed pool operations
- Statistical randomness tests (entropy, chi-squared, runs test)
- Benchmark suite across all schemes

## Performance

Typical latency breakdown for a single DNS resolution (local Docker, ML-DSA-65, QRNG):

| Step | Typical Time | Notes |
|------|-------------|-------|
| Seed fetch | 0.2-0.5 ms | Redis LPOP from pool |
| DNS lookup | 5-15 ms | Upstream resolver dependent |
| Signing | 1-5 ms | ML-DSA-65; Falcon ~0.5 ms; SLH-DSA ~50 ms |
| Verification | 0.2-1.0 ms | Cached verifier instance reduces by ~0.3 ms |
| **Total** | **7-22 ms** | Dominated by DNS lookup |

**Seed consumption rate:** At 1 query/second, the pool consumes 86,400 seeds/day. With the QRNG background task generating ~1,500 seeds per 5-minute invocation, the pool sustains ~2 queries/second continuously.

**Scheme comparison (sign + verify):**

| Scheme | Sign (ms) | Verify (ms) | Signature Size | NIST Level |
|--------|----------|-------------|----------------|------------|
| ML-DSA-65 | 1-3 | 0.2-0.5 | 3,309 B | 3 |
| Falcon-512 | 0.3-1.0 | 0.1-0.3 | 666 B | 1 |
| SLH-DSA-SHA2-128s | 30-80 | 1-3 | 7,856 B | 1 |
| RSA-2048 | 0.01-0.05 | 0.01-0.03 | 256 B | Classical |

## Security Considerations

- **QRNG vs PRNG trust model** — QRNG provides information-theoretic randomness guarantees from quantum mechanics. PRNG (`os.urandom`) is computationally secure but deterministic given the seed. For production use, QRNG seeds should be sourced from real quantum hardware.

- **liboqs dependency** — The PQ signatures rely on [liboqs](https://openquantumsafe.org/), which implements NIST draft standards. When liboqs is unavailable, the system falls back to HMAC-SHA256 — this is **not post-quantum secure** and is only suitable for demos.

- **Redis security** — In production, use `REDIS_PASSWORD` and enable TLS. ElastiCache provides encryption at rest and in transit.

- **Secret management** — IBM Quantum tokens and the OpenAI API key should use AWS Secrets Manager (configured in CDK stack), not environment variables in production.

- **Audit logging** — When `AUDIT_BUCKET` is set, every QRNG batch writes provenance metadata to S3, enabling full traceability of seed generation.

## Troubleshooting

**liboqs build errors:**
```
ImportError: No module named 'oqs'
```
Install liboqs-python: `pip install liboqs-python`. On macOS, you may need `brew install liboqs` first. The system will fall back to HMAC-SHA256 if liboqs is unavailable.

**Redis connection refused:**
```
ConnectionError: Error connecting to localhost:6379
```
Ensure Redis is running: `docker-compose up redis -d` or `redis-server`. Check `REDIS_HOST` and `REDIS_PORT` environment variables.

**Empty QRNG pool (all seeds fallback to PRNG):**
Run the local seed fill script: `python scripts/local_seed_fill.py`. This generates seeds using AerSimulator and pushes them to Redis.

**Shor's algorithm timeout:**
Larger semiprimes (N=77, 91) require 15+ qubits and 16,384 shots, which can take 30-60 seconds on AerSimulator. The API runs Shor's as a background task — poll `GET /api/attack/shors` for status.

**Missing OPENAI_API_KEY:**
The AI Chat tab requires a valid OpenAI API key. Set `OPENAI_API_KEY` in `.env` or pass it as an environment variable. The rest of the dashboard functions without it.

**Docker networking issues:**
If the Streamlit dashboard can't reach the API, ensure `API_URL=http://localhost:8000` is set. Inside Docker Compose, the app container runs both services and uses `localhost`.

## Tech Stack

- **Backend**: FastAPI, uvicorn
- **Frontend**: Streamlit
- **Crypto**: liboqs (ML-DSA-65, Falcon-512, SLH-DSA-SHA2-128s), oqs-python
- **Quantum**: Qiskit 2.x, qiskit-aer (AerSimulator), optional IBM Quantum
- **AI**: OpenAI API (GPT-4o-mini)
- **State**: Redis (ElastiCache in AWS)
- **Infra**: AWS CDK, ECS Fargate, ALB, CloudFront, S3, CloudWatch, SNS
- **Container**: Docker multi-stage build

## References

1. Shor, P.W. (1994). "Algorithms for Quantum Computation: Discrete Logarithms and Factoring." *Proc. 35th Annual Symposium on Foundations of Computer Science (FOCS '94)*, pp. 124-134.
2. Gidney, C. & Ekera, M. (2021). "How to Factor 2048-Bit RSA Integers in 8 Hours Using 20 Million Noisy Qubits." *Quantum* 5:433. https://doi.org/10.22331/q-2021-04-15-433
3. Mosca, M. & Piani, M. (2024). "Quantum Threat Timeline Report." *Global Risk Institute*.
4. ETSI White Paper No. 8 (2015). "Quantum Safe Cryptography and Security." *European Telecommunications Standards Institute*.
5. Regev, O. (2005). "On Lattices, Learning with Errors, Random Linear Codes, and Cryptography." *Proc. 37th ACM Symposium on Theory of Computing (STOC '05)*, pp. 84-93.
6. Ducas, L. et al. (2018). "CRYSTALS-Dilithium: A Lattice-Based Digital Signature Scheme." *IACR Transactions on Cryptographic Hardware and Embedded Systems (TCHES)* 2018(1), pp. 238-268.
7. NIST FIPS 204 (2024). "Module-Lattice-Based Digital Signature Standard (ML-DSA)."
8. Fouque, P.-A. et al. (2020). "Falcon: Fast-Fourier Lattice-based Compact Signatures over NTRU." *NIST Post-Quantum Cryptography Standardization Round 3*.
9. Hoffstein, J., Pipher, J. & Silverman, J.H. (1998). "NTRU: A Ring-Based Public Key Cryptosystem." *Algorithmic Number Theory (ANTS-III)*, LNCS 1423, pp. 267-288.
10. NIST FIPS 205 (2024). "Stateless Hash-Based Digital Signature Standard (SLH-DSA)."
11. Ajtai, M. (1996). "Generating Hard Instances of Lattice Problems." *Proc. 28th ACM Symposium on Theory of Computing (STOC '96)*, pp. 99-108.
12. Bernstein, D.J. et al. (2019). "The SPHINCS+ Signature Framework." *Proc. ACM SIGSAC Conference on Computer and Communications Security (CCS '19)*, pp. 2129-2146.
13. Herrero-Collantes, M. & Garcia-Escartin, J.C. (2017). "Quantum Random Number Generators." *Reviews of Modern Physics* 89, 015004. https://doi.org/10.1103/RevModPhys.89.015004
14. Von Neumann, J. (1951). "Various Techniques Used in Connection with Random Digits." *NBS Applied Mathematics Series* 12, pp. 36-38.
15. Carter, J.L. & Wegman, M.N. (1979). "Universal Classes of Hash Functions." *Journal of Computer and System Sciences* 18(2), pp. 143-154.
16. Zhang, X. et al. (2016). "FPGA Implementation of Toeplitz Hashing Extractor for Quantum Random Number Generation." *IEEE International Symposium on Circuits and Systems (ISCAS)*.
17. Mueller, M. et al. (2020). "Retrofitting Post-Quantum Cryptography in Internet Protocols: A Case Study of DNSSEC." *ACM SIGCOMM Computer Communication Review* 50(4).
18. NIST FIPS 203 (2024). "Module-Lattice-Based Key-Encapsulation Mechanism Standard (ML-KEM)."
19. Peikert, C. (2016). "A Decade of Lattice Cryptography." *Foundations and Trends in Theoretical Computer Science* 10(4), pp. 283-424.

## FAQ — Addressing Common Counterarguments

> **Tip:** For deeper explanations, use the **AI Chat** tab in the dashboard. The assistant is trained on this project's architecture, the three NIST PQ standards, and the threat model — it can answer follow-up questions in plain language.

---

### "DNS resolution with RSA completes in milliseconds. An attacker can't run Shor's algorithm fast enough to intercept a live DNS response. Why does post-quantum DNS matter?"

This misconception conflates **real-time attack** with **harvest-and-decrypt attack**. An adversary does not need to break DNS in real time.

The threat is **Harvest-Now, Decrypt-Later (HNDL)**: adversaries record encrypted DNS traffic today — TLS-wrapped resolver queries, DNSSEC-signed zone transfers, signed resolver responses — and decrypt it once a cryptographically relevant quantum computer becomes available (estimated 2030–2040). DNS records reveal browsing behavior, internal infrastructure topology, and certificate metadata. DNSSEC itself uses RSA/ECDSA for *zone signing* — those signatures on long-lived DNS zones are exactly the kind of persistent cryptographic artifacts adversaries stockpile.

DNS is also a **stepping stone**: forging a cached DNS response enables man-in-the-middle attacks on all downstream TLS sessions, authentication flows, and software updates that rely on the domain. The threat is not to the 5ms handshake — it is to the persistent signed artifacts DNS creates and the decade-long window during which they remain valid.

---

### "The increase in sign/verify time with post-quantum schemes is a significant drawback for latency-sensitive DNS. How can this be viable at scale?"

This concern is valid and worth quantifying:

| Scheme | Sign (ms) | Verify (ms) | Signature Size | NIST Level |
|--------|----------|-------------|----------------|------------|
| RSA-2048 | 0.01–0.05 | 0.01–0.03 | 256 B | 0 (vulnerable) |
| ML-DSA-65 | 1–3 | 0.2–0.5 | 3,309 B | 3 |
| Falcon-512 | 0.3–1.0 | 0.1–0.3 | 666 B | 1 |
| SLH-DSA-SHA2-128s | 30–80 | 1–3 | 7,856 B | 1 |

A typical DNS lookup takes **5–15 ms** (upstream resolver dependent). ML-DSA-65 signing adds ~1–3 ms — a 10–30% overhead in the signing step, but DNS lookup still dominates the total. Falcon-512 at 0.3–1 ms is nearly indistinguishable from RSA in the total query budget.

**SLH-DSA-SHA2-128s is the outlier**: its 30–80 ms signing time makes it impractical for high-throughput online DNS signing, but it is appropriate for *offline zone signing* (pre-signing DNS records in advance) where speed is not a constraint. Its conservative hash-based design (no lattice assumptions) makes it attractive for maximum-assurance use cases.

More broadly: NIST standardized these algorithms knowing they would replace RSA/ECC across all of TLS, PKI, and DNSSEC. Browser makers, CDNs, and cloud providers are already deploying ML-KEM (the key exchange counterpart) in production TLS. Cloudflare and Google have run PQ TLS experiments at scale with acceptable overhead. The latency argument applies equally to TLS handshakes and certificate issuance — and industry has concluded the tradeoff is acceptable given the 10-year threat window.

---

### "Classical PRNGs like os.urandom are cryptographically secure. Does QRNG actually add meaningful security, or is the entropy the same?"

The distinction is in the **trust model**, not the output statistics.

`os.urandom` draws from the kernel's CSPRNG (Linux `/dev/urandom`, macOS `SecRandomCopyBytes`), seeded from hardware interrupts, disk I/O timing, and CPU jitter. This is *computationally secure*: an adversary who cannot observe the seed cannot predict the output.

The key caveat: the seed is **deterministic given sufficient system observation**. An adversary who compromises the kernel, hypervisor, or hardware RNG (via side-channel, supply-chain attack, or privileged access) can predict all future PRNG output. This is not a hypothetical — RNG compromise has been a documented attack vector in NSA surveillance programs, hypervisor exploits, and embedded device key generation.

**QRNG provides information-theoretic randomness**: quantum measurement outcomes are fundamentally unpredictable by the laws of physics (Born's rule). No algorithm, no observation of the qubit before measurement, and no amount of computation can predict the result. The randomness is not computationally hard — it is **physically impossible** to predict.

**Practical implications for DNS**:
- QRNG seeds are used for nonce generation in PQ signature schemes. A predictable nonce in a lattice-based scheme can enable signature forgery attacks.
- In adversarial environments (government, finance, critical infrastructure), PRNG compromise is a realistic threat. QRNG eliminates this attack surface.
- The cost: ~0.3 ms for a Redis LPOP of a pre-generated seed — effectively free.
- The pool is replenished automatically every 5 minutes by the Lambda QRNG generator.

When the pool is empty (PRNG fallback), the system remains functionally correct but loses the information-theoretic guarantee. The dashboard displays pool size and QRNG hit rate so this is always visible.

For the purposes of this demo: QRNG also illustrates a key architectural point — **quantum technology appears on both sides of the security equation**, as both a threat (Shor's algorithm) and a defense tool (quantum randomness). This duality is central to why post-quantum cryptography requires holistic thinking, not just algorithm swaps.

---

## What We Learned

Building Quantum DNS Shield in a hackathon compressed months of learning into a single weekend. Whether or not the full AWS deployment was standing at demo time, every component taught us something concrete:

- **Infrastructure-as-code with AWS CDK** — We defined a production-grade multi-service architecture (VPC, ECS Fargate, ElastiCache, ALB, CloudFront, S3, Secrets Manager, CloudWatch, SNS) entirely in Python. The CDK stack taught us how cloud services are wired together — networking, security groups, IAM roles, service discovery — and why infrastructure should be versioned and reproducible.

- **Post-quantum cryptography is practical today** — Integrating liboqs and the NIST-standardized schemes (ML-DSA-65/FIPS 204, SLH-DSA/FIPS 205, Falcon/FIPS 206 draft) showed us that PQ migration is not a theoretical exercise. The performance overhead is measurable but acceptable — ML-DSA-65 signing adds ~1–3 ms to a DNS query that already takes 5–15 ms for the upstream lookup. Crypto-agility (swapping schemes at runtime via toggles) is the key design principle.

- **Quantum computing fundamentals via Qiskit** — We built real quantum circuits: Hadamard-gate QRNG pipelines, Shor's algorithm with programmatic modular-multiplication unitaries, and quantum phase estimation. We learned the gap between textbook quantum algorithms and practical implementation — managing qubit counts, shot budgets, circuit depth, and classical post-processing.

- **Entropy extraction is non-trivial** — Generating raw random bits from quantum measurements is only the first step. We implemented four extraction algorithms (Von Neumann debiasing, Toeplitz universal hashing, FFT whitening, parity reduction) and validated output quality with statistical tests (Shannon entropy, chi-squared, serial correlation, runs test). Each extractor makes different throughput-vs-quality tradeoffs.

- **The HNDL threat is real and urgent** — Building the Attack Theater and security margin analysis made the Harvest-Now, Decrypt-Later threat concrete. Data encrypted with RSA today can be recorded by adversaries and decrypted when quantum computers mature. The migration window is now, not when CRQCs arrive.

---

## Team

**CUhackit 2026 — Team Ransom**
Clemson University
