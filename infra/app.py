#!/usr/bin/env python3
"""CDK app entry point for Quantum DNS Shield."""

from aws_cdk import App
from stacks.quantum_dns_stack import QuantumDNSStack

app = App()
QuantumDNSStack(app, "QuantumDNSShield", env={"region": "us-east-1"})
app.synth()
