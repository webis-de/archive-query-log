# Backend Kubernetes Deployment

Deploy the AQL backend (FastAPI) to the Webis Kubernetes cluster.

## Prerequisites

1. **VPN Connection**: Connect to the Webis VPN
2. **kubectl configured**: Run the credential commands to configure kubectl
3. **Docker image pushed**: Build and push the backend image to a registry

## Files

```
k8s/
├── kustomization.yaml  # Deploy all with one command
├── configmap.yaml      # ES_HOST, ES_VERIFY, ENVIRONMENT
├── secret.yaml         # ES_API_KEY (needs your actual value)
├── deployment.yaml     # Pod configuration
└── service.yaml        # Internal ClusterIP service
```

## Before Deploying

### 1. Update the image name

Edit `deployment.yaml` and replace `YOUR_DOCKERHUB_USERNAME`:

```yaml
image: docker.io/yourusername/aql-backend:latest
```

### 2. Configure the secret

Encode your Elasticsearch API key:

```bash
echo -n 'your-actual-api-key' | base64
```

Update `secret.yaml` with the encoded value.

### 3. Verify Elasticsearch host

Check `configmap.yaml` has the correct `ES_HOST` value.

## Build & Push Image

```bash
# From the backend directory
docker build -t yourusername/aql-backend:latest .
docker push yourusername/aql-backend:latest
```

## Deploy

```bash
# Preview what will be applied
kubectl kustomize k8s/

# Apply all resources
kubectl apply -k k8s/
```

## Verify

```bash
# Check deployment
kubectl get deployments -n user-ajjxp

# Check pods
kubectl get pods -n user-ajjxp

# View logs
kubectl logs -f deployment/aql-backend -n user-ajjxp

# Port forward for local testing
kubectl port-forward service/aql-backend 8000:8000 -n user-ajjxp
```

## Update Deployment

After pushing a new image:

```bash
kubectl rollout restart deployment/aql-backend -n user-ajjxp
kubectl rollout status deployment/aql-backend -n user-ajjxp
```

## Delete

```bash
kubectl delete -k k8s/
```

## Notes

- Deploy the backend **before** the frontend (frontend proxies to backend)
- The service is only accessible within the cluster (ClusterIP)
- The frontend's nginx proxies `/api/*` requests to `aql-backend:8000`
