# Auditor worker handoff: Python and klt for `signoff/verify.sh` (issue #84)

Status: discovery complete; provisioning NOT done; tracked destination is a
DRAFT (section 5) and has not been filed. Nothing here claims a repair.

Scope: worker deployment discovery only. No design content.

## 1. Affected worker and what it actually runs

Observed read-only on 2026-10-09 from the dispatch host (`hostname` =
`loom-worker-1`, user `ubuntu`, docker CLI reachable). Only non-secret
metadata was read (`docker inspect --format` with explicit fields,
`docker image inspect`, `docker exec ... command -v`). No environment
variables or credentials were dumped.

| Fact | Value |
|---|---|
| Container | `676b7360dbea` (full id `676b7360dbead23c12bd6c9b713baa83ef2bd913729bc6072db560d0b85a5a29`), name `loom-codex-session-agent-5`, state `running`, container user `loom`; created 2026-10-07T10:53:35Z. Not retired. |
| Configured image | `ghcr.io/rjwalters/loom-worker-session:latest` |
| Immutable image id | `sha256:ed61e8606052db44969e9553064b74fa8ec25b30a226f92fa1d0994e3d717741` (image created 2026-10-02T22:39:47Z; RepoDigest `ghcr.io/rjwalters/loom-worker-session@sha256:ed61e8606052db44969e9553064b74fa8ec25b30a226f92fa1d0994e3d717741`; label `org.opencontainers.image.version=24.04`, which is the Ubuntu base, not the loom release) |
| Tools inside the container | `docker exec 676b7360dbea sh -c 'id -un; command -v python3; command -v klt'` prints only `loom`; neither command resolves. `/opt/eda` does not exist; PATH has no `/opt/eda` entry. |
| Sibling containers | All 7 containers on this host (`docker ps -a`) use the same image `ghcr.io/rjwalters/loom-worker-session:latest`, id `ed61e8606052`. |

So the deployed image for the failing worker is the generic
`loom-worker-session` layer, not the EDA overlay. This matches the issue's
"verified correction": user `loom`, no `python3` and no `klt` on PATH. (The
host itself, outside any container, does have `/usr/bin/python3` 3.12.3 and
`~/.local/bin/klt` 0.7.0+g6440221f9207; those are host-wide tools provisioned
by the worker spec and are not what a containerized Auditor sees. A correct
tool version on a different host does not satisfy this issue.)

Caveat on "Auditor worker": the original reports came from Auditor sessions
that may have run on other hosts or other containers. This record maps only
container `676b7360dbea` on `loom-worker-1`. Any other Auditor host remains
unmapped until the execution owner checks it with the same commands.

## 2. Candidate images versus deployed image

| Image | Role | Evidence | Deployed for this worker? |
|---|---|---|---|
| `ghcr.io/rjwalters/loom-worker-session` (`:latest` -> `sha256:ed61e860...`) | Persistent per-account session layer; Loom `docker/session/README.md` | `docker inspect` above | YES (observed) |
| `ghcr.io/rjwalters/loom-worker` | Generic base; Ubuntu 24.04, bare `python3` only "because the managed gh launcher is a Python 3 script"; explicitly no domain toolchain (Loom `docker/worker/README.md`) | Local image `ghcr.io/rjwalters/loom-worker:latest` (`3e9c10689378`) exists on host but no container uses it | No |
| `ghcr.io/2amlogic/eda-sim:<version>` | Domain overlay `FROM loom-worker`; bakes ngspice, xschem, ciel, klt in `/opt/eda/venv`; `ENV PATH=/opt/eda/venv/bin:...` (klayout-tools `docker/eda-sim/README.md`, `Dockerfile` line ~192) | Not present in `docker images`; no running container | No. CANDIDATE only. |

Note on the base image: the Loom worker README states `python3` is present in
`loom-worker`, yet it does not resolve inside the session container. Whether
the session layer or its `:latest` build dropped it is not established here;
treat it as an open observation for the execution owner (do not assume the
README holds for this image).

## 3. Source revisions consulted

