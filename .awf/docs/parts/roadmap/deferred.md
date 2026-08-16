### Neural-network verification

Defer PyTorch-oriented gradient, tiny-batch learning, reproducibility, memory, throughput, and operator-profile checks until the shared experiment and result contracts are stable. Revisit when a concrete neural workload can validate the design.

### GPU execution

Defer a pinned ROCm environment and explicit GPU permission model until CPU confinement and environment fingerprints are reliable. Revisit with a supported target GPU and a reproducible container-host compatibility test.

### Formal proof and interoperability

Defer Lean-backed proof checks and an MCP adapter until core Pi tools demonstrate a need that symbolic, numeric, and constraint checks or the native extension boundary cannot meet.