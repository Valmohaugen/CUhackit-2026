#!/usr/bin/env bash
# ============================================================================
#  Quantum DNS Shield — Teardown
#
#  Destroys all AWS resources created by deploy.sh
# ============================================================================
set -euo pipefail

DOMAIN="qdns.valmohaugen.com"
REGION="us-east-1"
STACK_NAME="QuantumDNSShield"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
INFRA_DIR="$PROJECT_ROOT/infra"

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
BOLD='\033[1m'; NC='\033[0m'

echo ""
echo -e "${RED}${BOLD}This will DESTROY all AWS resources for Quantum DNS Shield.${NC}"
echo "  Stack:  $STACK_NAME"
echo "  Region: $REGION"
echo ""
read -rp "Are you sure? Type 'yes' to confirm: " confirm
if [[ "$confirm" != "yes" ]]; then
    echo "Aborted."
    exit 0
fi

echo ""

# CDK destroy
echo -e "${YELLOW}[1/3]${NC} Destroying CDK stack..."
cd "$INFRA_DIR"
if [[ -d ".venv" ]]; then
    source .venv/bin/activate
fi
cdk destroy "$STACK_NAME" --force
echo -e "${GREEN}[ OK ]${NC}  Stack destroyed"

# Clean up Secrets Manager (bypass 7-day recovery window)
echo -e "${YELLOW}[2/3]${NC} Cleaning up Secrets Manager..."
for secret in quantum-dns/ibm-token quantum-dns/redis-auth quantum-dns/openai-key; do
    aws secretsmanager delete-secret --secret-id "$secret" \
        --force-delete-without-recovery --region "$REGION" 2>/dev/null || true
done
echo -e "${GREEN}[ OK ]${NC}  Secrets deleted"

# Clean up ACM certificate
echo -e "${YELLOW}[3/3]${NC} Cleaning up ACM certificate..."
cert_arn=$(aws acm list-certificates --region "$REGION" \
    --query "CertificateSummaryList[?DomainName=='$DOMAIN'].CertificateArn | [0]" \
    --output text 2>/dev/null || echo "None")
if [[ "$cert_arn" != "None" && -n "$cert_arn" ]]; then
    aws acm delete-certificate --certificate-arn "$cert_arn" --region "$REGION" 2>/dev/null || true
    echo -e "${GREEN}[ OK ]${NC}  Certificate deleted"
else
    echo -e "${GREEN}[ OK ]${NC}  No certificate found"
fi

# Clean up local artifacts
rm -f "$PROJECT_ROOT/cdk-outputs.json"

echo ""
echo -e "${GREEN}${BOLD}All AWS resources destroyed.${NC}"
echo ""
echo -e "${YELLOW}MANUAL CLEANUP in Namecheap:${NC}"
echo "  1. Remove CNAME record for 'qdns' (pointing to CloudFront)"
echo "  2. Remove the ACM validation CNAME record (_xxx.qdns)"
echo ""
