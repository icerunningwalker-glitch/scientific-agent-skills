# Topology, model and selection contract

## Real inputs and topology

The implementation uses the four strands in `data/ai_optimization/design/reference.json` as WT. Each has 63 A/C/G/T bases. Junction positions 1, 22 and 43 preserve their WT values. Six antiparallel domains have 20 bases each:

| Edge | First strand/start | Complementary strand/start |
|---|---|---|
| E12 | 1c / 44 | 2c / 44 |
| E13 | 1c / 2 | 3c / 2 |
| E14 | 1c / 23 | 4c / 23 |
| E23 | 2c / 23 | 3c / 23 |
| E24 | 2c / 2 | 4c / 2 |
| E34 | 3c / 44 | 4c / 44 |

A first-domain position `p` maps to partner strand position `start_b + 20 - p`. Replacing a paired site changes two nucleotides. Count actual changes across all four strands independently; a broken partner or edited junction can violate the two-to-one relationship.

The repository's full validator also requires edge GC fraction 0.30–0.70, maximum strand homopolymer length 4, within-strand domain identity at most 0.75, and unintended common/complementary substring length at most 7. The last threshold comes from the recorded WT topology audit for this round. Read the chosen reference before reusing these settings with another scaffold. The skill helper audits topology and mutation counts; use the repository validator for these additional design filters.

FASTA requires four unique headers ending in `1c`, `2c`, `3c`, `4c`, such as `candidate_1c`. A scoring CSV needs `candidate_id` and `strand_1c` through `strand_4c`; declared paired-site counts must agree with the strands. The selector additionally requires `kind`, `generation_pattern`, and all four existing comparator IDs. It expects a scored table produced by the scoring command.

## Historical constructs and source identity

WT and Opt1/Opt2/Opt3 are saved comparators, read from `data/ai_optimization/design/four_constructs/` and the historical pool/selected table. Preserve these sequences when replaying them. Their mutations relative to WT are:

| Construct | Paired sites | Nucleotide changes | First-domain edits |
|---|---:|---:|---|
| WT | 0 | 0 | None |
| Opt1 | 3 | 6 | E12:11T>G; E34:12T>G; E34:15C>T |
| Opt2 | 1 | 2 | E12:11T>G |
| Opt3 | 4 | 8 | Opt1 plus E24:17A>G |

For new generation the four comparators are retained first, then all 360 possible single paired substitutions are considered. Invalid or duplicate singles are excluded; surviving singles may retain a marked historical overlap. For burdens 2, 3 and 4, the generator samples a configurable quota of within-edge and cross-edge designs with seed 20261002 by default. Multi-site designs matching prior-pool hashes are excluded. Sampling ends with an error if the quota cannot be reached before the attempt limit. New candidate IDs and outputs identify the current run.

## Frozen prediction contract

Historical model version: `historical_frozen_MLP_16_hidden_20261001`. It uses 123 local 20-nt sequence labels, representing spatially deduplicated local docking-site counts above `S = -E_Vina >= 8.0 kcal/mol`. The later seven-model benchmark has separate fitted models and evaluation records.

The encoder is HyenaDNA tiny at revision `e8c1effa8673814e257e627d2e1eda9ea5a373f6`. Mean pooling covers 20 real nucleotide embeddings and averages forward/reverse-complement orientations into 128 features. The MLP numerical snapshot applies a variance mask, input standardization, a 16-unit ReLU layer, output and inverse target standardization, then clips negative estimates to zero. The integer display rule is `floor(max(estimate, 0) + 0.5)`.

Cached prediction needs Python and NumPy. Fresh offline encoding also needs Torch, Transformers, tokenizers, safetensors and the bundled checkpoint. Check its `source_manifest.json` and model metadata; the encoder code executes the pinned local custom model implementation. Fresh inference is performed on CPU. Dependency installation, retraining and new docking are separate actions when requested.

The six-edge sum is a screening proxy derived from local count predictions. Its scale differs from docking energy, measured CK occupancy and simultaneous whole-tetrahedron loading. Historical saved scores are WT 3.0342441208, Opt1 4.9357407420, Opt2 3.9433063607 and Opt3 4.9357407420. The Opt1/Opt3 tie follows from a zero predicted contribution for both E24 variants. Preserve per-edge estimates and exact/reverse-complement training overlaps to interpret these values.

## Selection and completion

The saved 84 entries contain four comparators plus 20 designs at each burden 1–4. Burden 1 takes 20 score-ordered designs. Each other burden takes 10 within-edge and 10 cross-edge designs. Within each group, the selector first prefers a Hamming distance of at least 2 over the six first-oriented domains, then fills any shortage in score order. Distance is neither enforced between separate groups nor guaranteed after fallback.

For saved-score replay, compare candidate identity, pairing and mutation counts, six-edge contributions and numerical errors. Existing `smoke_check.py` tolerances are `1e-10` for cached local predictions and `1e-9` for complete proxy scores; optional fresh Opt3 replay uses `1e-5`. A saved-score replay checks computation against frozen assets. Record new generation, fresh encoding or model fitting separately when these actually run.
