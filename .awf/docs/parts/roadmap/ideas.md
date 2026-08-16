### Core evidence workbench

Build a standalone `labctl` backend with versioned experiment and result schemas, then expose narrow Pi tools for mathematical checks, simulation verification, and controlled benchmark comparison. Establish clean-process execution, environment fingerprinting, artifact retention, resource limits, and one shared verdict envelope before adding specialized checks.

Package the workbench for project-local installation and version pinning first, while retaining an optional user-level installation. Define deterministic discovery and precedence so project-local configuration, skills, schemas, and backend selection override user defaults and every run records the effective source.

Candidate Python capabilities include SymPy and arbitrary-precision numerics for independent mathematical checks, Pint for dimensions, Hypothesis for generated properties, NumPy and SciPy for reference calculations, and pyperf for benchmark measurement. Adopt each dependency only with the capability that requires it.

### Simulation evidence

Support readable reference implementations, invariant and monotonicity checks, refinement studies, observed convergence order, symmetry and metamorphic properties, deterministic seed capture, distribution-aware stochastic validation, and finite-value or range checks. Compare full state and error distributions rather than only aggregate means.

### Performance evidence

Add geometric workload scaling, uncertainty-aware A/B comparisons, stable environment capture, and separation of startup, warmup, compilation, steady state, and teardown. Add Hyperfine and system counter adapters where portable command benchmarking or hardware evidence is needed. Add Rust adapters for Criterion, Iai-Callgrind, and Proptest when a Rust workload exists.

### Exploration and diagnosis

Add an explicitly non-evidentiary persistent scratch environment. Add compact CPU, memory, instruction, and GPU profiling summaries only after benchmarks identify a reproducible bottleneck; retain full traces as artifacts rather than model context.
