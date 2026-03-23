# Gatekeeper — Docker install (pre-built image)

Use this folder if you want to run Gatekeeper **without cloning the repository** or building images locally.

## Prerequisites

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) (Mac/Windows) or Docker Engine + Compose on Linux

## Option A: One-line install (downloads this folder’s files from GitHub)

From an empty directory:

```bash
curl -fsSL https://raw.githubusercontent.com/iwegbue/gatekeeper/main/deploy/install.sh | bash
```

Optional environment variables:

| Variable | Default | Meaning |
|----------|---------|---------|
| `GATEKEEPER_REPO` | `iwegbue/gatekeeper` | GitHub `owner/repo` (forks can override) |
| `GATEKEEPER_REF` | `main` | Branch or tag (e.g. `v1.0.0`) to download compose files from |
| `GATEKEEPER_IMAGE` | (see `docker-compose.yml`) | Full image reference, e.g. `ghcr.io/iwegbue/gatekeeper:v1.0.0` |

## Option B: Release zip

Download **`gatekeeper-docker.zip`** from the [Releases](https://github.com/iwegbue/gatekeeper/releases) page, unzip, then:

```bash
docker compose pull
docker compose up -d
```

## After startup

Open **http://localhost** and complete the setup wizard (admin password).

## Pinning a version

Set in a `.env` file next to `docker-compose.yml`:

```env
GATEKEEPER_IMAGE=ghcr.io/iwegbue/gatekeeper:v1.0.0
```

Or export it before `docker compose up`:

```bash
export GATEKEEPER_IMAGE=ghcr.io/iwegbue/gatekeeper:v1.0.0
docker compose pull && docker compose up -d
```

## Container registry access

Images are published to **GitHub Container Registry** (`ghcr.io`). If pulls fail with “denied”, the package may be private — in GitHub: **Packages** → **gatekeeper** → **Package settings** → set visibility to **public** (or log in with `docker login ghcr.io`).
