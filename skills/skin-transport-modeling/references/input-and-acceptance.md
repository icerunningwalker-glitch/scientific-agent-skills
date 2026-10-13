# Input contract and model-change acceptance

For another skin transport implementation, build a parameter map from the user's actual inputs rather than copying the TH21 defaults. A useful record has one row per parameter:

| Field | Required content |
|---|---|
| `parameter` | Exact code field or symbol |
| `value` | Supplied or estimated numeric value |
| `unit` | Dimension and scale, including per-area/per-volume basis |
| `role` | Measured, fitted, design condition, geometric conversion, or numerical setting |
| `source` | Dataset/file or DOI with location and version |
| `transformation` | Equation or unit conversion from source to model |

Specify layer edges and porosities, particle/cargo identity, spatial grid, initial mass, supply/removal schedule, transport coefficients, degradation and uptake rates, output time grid, and target endpoint when used. Check positivity of physical scales, ordered layer edges, probabilities/fractions within their stated range, and nonzero denominators used by the equations. Specify uncertainty distributions only when supported by observations or an explicitly requested scenario analysis.

For acceptance, derive the mass ledger from the actual state vector: initial intact and fragment mass plus cumulative supplied mass equals current intact and fragment mass plus cumulative boundary loss. Exclude event counters such as cumulative uptake from total mass. Use an absolute threshold when the initial dose is zero; a relative residual then has no denominator.

Use a manufactured solution, limiting case, or existing reference dataset when the repository provides one. Zero transport must suppress the corresponding flux; a source cutoff must stop the designated input counter; a conservative exchange must sum to zero across the two receiving states. For discretization changes, compare the requested endpoint under a finer grid or tighter integration tolerance and state the observed change and tolerance. Keep numerical accuracy checks distinct from agreement with calibration or validation experiments.

Concentration endpoints need both the species and denominator: extracellular intact carrier per extracellular fluid volume, intact mass per tissue volume, free cargo, intracellular mass, and loaded-cargo equivalent are different outputs. A threshold-contact duration also needs the time window, interpolation rule, and whether all continuous intervals or one specified interval are measured. Preserve these definitions in output column names or accompanying metadata.

Report an adapted-model run with its input and code hashes, solver and environment, physical residuals, endpoint values, source map, and performed numerical comparison. Store concrete unexecuted checks and missing empirical parameters in the model's boundary/reference document.
