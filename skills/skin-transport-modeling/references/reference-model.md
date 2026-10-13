# TH21 reference model

## Locate the code and inputs

The reference checkout has `src/transport/{physics.py,model.py,run_model.py,verify_results.py}`, `data/transport/`, `results/transport/`, `models/transport/MODEL_CARD.md`, and `logs/transport/Data_Sources.csv`. Read the model card, `Parameter_Table.csv`, `reference_inputs.json`, `Team_Design_Input.json`, and `fit_summary.json` before using its results. The source table maps parameter IDs to DOI records; the runner consumes the complete JSON input directly and performs no parameter refit.

`physics.Inputs` defines the flat JSON schema. All 34 fields in `reference_inputs.json` are numeric values with units encoded by their names. For field-level units and provenance, use `Parameter_Table.csv`; `core_nt` and `core_molecular_weight` are derived reporting constants in that table, not JSON fields accepted by `Inputs`.

| Input group | JSON fields |
|---|---|
| Protocol | `application_min`, `target_uM`, `required_contact_min`, `loading_fraction` |
| Particle and medium | `diameter_nm`, `zeta_mV`, `temperature_K`, `viscosity_Pas`, `relative_permittivity`, `ionic_strength_M`, `collagen_zeta_mV`, `intact_half_h` |
| Follicles | `follicles_cm2`, `volume_single_cm3`, `wall_single_cm2`, `orifice_diameter_um`, `follicle_length_um`, `follicle_viscosity_ratio`, `wall_P_ref_cm_h`, `packing_fraction` |
| Tracer closure | `dextran40_radius_nm`, `dextran500_radius_nm`, `dextran40_ve_um2_s`, `dextran500_ve_um2_s`, `dextran40_dermis_um2_s`, `dextran500_dermis_um2_s` |
| Tissue and uptake | `epsilon_ve`, `epsilon_dermis`, `internalization_hazard_h`, `sc_um`, `ve_bottom_um`, `bottom_um`, `dx_um`, `follicle_dx_um` |

## Equations and state accounting

The model uses a one-dimensional finite-volume depth grid for viable epidermis and shallow dermis, coupled laterally to a discretized finite follicular lumen. Follicular entry uses access resistance, and luminal motion uses an apparent fitted viscosity ratio. After wall exit, layer diffusion follows a power law interpolated from two dextran sizes and a screened-charge mobility factor. The lateral wall coefficient and luminal resistance are jointly fitted coefficients; uptake hazard is separately estimated from optical uptake data. These roles are recorded in the parameter table and fit summary.

Mass is ng of 252-nt TH21 core DNA equivalent per cm². `H` denotes follicular intact mass, `E` extracellular intact mass, `I` intracellular intact mass, `F` fragments, and `O` outward loss. The auxiliary `S` state represents the finite donor in the source-experiment protocol. `A` is additional input and `U` cumulative uptake; these counters are excluded from total mass. For the ideal application, the lumen starts at its specified fill fraction and is held at that level through the application cutoff, with replacement and removal explicitly added to `A` and `O`.

For each tissue cell, free concentration is `E / (epsilon * depth_width_cm) / 83160` in µmol/L. Because 1 ng/cm³ equals 1 µg/L, dividing by molecular weight in g/mol gives µmol/L. Contact concentration multiplies this free concentration by `alpha`, currently 1. Layer contact averages use extracellular fluid volume weights. Layer total concentration includes `E + I` and uses total tissue depth, so its denominator differs from free concentration.

The preserved `summary.json` field `dose_ug` equals total supplied core-DNA-equivalent mass in ng/cm² divided by 1000. Its unit is **µg/cm²**; for the fixed 1 cm² modeled area, the same numeric value is the total µg in that area. Retain the historical field name when comparing reference files and include the area unit when reporting it.

`run_model.py` produces intact-carrier mass and concentration outputs, with no separate free-CK or loaded-cargo-equivalent output column. Under the team input of two CK molecules per tFNA, multiplying intact-carrier molar concentration by 2 gives a loaded-CK-equivalent concentration by arithmetic. Record that loading assumption and conversion separately when reporting the derived quantity.

## Reference execution and acceptance

From the checkout root:

```text
python src/transport/run_model.py --output-dir <fresh-output-dir>
python src/transport/verify_results.py --generated-dir <fresh-output-dir> --report <fresh-output-dir>/validation.json
```

Inputs are located relative to the source file, so these script paths can also be absolute paths from another working directory. The model uses SciPy BDF integration, `rtol=2e-7`, a mass-scaled absolute tolerance, and Jacobian sparsity. It splits integration at 15 minutes for the reference application.

The reference JSON uses a 17.02 nm particle, -8.188 mV charge, 15-minute application, full initial lumen loading, 20–400 µm tissue domain, 2.5 µm tissue cells, and 6.25 µm follicular cells. The runner computes 2,032 time samples through 100 h, while the depth-time heatmap covers 0–4 h. Required-contact duration is design metadata; the current entrypoint does not compute a duration-above-threshold endpoint.

The verifier compares five numerical CSVs, all scientific summary values, and the exact schema and values of the run's copied reference inputs. Tables must be nonempty and finite, with matching row count, ordered column names, and text fields. Numerical comparison uses `rtol=1e-9`, `atol=1e-10`. Solver residual values may vary between builds, so the three physical checks are evaluated by thresholds rather than compared with historical residual magnitudes: relative mass residual below `1e-7`, minimum state above `-1e-7`, and additional-input range after removal below `1e-8`.

The helper also checks unchanged SHA-256 identities for the module's source, data, model metadata, logs, and preserved results. It records the actual environment; the dependency pins are the historical declared environment. Generated PNG/SVG files are render outputs and are not required to be byte-identical across Matplotlib versions.

## Scope and conditions

- The default run estimates transport of the reference intact TH21 carrier under the specified ideal follicular supply protocol. It uses two CK molecules per carrier as a team design loading condition; 0.5 µmol/L tFNA corresponds to 1 µmol/L loaded-CK equivalent by that arithmetic.
- Luminal capacity is calculated from equal hydrodynamic spheres with packing fraction 0.64. Tissue geometry and porosity come from the stated reference sources.
- The equations have no explicit formulation-release compartment, direct stratum-corneum passage, intracellular carrier export, or free-CK release state. Use extracellular carrier concentration, intracellular intact mass, and cargo-equivalent arithmetic as separate quantities.
- The packaged entrypoint fixes its summaries and plot axes to the 15-minute reference design and assumes full initial loading in its dose and residual calculation. A changed application time or loading fraction requires corresponding runner changes and acceptance checks; editing the JSON alone is insufficient.
- The charge and size scaling is a stated closure normalized at reference TH21. Opt1/Opt2/Opt3 sequence predictions, packing proxies, docking scores, or loop optimization scores do not supply a measured hydrodynamic size, zeta potential, permeability, or calibrated transport coefficient. Candidate-specific forward comparisons require those inputs and their provenance.
- This bundle contains processed calibration data and fit summaries; parameter-refitting code is outside this forward reproduction entrypoint. Preserve each data snapshot and fitted-value identity when adapting it.
