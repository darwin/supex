# Contracts Reference

Schema and example payloads for Supex protocol contracts.

## Layout

- `v1/` - Versioned JSON Schema documents (canonical machine contracts)
- `examples/` - Example request/response/error payloads

## v1 Schemas

- `v1/handshake.schema.json`
- `v1/tools-call.schema.json`
- `v1/error-envelope.schema.json`
- `v1/artifact-manifest.schema.json`
- `v1/vcad-tools-results.schema.json`
- `v1/viewer-relay.schema.json`

## Examples

- Handshake: `examples/handshake.ok.json`, `examples/handshake.protocol-mismatch.json`
- Tool results: `examples/vcad_place.success.json`, `examples/vcad_place.error.json`
- Viewer relay: `examples/viewer.ready.ok.json`, `examples/scene.snapshot.ok.json`
- Artifact outcomes: `examples/artifact.applied.json`, `examples/artifact.superseded.json`, `examples/artifact.stale_dropped.json`
- Error envelopes: `examples/error.*.json`

## Notes

- Use `v1/` schemas as the source of truth when implementing clients.
- Example files are illustrative and may omit fields that are optional in schema.
