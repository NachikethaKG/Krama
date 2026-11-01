# Video storage: MP4 size per minute, and when to leave the local disk

- **Phase:** 5
- **Researched by:** Vishwas (research and checks run by Claude Code on Vishwas's laptop, 2026-11-01; decisions by Vishwas)
- **Question(s):** **Storage:** typical MP4 size per minute at 1080p. When should we move from local files to S3/MinIO?

## Findings

### MP4 size [verified locally: `assets/phase-5-vishwas-checks/mp4_size.py`, `results-mp4.json`]

There's no renderer yet (Remotion is Nachiketha's #122/#126), so this builds a stand-in from real frames: the 6 step
screenshots of a real GitHub run (1280×800), 10 scenes × 6 s. Each scene zooms 1.0 → 1.4 over 1.5 s while a
cursor glides across, plus the narration track (AAC 96 kb/s). It's then encoded with libx264 from the bundled FFmpeg
7.1. Remotion's default codec is H.264 with **CRF 18** (range 1–51) [verified: remotion.dev/docs/encoding].

| Output | CRF / preset | MB per minute | Encode s per minute | × real time |
|---|---|---|---|---|
| 16:9 1920×1080 | **18 / medium** | **5.2** | 7.0 | 8.6 |
| 16:9 1920×1080 | 23 / medium | 3.4 | 6.8 | 8.8 |
| 16:9 1920×1080 | 23 / veryfast | 3.2 | 4.7 | 12.9 |
| 16:9 1920×1080 | 28 / medium | 2.5 | 6.5 | 9.2 |
| 16:9 1280×720 | 18 / medium | 3.4 | 4.4 | 13.6 |
| 9:16 1080×1920 (centre crop) | 18 / medium | 3.5 | 8.0 | 7.5 |

- **About 5 MB per minute at 1080p, CRF 18.** UI video is mostly still, so H.264 compresses it very well. A typical
  6-step tutorial is ~28 s, so **~2.4 MB per export**, both aspect ratios ~4 MB. Encode times are x264 only; Remotion's
  frame rendering will take far longer (#118 measures it).
- For scale: one run's rrweb recording is 9.3 MB (the label run), and `data/artifacts` holds **553 MB** for 136
  workflows [verified locally: `du`]. Exports will be a small share of disk.
- The 9:16 centre crop of the labels page showed only the description column and cut off the labels, which is why
  9:16 must follow the highlight (decision in `phase-5-decisions-alignment.md`).

### What the storage code can do today [verified by reading `app/ports/artifacts.py`, `app/ports/models.py`, `app/storage/local.py`, `app/api/artifacts.py`]

- `ArtifactStore` has `put(key, bytes, content_type)`, `get(key) -> bytes`, `exists(key)`. No delete, no listing,
  no size total, no streaming.
- `ArtifactContentType` is `image/png | image/jpeg | application/json`. MP4, WAV and VTT aren't allowed, and
  `sniff_content_type` would serve them as JSON.
- `GET /artifacts/{key}` returns the whole file as one `Response(bytes)`. A browser `<video>` needs HTTP Range
  requests to seek.
- Starlette 1.7.0 / FastAPI 0.142.2 `FileResponse` handles Range: full GET → 200 with `accept-ranges: bytes`,
  `Range: bytes=1000-1999` → **206** with `content-range`, out-of-range → **416**, and `filename=` sets
  `Content-Disposition: attachment` [verified locally on a 5.2 MB MP4].
- The export job (Node/Remotion) writes a file on disk. Reading 5–50 MB into Python just to `put` the bytes would
  work, but a "store this file" path (move/copy) is simpler and uses less memory.

### When to leave the local disk

- **MinIO is no longer an option as planned.** The `minio/minio` repo is **archived**; its README says "THIS
  REPOSITORY IS NO LONGER MAINTAINED" and points to the commercial "AIStor" editions. The last community release is
  `RELEASE.2025-10-15T17-29-55Z`, license AGPL-3.0 [verified: GitHub API + README, 2026-11-01].
- Alternatives with an S3 API:

  | Option | License / cost | Status |
  |---|---|---|
  | SeaweedFS | Apache-2.0, self-hosted | active: 4.51 on 2026-10-25 [verified: GitHub API] |
  | Garage | AGPL-3.0, self-hosted | active: v2.5.0 on 2026-10-24 [verified: git.deuxfleurs.fr API] |
  | Cloudflare R2 | 10 GB-month, 1 M class A + 10 M class B ops free, **egress free** [verified: developers.cloudflare.com/r2/pricing] | hosted; payment method requirement [unverified] |

- Disk size isn't the reason to move (above). The reasons would be:
  1. the renderer runs on a **different machine** from the API (both would need to read and write the same files);
  2. we **deploy** somewhere with ephemeral disks;
  3. we want downloads served from a bucket/CDN instead of the API process.
  None of these happen in Phase 5: both laptops run API, worker and renderer on one machine.

## Recommendation

Decided by Vishwas on 2026-11-01:

1. **Stay on `LocalFsStore` for Phase 5.** When one of the three triggers above happens, move to **SeaweedFS**
   (Apache-2.0) behind the same port. **NEEDS ADR**: architecture.md says "S3/MinIO later" (mock seams table, `storage/`
   row), and MinIO OSS is archived.
2. **Port changes for #124/#125 (contract-change PR, both owners):**
   - `ArtifactContentType` += `video/mp4`, `audio/wav`, `text/vtt`;
   - `put_file(key, path, content_type)` (move a finished file into the store), `open_path(key)` or `local_path(key)`
     for `FileResponse` (with S3 later this becomes a presigned URL), `delete(key)`, and a way to list/size a prefix
     for cleanup.
3. **Download = `FileResponse`** with Range support and `Content-Disposition: attachment; filename="<title>.mp4"`.
   Encode with `-movflags +faststart` (index at the front, so playback starts before the download finishes). That's an
   FFmpeg/Remotion setting for #122/#126.
4. **Retention (#125):** keep the newest `ready` export per (workflow version, preset). Delete the others after **30
   days**, delete oldest-first above **`EXPORTS_MAX_GB` (default 5)**, and delete a failed export's partial file
   right away. The row stays, marked `expired`. Cleanup runs as an arq cron job.

## Open questions

- Real Remotion output size: Remotion renders sharper text and real cursor motion; re-measure MB/min on the first
  real export (#126) and update this note if it's far from 5 MB/min.
- Whether Remotion writes `+faststart` by default [unverified].
- Narration clips: WAV is ~44 KB/s (22.05 kHz, 16-bit mono), ~0.9 MB for a 6-step tutorial. They're cached and shared
  between versions, so they need their own cleanup rule (e.g. delete clips no manifest references for 30 days).

## Links
- https://www.remotion.dev/docs/encoding
- https://github.com/minio/minio (archived)
- https://github.com/seaweedfs/seaweedfs
- https://git.deuxfleurs.fr/Deuxfleurs/garage
- https://developers.cloudflare.com/r2/pricing/
- https://www.starlette.io/responses/#fileresponse