| Source | Path | Revision |
|---|---|---|
| Loom checkout (`cat .loom/loom-source-path` -> `/home/ubuntu/GitHub/loom`) | `docker/README.md`, `docker/worker/README.md`, `docker/session/README.md` | `36a76eeb2` (`v0.19.971-10-g36a76eeb2`); the issue text cited `fabe6521f7f5`, local checkout has since moved |
| Session launcher (default image constant) | `/home/ubuntu/GitHub/loom/loom-daemon/src/tokens_pool/session_lifecycle.rs` line 93: `DEFAULT_SESSION_IMAGE = "ghcr.io/rjwalters/loom-worker-session:latest"` | `36a76eeb2` |
| Worker host spec / session start procedure | `/home/ubuntu/GitHub/2am/infra/aws/loom-worker/new-worker.md` (step 4: `loom-daemon accounts session start <profile> --mount-workspace ~/GitHub`, image `...loom-worker-session:latest`); host provisioning in `provision.sh`, `worker.env`, `PROVENANCE.md` | 2am checkout `ef0e84714b5a0fdade4ad707194cbeb943692666` |
| Domain image source | `/home/ubuntu/GitHub/klayout-tools/docker/eda-sim/{README.md,Dockerfile}` (upstream https://github.com/2AMLogic/klayout-tools/tree/main/docker/eda-sim) | `a6d9b8dcb6584c4908466e65210b6cc8c07ab9e8` |

Evidence chain: container `676b7360dbea` -> Config.Image `...loom-worker-session:latest`
-> image id `sha256:ed61e860...` -> the launcher's `DEFAULT_SESSION_IMAGE`
constant (same tag) -> started per the worker-spec procedure with no
override recorded. The launcher source revision that actually started the
container (2026-10-07) is NOT recorded in container metadata; `36a76eeb2` is the
current checkout, not proven to equal the revision at start time. Remaining
mapping gap: which release of Loom built `:latest` at digest `ed61e860...`
(registry digest/tag lookup against ghcr.io was not performed; it needs
registry access or the release workflow run for image created 2026-10-02).

## 4. Which party needs to change what

- The session image is generic by design; its owner (Loom) documents that
  domain toolchains are downstream layers. Adding klt to it would contradict
  that contract, so a Loom image change is not the default ask.
- The domain image owner is klayout-tools (`eda-sim` already provides Python
  and klt on PATH via `/opt/eda/venv`). It needs no change for this
  purpose unless the execution owner finds `eda-sim` unsuitable
  (it is `FROM loom-worker`, not `FROM loom-worker-session`, and is
  not currently built into the session layer). Open question for the owner:
  whether session containers can be launched from `eda-sim` or an equivalent
  overlay, or whether the Auditor should run `signoff/verify.sh` through a
  separate one-off `docker run` of `eda-sim`.
- Launcher image selection (per-account/session image override, or a
  separate Auditor seat image) is fleet-infrastructure territory: the
  launcher defaults to `loom-worker-session:latest`
  (`session_lifecycle.rs` line 93; an image override parameter exists at
  lines ~1133/1161 of that file).
- Therefore the execution owner is fleet infrastructure (worker image /
  launcher provisioning), consulting klayout-tools for the klt-bearing image.
- Related but distinct: klayout-tools issue
  https://github.com/2AMLogic/klayout-tools/issues/2829 (open, "portable
  Python runtime on Linux audit host") is a different Auditor request about a
  macOS-created `.venv` and a host without `uv`/`python3`. It overlaps in
  theme and could share a fix, but it is not this ticket and does not carry
  the requirements below; it is not accepted as the tracked destination.
  No existing ticket found by read-only search covers this deployment.
- This repo's #71 (closed) concerned Python for simulation-runner smoke checks;
  interpreter provisioning here must be coordinated with that earlier
  outcome so the two fixes do not diverge.

## 5. Tracked handoff destination (DRAFT, NOT FILED)

Filing requires the operator or the authorized fleet issue-filing workflow.
This agent was told not to file in external repos. The draft below is ready
to file. Until it exists with a link recorded here, the destination is
unresolved and issue #84 must not be treated as complete.

- Owner / role: fleet infrastructure (worker image and launcher
  provisioning), with klayout-tools consulted for the klt image.
- Suggested home: the repository holding the worker-spec and launcher
  provisioning (path found: `/home/ubuntu/GitHub/2am/infra/aws/loom-worker/`).
- Link: PENDING (to be filled in by whoever files it).

### Draft ticket

Title: `Auditor containers lack python3 and klt on PATH: provision a klt-capable Auditor environment`

Body:

> **Problem.** Auditor sessions cannot run a repository's signoff verification
> (`bash signoff/verify.sh`) because `python3` and `klt` do not resolve on PATH.
> Verified 2026-10-09 on host `loom-worker-1`: container `676b7360dbea`
> (`loom-codex-session-agent-5`, user `loom`) runs
> `ghcr.io/rjwalters/loom-worker-session:latest`, image id
> `sha256:ed61e8606052db44969e9553064b74fa8ec25b30a226f92fa1d0994e3d717741`;
> `command -v python3` and `command -v klt` print nothing; `/opt/eda` is
> absent. All 7 containers on the host use the same image. The EDA overlay
> `ghcr.io/2amlogic/eda-sim` (Python and klt on PATH via `/opt/eda/venv`) is a
> candidate, not deployed.
>
> **Decision needed from the owner.** Which of: (a) launch Auditor seats from
> an image that carries the domain toolchain (eda-sim or equivalent, noting it
> derives from `loom-worker`, not `loom-worker-session`); (b) run verification
> in a separate `eda-sim` container; (c) another mechanism. Do not add domain
> tooling to the generic session image without an owner decision. Also
> establish why bare `python3` documented for `loom-worker` is absent in the
> session container, and which Loom release built digest `ed61e860...`.
>
> **Scope of this ticket.** Persistent provisioning and live verification.
> Coordinate interpreter provisioning with the earlier Python request
> (gf180-antifuse #71, closed) and the related klayout-tools #2829.
>
> **Acceptance criteria (all required; completion and live verification live
> on this ticket).**
> 1. In a newly launched Auditor worker (not a hand-patched existing one),
>    `command -v python3` and `command -v klt` resolve on the ordinary PATH
>    for the Auditor's user, without sourcing extra files or activating a
>    venv by hand.
> 2. Tool provenance recorded: image digest, source revision of the launcher
>    and image build, `python3 --version`, `klt --version` (full build
>    string, including git commit), and where each binary comes from.
> 3. The klt build is compatible with the repository's committed verdict.
>    Re-read `signoff/README.md` and `signoff/report.json` at execution time
>    for the currently required build (PR #85 may change it; the README as of
>    this record pins klayout-tools commit
>    `32f69f81168217e8bc05dab97666f6806aa56424`, `0.5.0+g32f69f811682`, and
>    states the published PyPI 0.5.0 release cannot reproduce the report).
>    Do not assume a newer klt (host currently has 0.7.0+g6440221f9207) is
>    compatible: a different checklist changes the report bytes.
> 4. From a clean checkout of the repository at `origin/main`, run
>    `bash signoff/verify.sh` and attach complete stdout, stderr, and exit
>    status.
> 5. Pass condition: exit status 0 and confirmation that the committed
>    verdict (`signoff/report.json`) matches the regenerated one. The grader
>    exit status 3 and an incomplete T1 verdict are ACCEPTABLE (that is the
>    committed state). FAILURES: a missing command, grader exit 1 or 2, any
>    Python failure/traceback, or any report drift (byte-level difference).
> 6. Preserve the committed `signoff/manifest.json`, `signoff/report.json`,
>    and the repository's stated claim. Do not edit, regenerate-and-commit,
>    or hand-adjust them to make verification pass.
> 7. Do not install or modify host-wide tools on shared workers to satisfy
>    this; the fix is a change to the worker/image spec.
> 8. Close only after the above is shown on a freshly launched worker.

### Possible klayout-tools tool-gap issue (DRAFT, only if warranted, NOT FILED)

Not clearly warranted: klayout-tools already ships the needed image. If the
execution owner finds a real gap, a generic issue could read: "Provide a
documented way to layer the eda-sim toolchain onto a session-style
(persistent-container) base, or to run `klt` from an environment where only a
bare interpreter is available". No design detail and no mention of this
repository should appear in it.

## 6. Downstream requirements (retained for the execution owner)

1. Python and klt on the ordinary PATH in a newly launched Auditor worker.
2. Tool provenance (image digest, source revisions, versions, origin).
3. Clean-checkout `bash signoff/verify.sh` full stdout, stderr, exit status.
4. Pass: exit 0 and committed-verdict match. Acceptable: grader exit 3 and
   incomplete T1. Failure: missing commands, grader exit 1 or 2, Python
   failures, report drift.
5. Re-read `signoff/README.md` and `signoff/report.json` for the current
   compatible build (PR #85 may change it) before choosing the klt build.
6. Preserve the committed manifest, report, and claim.
7. Coordinate interpreter provisioning with #71.

## 7. Open items

- Tracked destination not filed (needs operator / authorized fleet workflow).
- Digest `ed61e860...` to Loom release mapping not looked up (no registry query).
- Launcher revision at container start time (2026-10-07) not recorded.
- Other Auditor hosts, if any, unmapped.
- Origin of the original reports ("Python missing") versus the present
  observation (host has Python; container does not) not reconciled.
- Provisioning and fresh-worker verification: not started.
