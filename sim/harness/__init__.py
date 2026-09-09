"""sim/harness -- shared PDK-resolution and record-writing machinery.

This is a deliberately small package: it ports the *shape* of the public
gf180-bandgap canary's ``sim/harness`` (record-id / corner-id conventions,
PDK resolution, git provenance) into this repo, not that repo's spec-line
test suite. See ``sim/README.md`` for the convention this package implements
and ``sim/cell-device-characterization/README.md`` for the first (and so
far only) consumer.
"""
