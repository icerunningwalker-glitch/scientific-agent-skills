---
name: skin-transport-modeling
description: Reproduce, inspect, or adapt compartmental and finite-volume skin transport models with traceable parameters, dimensional checks, mass balance, and numerical comparison. Use for follicular reservoirs, tissue diffusion, uptake, and application/removal protocols; the included runner supports a TH21 reference model.
---

# Skin transport modeling

Deliver a reproducible forward-model run or a clearly specified model change, with input provenance, units, solver settings, output tables, and numerical acceptance evidence.

## Choose the model and evidence

- Locate the user's checkout and its model card, input table, sources, and existing verification entrypoint. Keep the requested mechanism and carrier identity explicit.
- For the packaged TH21 example, read [references/reference-model.md](references/reference-model.md). Its intended source repository is `https://github.com/icerunningwalker-glitch/tfna-ck-modeling`.. Verify availability before acquiring a checkout, and record its commit or archive hash. An existing local checkout works offline.
- For another carrier or tissue model, read [references/input-and-acceptance.md](references/input-and-acceptance.md). Map its actual equations, state variables, boundaries, and measurements before choosing a solver or reusing TH21 coefficients.

## Run and verify

1. Record the interpreter and required library versions; use the repository's declared environment when available. Report missing dependencies with their names. Install or change dependencies only within the user's authorization.
2. Identify mass states, counters, concentration denominators, initial dose, incoming flux, outgoing flux, and application cutoff. Check unit conversions against the parameter source map.
3. Choose a fresh output directory. Preserve reference inputs and reference results, then execute the existing forward-model entrypoint from an independent working directory.
4. Compare numerical outputs with the repository's reference and tolerances. Check nonempty tables, finite values, mass balance, minimum state, and source cutoff. For a model change, define acceptance from the changed equations and desired observables; compare grid and time accuracy when they affect the result.
5. Report the numerical outcome with parameter provenance, command, environment, code identity, elapsed time, and actual verification status. Use the output concentration definition directly in labels and interpretations.

For a checkout with `src/transport/run_model.py`, `src/transport/verify_results.py`, and the TH21 file layout, use the bundled helper:

```text
python <skill-dir>/scripts/reproduce_reference.py --repo <checkout> --output-dir <fresh-output-dir>
```

`--python <interpreter>` selects the environment for the model. The helper records dependency versions and file hashes, runs the model and verifier, and confirms that reference inputs, results, model metadata, logs, and source code remained unchanged. It performs no download or installation.

## Interpret results

Distinguish predicted extracellular carrier concentration, intact intracellular mass, cumulative uptake, retained carrier, and cargo-equivalent concentration. Keep calibration observations and forward predictions separately identified. A deterministic rate sweep is a sensitivity comparison; statistical uncertainty requires a specified distribution or replicated data and a corresponding analysis.

Read the reference's [scope and conditions](references/reference-model.md#scope-and-conditions) when discussing TH21 output or AI-designed tFNA candidates. Use candidate delivery claims only after a candidate-specific parameter map and forward calculation are available.
