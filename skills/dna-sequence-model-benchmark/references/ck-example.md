# CK source example

The source benchmark uses 123 unique local 20-nt DNA sequences and 128 frozen HyenaDNA features. Labels count sampled, pose-deduplicated tight local docking sites using seed 104729 and Vina energy <= -8 kcal/mol (`S=-energy >=8`). Counts 0/1/2 occur 31/90/2 times. Use that definition only for the CK source data; another user's count or regression label needs its own source, units and generation protocol.

The recorded outer seed is 20261003 and test sizes are 25/25/25/24/24. Outer folds are shuffled and stratified by count, with related families crossing outer train/test partitions. Three inner folds keep families separated while tuning. Each model contributes 123 OOF values; its pooled training diagnostic averages four in-sample outer-model predictions per sequence.

Historical MLP pooled OOF MAE is 0.2104099787 and AUC is 0.8972650771. TabPFN MAE is 0.2146171329. One-hot Ridge MAE is 0.2234014184. Ridge has a lower integer count MAE than MLP. Report comparison by the particular metric rather than claiming one model leads every endpoint.

Packaged source paths are `src/ai_optimization/benchmark`, `data/ai_optimization/benchmark`, `models/ai_optimization/benchmark`, `results/ai_optimization/benchmark` and `logs/ai_optimization/benchmark`. The fixed-source trainer accepts that specific schema and saved membership files; the skill helper accepts a new user's generic schema.

The intended public repository is https://github.com/icerunningwalker-glitch/tfna-ck-modeling . Publication status must be verified at use time. This reference does not assert that the repository has been created.

The source package includes 35 non-TabPFN fitted fold snapshots and five TabPFN training-context files. The official TabPFN V2 checkpoint is supplied separately under its applicable terms. This audit reproduces numerical snapshots and independently recalculates saved TabPFN metrics; fresh TabPFN checkpoint inference is a separate action. Local docking-site counts are the source proxy; whole-tFNA loading, MD stability and wet-lab measurements use their own inputs and endpoints.
