# SIH26143 Maritime Oil-Spill Attribution

Project scaffold for the SIH26143 oil-spill detection and vessel attribution workflow. The architecture and implementation guide describe the intended system; this repository currently contains the documentation and folder structure for implementation.

## Project documentation

- [Architecture](./ai-ml-maritime-oil-spill-architecture.md)
- [Implementation guide](./documation.md)

## Repository layout

- `frontend/` — investigator case workspace, pipeline monitor, map, and evidence review UI.
- `backend/` — analyst-facing FastAPI API, domain/application logic, persistence, clients, and workers.
- `services/` — separate FastAPI services for slick detection, drift hindcasting, and AIS correlation.
- `data/` — sample and expected fixture data. Keep large or licensed source datasets out of Git unless their terms explicitly permit redistribution.
- `docs/api-contracts/` — backend and AI-service API specifications.
- `infra/` — local/deployment configuration for PostgreSQL, object storage, and monitoring.

The `.gitkeep` files preserve empty implementation directories in Git and can be removed as real files are added.
