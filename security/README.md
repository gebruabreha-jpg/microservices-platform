# Security & Production Hardening

This directory contains Kubernetes manifests for securing the microservices platform.

## Contents

### cert-manager
TLS certificate automation using Let's Encrypt.

- `cluster-issuer.yaml` — ClusterIssuer for Let's Encrypt production
- `certificate.yaml` — Certificate resource for the platform domain

**Usage:**
```bash
kubectl apply -f security/cert-manager/
```

### external-secrets
External Secrets Operator integration with HashiCorp Vault.

- `cluster-secret-store.yaml` — ClusterSecretStore pointing to Vault
- `external-secret-order.yaml` — Example ExternalSecret for order-service

**Prerequisites:**
- External Secrets Operator installed
- Vault accessible at `https://vault.example.com`
- Kubernetes auth method configured in Vault
- ServiceAccount `external-secrets-sa` created in `external-secrets` namespace

**Usage:**
```bash
kubectl apply -f security/external-secrets/
```

### service-mesh/istio
Istio service mesh configuration for mTLS and traffic management.

- `peer-authentication.yaml` — Enforces STRICT mTLS across all services
- `destination-rules.yaml` — Connection pool and load balancing policies
- `sidecar.yaml` — Sidecar injection and egress policies
- `gateway.yaml` — Istio ingress gateway with TLS termination

**Prerequisites:**
- Istio installed with `auto-inject` annotation or `sidecar.istio.io/inject: "true"` label
- `istio-system` namespace exists
- Certificate secret `microservices-platform-tls` created by cert-manager

**Usage:**
```bash
kubectl apply -f security/service-mesh/istio/
```

## Deployment Order

1. Install cert-manager
2. Install External Secrets Operator
3. Install Istio
4. Apply `security/cert-manager/`
5. Apply `security/external-secrets/`
6. Apply `security/service-mesh/istio/`

## Notes

- Replace `example.com` with your actual domain
- Update Vault server URL in `cluster-secret-store.yaml`
- Ensure service accounts and RBAC are configured for external-secrets
- Istio mTLS requires all sidecars to be injected before enforcing STRICT mode
