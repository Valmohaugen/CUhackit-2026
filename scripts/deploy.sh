#!/usr/bin/env bash
# ============================================================================
#  Quantum DNS Shield — One-Click AWS Deploy
#
#  Deploys the full stack to AWS with HTTPS at qdns.valmohaugen.com
#
#  Usage:
#    1. Copy .env.example to .env and fill in your keys
#    2. bash scripts/deploy.sh
#
#  Prerequisites: aws, docker, node (v18+), cdk (npm i -g aws-cdk)
# ============================================================================
set -euo pipefail

# ── Config ──────────────────────────────────────────────────────────────────
DOMAIN="qdns.valmohaugen.com"
REGION="us-east-1"
STACK_NAME="QuantumDNSShield"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
INFRA_DIR="$PROJECT_ROOT/infra"

# ── Colors ──────────────────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
BLUE='\033[0;34m'; BOLD='\033[1m'; NC='\033[0m'

info()  { echo -e "${BLUE}[INFO]${NC}  $*"; }
ok()    { echo -e "${GREEN}[ OK ]${NC}  $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC}  $*"; }
fail()  { echo -e "${RED}[FAIL]${NC}  $*"; exit 1; }
header(){ echo -e "\n${BOLD}━━━ $* ━━━${NC}"; }

# ── Step 1: Prerequisites ──────────────────────────────────────────────────
step_prereqs() {
    header "Step 1/10: Checking prerequisites"
    local missing=()
    for cmd in aws docker node; do
        if ! command -v "$cmd" &>/dev/null; then
            missing+=("$cmd")
        fi
    done
    if ! command -v cdk &>/dev/null; then
        warn "CDK CLI not found. Installing..."
        npm install -g aws-cdk
    fi
    if [[ ${#missing[@]} -gt 0 ]]; then
        fail "Missing tools: ${missing[*]}
  aws    -> https://docs.aws.amazon.com/cli/latest/userguide/install-cliv2.html
  docker -> https://docs.docker.com/get-docker/
  node   -> https://nodejs.org/ (v18+)"
    fi
    if ! docker info &>/dev/null 2>&1; then
        fail "Docker daemon is not running. Start Docker Desktop and retry."
    fi
    ok "All prerequisites found"
}

# ── Step 2: AWS Credentials ────────────────────────────────────────────────
step_aws_config() {
    header "Step 2/10: Checking AWS credentials"
    if ! aws sts get-caller-identity --region "$REGION" &>/dev/null; then
        warn "AWS CLI not configured. Running 'aws configure'..."
        echo ""
        echo "  You need:"
        echo "    - AWS Access Key ID"
        echo "    - AWS Secret Access Key"
        echo "    - Default region: us-east-1"
        echo "    - Default output format: json"
        echo ""
        aws configure
        if ! aws sts get-caller-identity --region "$REGION" &>/dev/null; then
            fail "AWS credentials still invalid after configuration."
        fi
    fi
    local account_id
    account_id=$(aws sts get-caller-identity --query Account --output text)
    ok "AWS account $account_id, region $REGION"
}

# ── Step 3: Load .env ──────────────────────────────────────────────────────
step_load_env() {
    header "Step 3/10: Loading secrets from .env"
    local env_file="$PROJECT_ROOT/.env"
    if [[ ! -f "$env_file" ]]; then
        # Create a minimal .env if it doesn't exist
        warn "No .env file found. Creating one..."
        echo "  Enter your OpenAI API key (or press Enter to skip):"
        read -rp "  OPENAI_API_KEY=" openai_key
        echo "  Enter your IBM Quantum token (or press Enter to skip):"
        read -rp "  IBM_QUANTUM_TOKEN=" ibm_token
        cat > "$env_file" <<EOF
OPENAI_API_KEY=${openai_key}
IBM_QUANTUM_TOKEN=${ibm_token}
EOF
        ok "Created .env file"
    fi
    set -a
    source "$env_file"
    set +a
    if [[ -z "${OPENAI_API_KEY:-}" ]]; then
        warn "OPENAI_API_KEY is empty — chatbot will be disabled"
    else
        ok "OPENAI_API_KEY loaded"
    fi
    if [[ -z "${IBM_QUANTUM_TOKEN:-}" ]]; then
        warn "IBM_QUANTUM_TOKEN is empty — will use Qiskit simulator only"
    else
        ok "IBM_QUANTUM_TOKEN loaded"
    fi
}

# ── Step 4: ACM Certificate ───────────────────────────────────────────────
step_request_cert() {
    header "Step 4/10: ACM certificate for $DOMAIN"

    # Check for an already-issued certificate
    CERTIFICATE_ARN=$(aws acm list-certificates --region "$REGION" \
        --query "CertificateSummaryList[?DomainName=='$DOMAIN' && Status=='ISSUED'].CertificateArn | [0]" \
        --output text 2>/dev/null || echo "None")

    if [[ "$CERTIFICATE_ARN" != "None" && -n "$CERTIFICATE_ARN" ]]; then
        ok "Certificate already issued: $CERTIFICATE_ARN"
        return
    fi

    # Check for a pending certificate
    CERTIFICATE_ARN=$(aws acm list-certificates --region "$REGION" \
        --certificate-statuses PENDING_VALIDATION \
        --query "CertificateSummaryList[?DomainName=='$DOMAIN'].CertificateArn | [0]" \
        --output text 2>/dev/null || echo "None")

    if [[ "$CERTIFICATE_ARN" == "None" || -z "$CERTIFICATE_ARN" ]]; then
        info "Requesting new certificate..."
        CERTIFICATE_ARN=$(aws acm request-certificate --region "$REGION" \
            --domain-name "$DOMAIN" \
            --validation-method DNS \
            --query CertificateArn --output text)
        ok "Certificate requested: $CERTIFICATE_ARN"
        sleep 5  # Wait for ACM to populate validation records
    else
        info "Found pending certificate: $CERTIFICATE_ARN"
    fi

    # Get the DNS validation CNAME
    local cname_name cname_value
    for i in 1 2 3 4 5; do
        cname_name=$(aws acm describe-certificate --region "$REGION" \
            --certificate-arn "$CERTIFICATE_ARN" \
            --query "Certificate.DomainValidationOptions[0].ResourceRecord.Name" \
            --output text 2>/dev/null || echo "None")
        if [[ "$cname_name" != "None" && -n "$cname_name" ]]; then
            break
        fi
        sleep 3
    done

    cname_value=$(aws acm describe-certificate --region "$REGION" \
        --certificate-arn "$CERTIFICATE_ARN" \
        --query "Certificate.DomainValidationOptions[0].ResourceRecord.Value" \
        --output text)

    # Strip the root domain and trailing dots for Namecheap
    local nc_host="${cname_name%.}"
    local nc_value="${cname_value%.}"

    echo ""
    echo -e "${BOLD}╔══════════════════════════════════════════════════╗${NC}"
    echo -e "${BOLD}║  ADD THIS DNS RECORD IN NAMECHEAP               ║${NC}"
    echo -e "${BOLD}╠══════════════════════════════════════════════════╣${NC}"
    echo -e "║  Type:  ${GREEN}CNAME${NC}"
    echo -e "║  Host:  ${GREEN}${nc_host%.valmohaugen.com}${NC}"
    echo -e "║  Value: ${GREEN}${nc_value}${NC}"
    echo -e "║"
    echo -e "║  Namecheap → Domain List → valmohaugen.com"
    echo -e "║  → Advanced DNS → Add New Record"
    echo -e "${BOLD}╚══════════════════════════════════════════════════╝${NC}"
    echo ""

    # Poll for validation
    info "Waiting for certificate validation (usually 2-10 min)..."
    local max_wait=600
    local elapsed=0
    while [[ $elapsed -lt $max_wait ]]; do
        local status
        status=$(aws acm describe-certificate --region "$REGION" \
            --certificate-arn "$CERTIFICATE_ARN" \
            --query "Certificate.Status" --output text)
        if [[ "$status" == "ISSUED" ]]; then
            echo ""
            ok "Certificate validated and issued!"
            return
        fi
        printf "\r  Waiting... %ds / %ds (status: %s)    " "$elapsed" "$max_wait" "$status"
        sleep 15
        elapsed=$((elapsed + 15))
    done

    echo ""
    warn "Certificate not validated within ${max_wait}s."
    warn "Deploying anyway — CloudFront will use its default *.cloudfront.net domain."
    warn "Once the cert is issued, redeploy with: cd infra && cdk deploy -c certificate_arn=$CERTIFICATE_ARN"
    # Clear certificate_arn so CDK deploys without custom domain
    CERTIFICATE_ARN=""
}

# ── Step 5: CDK Bootstrap ─────────────────────────────────────────────────
step_bootstrap() {
    header "Step 5/10: CDK bootstrap"
    local account_id
    account_id=$(aws sts get-caller-identity --query Account --output text)

    if aws cloudformation describe-stacks --stack-name CDKToolkit --region "$REGION" &>/dev/null; then
        ok "CDK already bootstrapped"
    else
        info "Bootstrapping CDK (one-time setup)..."
        cdk bootstrap "aws://${account_id}/${REGION}"
        ok "CDK bootstrapped"
    fi
}

# ── Step 6: Clean stale secrets ────────────────────────────────────────────
step_clean_secrets() {
    header "Step 6/10: Cleaning stale secrets"
    for secret in quantum-dns/ibm-token quantum-dns/redis-auth quantum-dns/openai-key; do
        # Force-delete any secrets stuck in scheduled-deletion from prior deploys
        local status
        status=$(aws secretsmanager describe-secret --secret-id "$secret" --region "$REGION" \
            --query "DeletedDate" --output text 2>/dev/null || echo "None")
        if [[ "$status" != "None" && -n "$status" ]]; then
            info "Removing stale secret: $secret"
            aws secretsmanager delete-secret --secret-id "$secret" \
                --force-delete-without-recovery --region "$REGION" 2>/dev/null || true
            sleep 2
        fi
    done
    ok "Secrets clean"
}

# ── Step 7: Install CDK deps ──────────────────────────────────────────────
step_cdk_deps() {
    header "Step 7/10: Installing CDK dependencies"
    cd "$INFRA_DIR"
    if [[ ! -d ".venv" ]]; then
        python3 -m venv .venv
    fi
    source .venv/bin/activate
    pip install -q -r requirements.txt
    ok "CDK dependencies installed"
}

# ── Step 8: CDK Deploy ────────────────────────────────────────────────────
step_deploy() {
    header "Step 8/10: Deploying stack (15-25 min on first deploy)"
    info "Building Docker image (liboqs from source — ~5-10 min first time)..."
    cd "$INFRA_DIR"
    source .venv/bin/activate

    local context_args=""
    if [[ -n "${CERTIFICATE_ARN:-}" ]]; then
        context_args="--context certificate_arn=$CERTIFICATE_ARN"
    fi

    # shellcheck disable=SC2086
    cdk deploy "$STACK_NAME" \
        $context_args \
        --require-approval never \
        --outputs-file "$PROJECT_ROOT/cdk-outputs.json"

    ok "Stack deployed successfully!"
}

# ── Step 9: Populate secrets + restart ECS ────────────────────────────────
step_post_deploy() {
    header "Step 9/10: Populating secrets & restarting service"

    if [[ -n "${IBM_QUANTUM_TOKEN:-}" ]]; then
        aws secretsmanager put-secret-value \
            --secret-id "quantum-dns/ibm-token" \
            --secret-string "$IBM_QUANTUM_TOKEN" \
            --region "$REGION" >/dev/null
        ok "IBM Quantum token set"
    fi

    if [[ -n "${OPENAI_API_KEY:-}" ]]; then
        aws secretsmanager put-secret-value \
            --secret-id "quantum-dns/openai-key" \
            --secret-string "$OPENAI_API_KEY" \
            --region "$REGION" >/dev/null
        ok "OpenAI API key set"
    fi

    # Force ECS to redeploy with the real secret values
    info "Restarting ECS service to pick up secrets..."
    local cluster_arn service_arn
    cluster_arn=$(aws ecs list-clusters --region "$REGION" \
        --query "clusterArns[?contains(@, 'QuantumDNSShield')]|[0]" --output text)
    if [[ -n "$cluster_arn" && "$cluster_arn" != "None" ]]; then
        service_arn=$(aws ecs list-services --cluster "$cluster_arn" --region "$REGION" \
            --query "serviceArns[0]" --output text)
        aws ecs update-service --cluster "$cluster_arn" --service "$service_arn" \
            --force-new-deployment --region "$REGION" >/dev/null
        ok "ECS service restarting with real secrets"
    else
        warn "Could not find ECS cluster — secrets will apply on next deployment"
    fi
}

# ── Step 10: Final DNS + Verification ─────────────────────────────────────
step_verify() {
    header "Step 10/10: Final setup & verification"

    # Read outputs
    local cf_domain alb_dns
    cf_domain=$(python3 -c "
import json
with open('$PROJECT_ROOT/cdk-outputs.json') as f:
    o = json.load(f)
print(o.get('$STACK_NAME', {}).get('CloudFrontDomain', 'UNKNOWN'))
")
    alb_dns=$(python3 -c "
import json
with open('$PROJECT_ROOT/cdk-outputs.json') as f:
    o = json.load(f)
print(o.get('$STACK_NAME', {}).get('ALBDnsName', 'UNKNOWN'))
")

    echo ""
    echo -e "${BOLD}╔══════════════════════════════════════════════════╗${NC}"
    echo -e "${BOLD}║  ADD THIS FINAL DNS RECORD IN NAMECHEAP         ║${NC}"
    echo -e "${BOLD}╠══════════════════════════════════════════════════╣${NC}"
    echo -e "║  Type:  ${GREEN}CNAME${NC}"
    echo -e "║  Host:  ${GREEN}qdns${NC}"
    echo -e "║  Value: ${GREEN}${cf_domain}${NC}"
    echo -e "║"
    echo -e "║  Namecheap → Domain List → valmohaugen.com"
    echo -e "║  → Advanced DNS → Add New Record"
    echo -e "${BOLD}╚══════════════════════════════════════════════════╝${NC}"
    echo ""

    # Smoke test against CloudFront
    info "Waiting for ECS task to become healthy (up to 3 min)..."
    local base_url="https://${cf_domain}"
    local attempts=0
    while [[ $attempts -lt 12 ]]; do
        if curl -sf "${base_url}/api/health" >/dev/null 2>&1; then
            ok "Health check passed!"
            local health
            health=$(curl -sf "${base_url}/api/health")
            echo "  $health"
            break
        fi
        attempts=$((attempts + 1))
        printf "\r  Waiting... attempt %d/12" "$attempts"
        sleep 15
    done
    echo ""

    if [[ $attempts -ge 12 ]]; then
        warn "Health check did not pass yet. The service may still be starting."
        echo "  Check logs: aws logs tail /ecs/quantum-dns --region $REGION --since 10m"
    fi

    echo ""
    echo -e "${BOLD}╔══════════════════════════════════════════════════╗${NC}"
    echo -e "${BOLD}║           DEPLOYMENT COMPLETE                   ║${NC}"
    echo -e "${BOLD}╠══════════════════════════════════════════════════╣${NC}"
    echo -e "║"
    echo -e "║  Dashboard:  ${GREEN}https://qdns.valmohaugen.com${NC}"
    echo -e "║  API:        ${GREEN}https://qdns.valmohaugen.com/api/health${NC}"
    echo -e "║  CloudFront: ${GREEN}https://${cf_domain}${NC}"
    echo -e "║"
    echo -e "║  Logs:"
    echo -e "║    aws logs tail /ecs/quantum-dns --region $REGION --follow"
    echo -e "║"
    echo -e "║  Teardown:"
    echo -e "║    bash scripts/teardown.sh"
    echo -e "║"
    echo -e "${BOLD}╚══════════════════════════════════════════════════╝${NC}"
    echo ""
}

# ── Main ──────────────────────────────────────────────────────────────────
main() {
    echo ""
    echo -e "${BOLD}╔══════════════════════════════════════════════════╗${NC}"
    echo -e "${BOLD}║     Quantum DNS Shield — Deploy to AWS          ║${NC}"
    echo -e "${BOLD}╚══════════════════════════════════════════════════╝${NC}"

    step_prereqs
    step_aws_config
    step_load_env
    step_request_cert
    step_bootstrap
    step_clean_secrets
    step_cdk_deps
    step_deploy
    step_post_deploy
    step_verify
}

main "$@"
