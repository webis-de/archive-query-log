# Frontend Kubernetes Deployment

Deploy the AQL frontend (Angular + Nginx) to the Webis Kubernetes cluster.

## Prerequisites

1. **VPN Connection**: Connect to the Webis VPN
2. **kubectl configured**: Run the credential commands to configure kubectl
3. **Backend deployed**: The backend must be deployed first
4. **Docker image pushed**: Build and push the frontend image to a registry

## Files

```
k8s/
├── kustomization.yaml  # Deploy all with one command
├── configmap.yaml      # Nginx configuration (with /api proxy)
├── deployment.yaml     # Pod configuration
├── service.yaml        # Internal ClusterIP service
└── ingress.yaml        # External access configuration
```

## Before Deploying

### 1. Image name

The deployment uses the Uni Jena GitLab Container Registry (pushed automatically by CI):

```yaml
image: git.uni-jena.de:5050/fusion/teaching/project/2025wise/swep/aql-browser/aql-frontend:latest
```

### 2. Confirm the ingress hostname

Ask the product owner for the correct domain and update `ingress.yaml`:

```yaml
- host: aql.user-ajjxp.k8s.webis.de
```

## Build & Push Image

The CI pipeline automatically builds and pushes the image on every commit to main.

To pull the image manually:

```bash
# Login to GitLab registry (if needed)
docker login git.uni-jena.de:5050

# Pull the image
docker pull git.uni-jena.de:5050/fusion/teaching/project/2025wise/swep/aql-browser/aql-frontend:latest
```

To build and push manually:

```bash
# From the aql-frontend directory
docker build -t git.uni-jena.de:5050/fusion/teaching/project/2025wise/swep/aql-browser/aql-frontend:latest .
docker push git.uni-jena.de:5050/fusion/teaching/project/2025wise/swep/aql-browser/aql-frontend:latest
```

## Deploy

**Important**: Deploy the backend first!

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

# Check ingress
kubectl get ingress -n user-ajjxp

# View logs
kubectl logs -f deployment/aql-frontend -n user-ajjxp

# Port forward for local testing
kubectl port-forward service/aql-frontend 4200:80 -n user-ajjxp
```

## Update Deployment

After pushing a new image:

```bash
kubectl rollout restart deployment/aql-frontend -n user-ajjxp
kubectl rollout status deployment/aql-frontend -n user-ajjxp
```

## Delete

```bash
kubectl delete -k k8s/
```

## Architecture

```
Internet (via VPN)
       │
       ▼
┌─────────────┐
│   Ingress   │  aql.user-ajjxp.k8s.webis.de
└──────┬──────┘
       │
       ▼
┌─────────────┐        ┌─────────────┐
│  Frontend   │───────►│   Backend   │
│   (nginx)   │ /api/* │  (FastAPI)  │
│    :80      │        │   :8000     │
└─────────────┘        └─────────────┘
```

## Notes

- The nginx config proxies `/api/*` requests to `aql-backend:8000`
- Make sure the backend is deployed and running before the frontend
- The frontend uses `/api` as the `apiUrl` in production (`environment.prod.ts`)
