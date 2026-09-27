# Docker

The Compose file lives at the repository root so this command works from a fresh clone:

```text
docker compose up -d --build
```

`docker-compose.gpu.yml` is an optional overlay for a Linux host with the NVIDIA Container Toolkit. CPU mode does not use it.
