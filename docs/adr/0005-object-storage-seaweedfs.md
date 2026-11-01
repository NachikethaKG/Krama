# 0005 — Artifacts stay on the local disk; SeaweedFS (not MinIO) when storage must be shared

- **Status:** accepted
- **Deciders:** Vishwas (research and decision, 2026-11-01), Nachiketha (review)
- **Issue:** #117 · Research: [`phase-5-vishwas-video-storage.md`](../research/phase-5-vishwas-video-storage.md),
  decisions D18–D20 in [`phase-5-decisions-alignment.md`](../research/phase-5-decisions-alignment.md)

## Context
`architecture.md` planned "local FS → S3/MinIO later" for the `ArtifactStore` port, and Phase 5 asked when to move,
now that videos are added.

- **MinIO's open-source repo is archived.** `minio/minio` says "THIS REPOSITORY IS NO LONGER MAINTAINED" and points
  to the commercial AIStor editions; the last community release is `RELEASE.2025-10-15T17-29-55Z` (AGPL-3.0). Checked
  on 2026-11-01.
- **Videos are small.** A 1080p H.264 CRF 18 export of real UI frames is ~5 MB per minute; a 6-step tutorial is
  ~2.4 MB. One run's rrweb recording is 9.3 MB, and all of `data/artifacts` is 553 MB for 136 workflows.
- Both laptops run the API, the arq worker and (in Phase 5) the renderer on one machine.

## Decision
1. **Keep `LocalFsStore` (`ARTIFACTS_DIR`) through Phase 5.** Disk size is handled by the export retention rule
   (#125: newest export per version and preset, 30 days, `EXPORTS_MAX_GB`), not by moving storage.
2. **Move to object storage when one of these happens:** the renderer or worker runs on a different machine from the
   API; we deploy somewhere with ephemeral disks; or downloads should be served from a bucket instead of the API.
3. **The target then is SeaweedFS** (Apache-2.0, S3 API, self-hosted, active: 4.51 on 2026-10-25), as an `S3Store`
   behind the same `ArtifactStore` port. No module outside `storage/` changes.
4. To keep that move cheap, the port grows in #120/#124's contract PRs with operations that map to S3: store a
   finished file, a way to serve it (a local path now, a presigned URL later), delete, and list/size a prefix.

## Alternatives considered
- **MinIO (last community release).** Archived and unmaintained; security fixes go to the commercial editions only.
  Rejected.
- **Garage** (AGPL-3.0, active). A fine S3 server, but AGPL, and its multi-node design is more than one laptop needs.
  Second choice.
- **Cloudflare R2** (10 GB-month, free egress). No container to run, but it's an external account, and whether it
  needs a payment method is unverified; Krama's rule is free tiers only. Kept as an option for a deploy.
- **Move to object storage now.** Nothing in Phase 5 needs it, and it would add a container on 16 GB laptops.

## Consequences
- Easier: nothing to run or configure in Phase 5; downloads are a `FileResponse` with HTTP Range support.
- Harder: everything that serves artifacts must use the port's serve operation, not a hard-coded file path, or the
  later move will touch more than `storage/`.
- `architecture.md` §3 and §4 say SeaweedFS instead of S3/MinIO (same PR as this ADR).
