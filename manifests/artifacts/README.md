# manifests/artifacts

One `<bench>-<run-id>.manifest.json` per run whose raw outputs live in the
fleet artifact store (`klt artifact put --manifest ...`). Every entry's `uri`
starts with `artifact:`; entry names keep the `<corner-id>` so per-corner
results stay separable. Manifests name no endpoint, bucket or account.

Check locally: `python3 scripts/check_artifact_manifests.py`
Verify bytes (needs the broker): `klt artifact verify <manifest>`
