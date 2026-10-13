# Scientific agent skills

Reusable, installable skills for scientific modeling and nucleic-acid design.

| Skill | Workflow |
|---|---|
| skin-transport-modeling | Reference carrier transport, dimensional checks and mass-balance reproduction |
| dna-sequence-model-benchmark | Nested sequence-model cross-validation and OOF auditing for supplied labels/features |
| tfna-paired-sequence-design | Four-strand complementary edits, actual mutation counts and frozen proxy scoring |
| generate-cadnano | Parameterized DNA-origami designs with topology and geometry validation |

Copy the desired folder from `skills/` into your agent's skill directory, preserving its
SKILL.md, scripts, references and agents metadata. Each skill describes when it applies,
the expected input, required environment and acceptance checks. Its scripts can also be
run directly using the documented command. Install only the dependencies of the selected skill.

The CK reference implementation, data and models live in
[tfna-ck-modeling](https://github.com/icerunningwalker-glitch/tfna-ck-modeling).
The standalone origami generator lives in
[generate-cadnano](https://github.com/icerunningwalker-glitch/generate-cadnano).
The benchmark helper can process a user's own sequence/feature/label table independently.

Three new skills were tested with isolated runs, saved scientific inputs and clearly
identified software fixtures. Mathematical outputs, OOF identity and illegal sequence
rejection were checked independently. Numerical provenance is retained with the code release.

Original new content uses MIT. The migrated generate-cadnano skill retains its own MIT
copyright notices and source ancestry. Third-party model/data terms are documented in the
implementation repository rather than redistributed as a new model license.
