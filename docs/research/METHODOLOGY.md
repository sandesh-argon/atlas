# METHODOLOGY_NARRATIVE



## 1. Introduction

Atlas is a longitudinal causal-discovery and policy-simulation program built to answer a specific research need: how to move from large observational development panels to scenario guidance without hiding uncertainty. The system was developed over multiple generations (V1 through V3.1), and the current publication corpus is anchored to a production-certified runtime and a claim-level evidence ledger. The certification state is `CERTIFIED` and `PRODUCTION_READY`, which means the data artifacts, runtime interfaces, and validation checks all passed release criteria before this narrative conversion began (Evidence: CLM-0001, CLM-0002).

The audited panel used in the current validation cycle contains 18,296,578 rows, 893 country entities, and 3,122 indicators. Runtime serving assets include 5,054 temporal graph files, 5,053 temporal SHAP files, and 5,026 baseline files. Regional serving adds 286 graph files, 286 SHAP files, and 11 regional indicator-stat files, with country-to-region mapping validated at 178/178 canonical countries (Evidence: CLM-0005, CLM-0006, CLM-0007, CLM-0014, CLM-0015, CLM-0016, CLM-0017, CLM-0018, CLM-0019, CLM-0057).

The project contribution is not a single coefficient table. The contribution is an integrated workflow where every numerical statement in public-facing documents can be traced to a registered claim, a concrete evidence anchor, and a known artifact path. That design choice is central to trust: Atlas treats provenance, contradiction handling, and uncertainty language as part of the scientific method, not as compliance afterthoughts.

### 1.1 Research Questions and Scope

The first research question is methodological: can a multi-stage causal discovery pipeline preserve interpretability at Atlas scale while staying auditable end to end? The second question is substantive: do high-coverage relationships in the Atlas corpus reveal mechanism classes that matter for policy design, such as cross-strata reversals, threshold effects, and mediated transmission chains? The third question is operational: can those findings be translated into policy-ready prose without breaking evidence fidelity.

Atlas answers these questions by separating concerns. Discovery stages estimate directional structure under explicit assumptions. Runtime layers serve those artifacts with scope-aware fallback handling. Narrative synthesis then converts validated evidence into documents that can be reviewed by technical and non-technical audiences without changing the underlying numbers.

Scope boundaries are explicit in this phase: no new model training, no causal re-estimation, and no external claims that are not already represented in repository artifacts. The narrative documents are therefore an evidence-grounded synthesis pass over validated outputs, not a new statistical experiment.

### 1.2 Origins and Early Failure Context

Atlas V1 established ambition and exposed feasibility constraints. The V1 scope statement targeted 174 countries across 65 years and 2,480 indicators. Early exports documented a combined graph with 162 nodes and 204 edges. Those numbers are historically important because they mark the first complete loop from ingestion to causal graph publication, but they also mark the beginning of identified limits in sample retention and temporal coverage management (Evidence: CLM-0023, CLM-0024).

The most consequential early failure was a data-coverage cascade. Under naive temporal-completeness handling, usable sample size collapsed after filtering, making downstream structure learning brittle. That failure is recorded as FAIL-0004 and was resolved by reworking feature engineering and filtering around explicit panel-density constraints before causal estimation (Evidence: FAIL-0004).

This failure history informs current methodology sections intentionally. Atlas does not frame pipeline changes as abstract “improvements”; it documents why specific design choices were made, what broke before, and what replacement policy is now enforced.

## 2. Data Sources and Integration

The active reproducibility registry contains 11 datasets with canonical URLs and archival URLs, each linked to ingestion lineage. The full dataset registry has 51 rows, but only active rows are used for public claims because active status requires link completeness and reproducibility metadata. This active-only policy was adopted to prevent citation drift between narrative text and fetchable source artifacts (Evidence: CLM-0054).

Atlas integrates institutional datasets with different definitions, update cycles, and country coverage conventions. Instead of forcing one universal source hierarchy, Atlas uses a controlled harmonization layer that preserves source identity while normalizing country keys, indicator IDs, and yearly indices for model compatibility.

### 2.1 Active Source Families

International Comparison Program (World Bank) is an active source family in this release. In the registry, this source is linked through a canonical reference (https://www.worldbank.org/en/programs/icp) and an archival reference (https://web.archive.org/web/*/https://www.worldbank.org/en/programs/icp). The metadata entry records coverage as 91 indicators (v2.1 labels). Atlas treats this source as reproducible for public claims because required provenance fields are complete (Dataset: DS-0019; Evidence: CLM-0054).

Penn World Table 10.0 (Penn World Table) is an active source family in this release. In the registry, this source is linked through a canonical reference (https://www.rug.nl/ggdc/productivity/pwt/) and an archival reference (https://web.archive.org/web/*/https://www.rug.nl/ggdc/productivity/pwt/). The metadata entry records coverage as 10 indicators (v2.1 labels). Atlas treats this source as reproducible for public claims because required provenance fields are complete (Dataset: DS-0023; Evidence: CLM-0054).

Quality of Government (Quality of Government Institute) is an active source family in this release. In the registry, this source is linked through a canonical reference (https://www.gu.se/en/quality-government/qog-data/data-downloads) and an archival reference (https://web.archive.org/web/*/https://www.gu.se/en/quality-government/qog-data/data-downloads). The metadata entry records coverage as 85 indicators (v2.1 labels). Atlas treats this source as reproducible for public claims because required provenance fields are complete (Dataset: DS-0025; Evidence: CLM-0054).

UNESCO Institute for Statistics (UNESCO UIS) is an active source family in this release. In the registry, this source is linked through a canonical reference (https://uis.unesco.org/) and an archival reference (https://web.archive.org/web/*/https://uis.unesco.org/). The metadata entry records coverage as 446 indicators (v2.1 labels). Atlas treats this source as reproducible for public claims because required provenance fields are complete (Dataset: DS-0033; Evidence: CLM-0054).

V-Dem Institute (V-Dem Institute) is an active source family in this release. In the registry, this source is linked through a canonical reference (https://www.v-dem.net/data/the-v-dem-dataset/) and an archival reference (https://web.archive.org/web/*/https://www.v-dem.net/data/the-v-dem-dataset/). The metadata entry records coverage as 456 indicators (v2.1 labels). Atlas treats this source as reproducible for public claims because required provenance fields are complete (Dataset: DS-0039; Evidence: CLM-0054).

World Bank (World Bank) is an active source family in this release. In the registry, this source is linked through a canonical reference (https://data.worldbank.org/) and an archival reference (https://web.archive.org/web/*/https://data.worldbank.org/). The metadata entry records coverage as 68 indicators (v2.1 labels). Atlas treats this source as reproducible for public claims because required provenance fields are complete (Dataset: DS-0045; Evidence: CLM-0054).

World Development Indicators (World Bank) is an active source family in this release. In the registry, this source is linked through a canonical reference (https://databank.worldbank.org/source/world-development-indicators) and an archival reference (https://web.archive.org/web/*/https://databank.worldbank.org/source/world-development-indicators). The metadata entry records coverage as 169 indicators (v2.1 labels). Atlas treats this source as reproducible for public claims because required provenance fields are complete (Dataset: DS-0047; Evidence: CLM-0054).

World Health Organization (World Health Organization) is an active source family in this release. In the registry, this source is linked through a canonical reference (https://www.who.int/data/gho) and an archival reference (https://web.archive.org/web/*/https://www.who.int/data/gho). The metadata entry records coverage as 2 indicators (v2.1 labels). Atlas treats this source as reproducible for public claims because required provenance fields are complete (Dataset: DS-0048; Evidence: CLM-0054).

World Inequality Database (WID) is an active source family in this release. In the registry, this source is linked through a canonical reference (https://wid.world/data/) and an archival reference (https://web.archive.org/web/*/https://wid.world/data/). The metadata entry records coverage as 296 indicators (v2.1 labels). Atlas treats this source as reproducible for public claims because required provenance fields are complete (Dataset: DS-0049; Evidence: CLM-0054).

Atlas v31 Income Classifications (Atlas) is an active source family in this release. In the registry, this source is linked through a canonical reference (https://github.com/Atlas-Project) and an archival reference (https://web.archive.org/web/*/https://github.com/Atlas-Project). The metadata entry records coverage as Atlas runtime metadata. Atlas treats this source as reproducible for public claims because required provenance fields are complete (Dataset: DS-9001; Evidence: CLM-0054).

Atlas v31 Regional Groups (Atlas) is an active source family in this release. In the registry, this source is linked through a canonical reference (https://github.com/Atlas-Project) and an archival reference (https://web.archive.org/web/*/https://github.com/Atlas-Project). The metadata entry records coverage as Atlas runtime metadata. Atlas treats this source as reproducible for public claims because required provenance fields are complete (Dataset: DS-9002; Evidence: CLM-0054).

### 2.2 Integration Workflow

Integration is executed in four controlled passes. Pass 1 is structural normalization, where source files are parsed into a common table schema with country, indicator, year, value, and source columns. Pass 2 is semantic normalization, where indicator IDs and labels are reconciled to avoid duplicate semantics entering the same causal neighborhood. Pass 3 is temporal compatibility filtering, where trajectories failing minimum continuity constraints are excluded from causal stages. Pass 4 is registry synchronization, where ingest outputs are linked to dataset and evidence registries before downstream use.

The key methodological point is that Atlas treats missingness handling as a causal-risk control, not a preprocessing convenience. If missingness is handled naively, the discovered graph can overrepresent well-observed country-year pockets while suppressing structurally important low-coverage signals. The current policy addresses this by filtering with transparency and carrying exclusions into audit logs.

Documentation drift checks are part of integration quality control. In this cycle, one progress artifact reported 9,926 outputs while a table reported 9,928 outputs. The contradiction was resolved through structured audit policy: frozen release claims must use structured validation artifacts, not prose headers. The contradiction register is currently closed to zero unresolved items (Evidence: CLM-0021, CLM-0022, CLM-0051).

### 2.3 Data Governance and Reproducibility Controls

Atlas uses three linked registries to enforce reproducibility: dataset registry, ingestion registry, and evidence ledger. The dataset registry defines source identity and access links. The ingestion registry records fetch/parse lineage and version alignment. The evidence ledger binds claim IDs to physical artifacts. Narrative conversion is allowed only when claim and evidence linkage is complete.

This policy directly affects writing behavior. If a value cannot be traced to a registered claim or a repository-verified artifact, Atlas excludes that value from public narrative sections. Claims are removed, not softened, when traceability fails. That is why the final documents can be audited line by line with machine-checkable references.

The same governance rule is used for contextual citations. Atlas allows contextual references only when they already exist in repository artifacts. New external claims are prohibited in this narrative phase to prevent accidental scope expansion and unverifiable comparisons.

## 3. Causal Discovery Pipeline

Atlas uses a staged causal discovery pipeline because each stage answers a different statistical question and failure mode. Stage A2 tests temporal precedence relationships at scale. Stage A3 removes conditionally spurious edges under multivariate structure constraints. Stage A4 estimates effect sizes with bootstrap retention and significance filters. Keeping these steps separate enables targeted diagnosis when claims are challenged.

A single-stage approach at this dimensionality tends to create either dense and uninterpretable graphs or sparse and brittle graphs. Atlas avoids that by allowing A2 to be broad, A3 to be structurally selective, and A4 to be reliability-selective. The resulting graph set is smaller than the candidate universe but still broad enough for policy scenario exploration.

The pipeline lineage in this release is anchored to V2.1 A2/A3/A4 outputs and carried forward into V3.1/v31 serving artifacts via standardized schemas and validation checks (Evidence: CLM-0008, CLM-0009, CLM-0011, CLM-0012, CLM-0013).

### 3.1 Stage A2: Granger Causality Prefiltering

Stage A2 ran 2,159,672 pairwise Granger causality tests with a maximum lag of 5 years. Granger causality, in this context, asks whether lagged history of candidate source variable X improves prediction of target Y beyond Y’s own lagged history. The test is used as a temporal precedence filter: it is necessary evidence for directional plausibility but not sufficient evidence for causal identification (Evidence: CLM-0008, CLM-0010).

False discovery rate control was applied at q<0.05, yielding 564,545 retained edges from the initial tested set. This corresponds to a retention rate of 26.14% and a pruning rate of 73.86%. That contraction is expected in high-dimensional observational settings where many pairwise correlations are either weak or temporally non-predictive when tested systematically (Evidence: CLM-0009).

A2 is intentionally permissive relative to later stages. The goal is to avoid discarding plausible temporal candidates too early while still shrinking the combinatorial space. Atlas therefore treats A2 output as a screened candidate pool, not as publishable causal claims.

### 3.2 Stage A3: Structure Learning with PC-Stable

Stage A3 applies PC-Stable conditional-independence logic to remove edges that are explainable by confounder structures. The method is documented in repository technical notes as PC-Stable with Fisher-Z testing and cycle-removal cleanup for DAG consistency. A3 reduces the edge set to 58,837 edges in the final DAG list (Evidence: CLM-0011).

Relative to A2 survivors, A3 retains about 10.42% of edges. This contraction is a structural specificity step: A2 asks whether X precedes Y temporally, while A3 asks whether X still contributes when candidate confounders are considered. Edges removed here are not “wrong” in a broad predictive sense; they are less defensible as direct structural relationships under the conditional-independence assumptions.

The key interpretive limitation is that conditional-independence decisions depend on observed variables. Unmeasured confounding can still distort orientation and adjacency. Atlas addresses this by treating A3 as structural pruning, not final certainty, and by requiring A4 stability checks before narrative promotion.

### 3.3 Stage A4: Bootstrap Effect Estimation and Retention

Stage A4 estimates edge effect sizes and stability using 100 bootstrap iterations, retaining 4,976 edges in the validated set. Bootstrap resampling is used to measure edge-level robustness under sampling perturbations and to compute interval summaries where available. Edges that do not satisfy retention criteria are removed from the validated graph set (Evidence: CLM-0012, CLM-0013).

The A4 retention rate relative to A3 is 8.46%, which reflects Atlas’s conservative reliability posture. This step intentionally favors edges that are persistent across resamples over edges that appear strong in a single fit but unstable under perturbation. The result is a materially smaller but more robust edge inventory for simulation and findings extraction.

Bootstrap output is not treated as absolute uncertainty truth. Atlas documents known miscalibration risks from prior phases and applies conservative caveat policy in public findings, especially where confidence intervals are sparse or missing.

### 3.4 Why the Three-Stage Design is Defensible

The staged design improves both computation and interpretation. Computationally, each stage reduces the search space in a way that makes the next stage feasible. Interpretively, each stage adds a specific evidence layer: temporal order, structural plausibility, and stability under perturbation. This layered logic is easier to explain and audit than one opaque end-to-end estimator.

For policy audiences, the practical outcome is that each narrative finding can be framed with mechanism class and uncertainty class. A finding that is high-coverage but sign-unstable is communicated differently from a finding that is threshold-stable but CI-sparse. That distinction is only possible because discovery artifacts preserve stage-level diagnostics.

For researchers, the same architecture enables targeted replication. A replication attempt can start at A2 counts, then A3 reductions, then A4 retention diagnostics, rather than only checking final top findings.

## 4. SHAP Importance Analysis

Atlas uses SHAP (SHapley Additive exPlanations) artifacts as contribution diagnostics for model interpretation layers. In plain terms, a SHAP value measures how much a feature contributes to a prediction relative to a baseline for a given model and observation context. Atlas uses these values to rank explanatory contribution, not to claim policy causation by itself.

The serving corpus includes 5,053 temporal SHAP files across scopes and 286 regional SHAP files. This near parity with graph files (5,054 temporal; 286 regional) supports year-by-year interpretability checks across model scopes (Evidence: CLM-0014, CLM-0015, CLM-0017, CLM-0018).

SHAP and causal edges are interpreted jointly. When SHAP concentration and edge stability align, confidence in mechanism framing improves. When they diverge, Atlas treats that divergence as a caution signal and elevates uncertainty language. This policy avoids a common communication error where feature importance is misrepresented as intervention effect size.

### 4.1 SHAP in Policy Context

Policy teams often ask which variables “matter most.” SHAP helps answer that in a model-relative way by quantifying contribution burden. Atlas translates this into two operational checks: persistence and concentration. Persistence asks whether high-contribution signals remain present across years. Concentration asks whether contribution mass is narrowly concentrated or distributed across many indicators.

A concentrated SHAP profile can be useful for prioritization but risky for overfitting policy interpretation. A distributed profile can indicate resilient multi-factor dynamics but can complicate intervention prioritization. Atlas therefore uses SHAP as a guide to investigation order, not as a policy prescription engine.

The final writing rule is strict: SHAP-based statements must be paired with causal-stage context and uncertainty statements when promoted into narrative findings.

## 5. Simulation Engine

Atlas simulation is a multi-hop propagation engine over validated directed graphs. Users define baseline conditions and intervention changes, and the engine propagates effects through connected edges with damping, horizon control, and optional nonlinear handling where edge metadata supports it. Output is interpreted as comparative movement under modeled assumptions.

Comparative output means the engine is designed for scenario differences, not for absolute point forecasts. The distinction is methodological and ethical: a scenario simulator can be transparent about uncertainty while still supporting decision sequencing, whereas deterministic forecast framing can create false precision in complex systems.

This distinction was not present from the beginning; it was learned through failure. V3.0 attempts to use propagation as an absolute forecaster were documented as a failure and replaced with comparative framing policy (Evidence: FAIL-0001).

### 5.1 Scope Modes and Regional Capability

Current runtime supports unified, stratified, country, and regional scopes. Regional capability is now part of the v31 asset set and includes dedicated graphs, SHAP files, and regional indicator statistics. Mapping coverage is 178/178 canonical countries, and North America mapping semantics are explicitly recorded as Canada and the United States with Mexico assigned to the Latin America and Caribbean region key (Evidence: CLM-0017, CLM-0018, CLM-0019, CLM-0057, CLM-0058).

Regional analysis introduces aggregation risk: edge union can inflate graph density relative to stratum-level graphs. Atlas mitigates this with explicit warnings, year-scope fallbacks, and continued reporting of contributor coverage. These caveats are surfaced in narrative outputs rather than hidden in runtime logs.

A recent regional audit counted 1,093,922 regional edges, confirming large-scale nonlinearity and marginal-effect metadata presence while still requiring per-finding caveat checks for CI sparsity and threshold stability (Evidence: CLM-0056).

### 5.2 Uncertainty Handling in Simulation Outputs

Simulation uncertainty is represented through bootstrap-informed intervals where available, edge-level confidence metadata, and scenario caveats. Atlas does not collapse this to a single confidence score because uncertainty sources are heterogeneous: data coverage gaps, directional instability, nonlinear regime shifts, and sparse interval fields can all affect interpretation differently.

The system includes explicit rules for problematic patterns. Direction-only claims are blocked from high-confidence framing without corroboration (FAIL-0002). Overly narrow intervals are treated as potentially miscalibrated and communicated conservatively (FAIL-0003). Scenario outputs are therefore best interpreted as structured hypotheses for local validation, not as standalone policy guarantees.

These safeguards are intentionally conservative. Atlas chooses slower, caveat-rich communication over headline certainty when evidence structure is mixed.

## 6. Validation and Robustness

Validation in this cycle is anchored to `CERTIFIED` / `PRODUCTION_READY` status with explicit pass counts in major checks: Phase 2A validated 4,749/4,767 files (99.62%) and Phase 2B validated 4,680/4,768 files (98.15%). These are not isolated model scores; they are system-level readiness checks spanning data integrity, artifact structure, and serving consistency (Evidence: CLM-0001, CLM-0002, CLM-0003, CLM-0004).

Robustness is evaluated on coherence across layers. Panel-level validation confirms scale and coverage. Runtime-level validation confirms file presence and schema compliance. Findings-level validation confirms that shortlisted findings are robust across years and graph scopes. Contradiction-level validation confirms that conflicting claims are resolved before publication.

In this run, contradiction closure reached zero unresolved items and citation audits reported zero missing and zero unknown evidence links. This is important for AI-assisted synthesis because fluent prose can conceal evidence gaps if audit constraints are not enforced (Evidence: CLM-0051, CLM-0054).

### 6.1 Findings Robustness Layer

The findings extraction package evaluated 11,632 candidates across a full coverage target of 140 graphs and 35 years. The ranked top-10 was explicitly diversified by class: four reversals, three mediation findings, two threshold findings, and one outcome-surprise finding. The public top-4 preserved one representative finding from each class family to avoid overrepresenting a single mechanism pattern (Evidence: CLM-0026, CLM-0027, CLM-0028, CLM-0029, CLM-0030, CLM-0031, CLM-0032).

This diversity policy is a robustness safeguard, not a marketing choice. If the top list is dominated by one class (for example, only sign reversals), readers can overgeneralize one uncertainty mode. By forcing class variety, Atlas communicates the true mechanism heterogeneity present in the corpus.

Anchor findings F01, F02, F06, and F08 were selected because each has full temporal and graph availability while representing different interpretive risks and policy use cases.

## 7. Limitations and Failure Modes

Atlas documents limitations as first-class outputs because omission of known failure modes can mislead readers more than model error itself. Four failures are explicitly maintained in the failure registry and are required in narrative limitations sections.

FAIL-0001: absolute forecasting framing failed predictive checks and was replaced by comparative scenario framing. FAIL-0002: directional interpretations were unstable under resampling, so direction-only claims now require corroboration. FAIL-0003: confidence intervals showed miscalibration risk, so conservative caveat policy was adopted. FAIL-0004: early V1 coverage handling caused sample-dropout cascades, leading to stricter panel-density filtering upstream (Evidence: FAIL-0001, FAIL-0002, FAIL-0003, FAIL-0004).

A separate archival limitation remains active: a v2.1 prefilter survivor artifact referenced in legacy documentation is absent in the current snapshot, while a v2.0 counterpart exists. Atlas policy therefore prohibits asserting exact v2.1 survivor counts as artifact-verified until that file is recovered (Evidence: CLM-0059).

### 7.1 Practical Interpretation Limits

High availability does not imply universal transportability. A finding active in 140/140 graphs can still have context-specific mechanism differences. Atlas mitigates this by pairing each finding with caveat text and by discouraging direct policy import across development stages without local diagnostics.

Threshold findings are especially sensitive to context because threshold value, below-regime slope, and above-regime slope can vary by institutional history and variable measurement. Mediation findings are sensitive to omitted mediators and data sparsity in intermediate variables. Reversal findings are sensitive to stratification boundaries and within-stratum heterogeneity.

For these reasons, Atlas recommends using findings for policy sequencing and hypothesis prioritization, then validating with local data before high-cost intervention deployment.

## 8. AI-Assisted Workflow and Validation Safeguards

This narrative conversion used AI assistance for prose drafting, restructuring, and readability editing. AI was not used to rerun discovery stages, compute new coefficients, or modify the underlying causal corpus. All quantitative statements originate from existing registered claims and findings artifacts.

AI use is bounded by explicit safeguards: evidence-linkage checks for quantitative claims, numeric integrity checks against canonical claims, uncertainty-caveat checks for flagged findings, failure-transparency checks for required failure IDs, and cross-document consistency checks for shared metrics. Any claim failing these checks is revised or removed before final packaging.

Human review remains final authority. The workflow includes three human gates: H1 findings-strength review, H2 scientific framing review, and H3 publication-readiness review with a fresh-reader check for policy brief trust and clarity. In this repo run, gate files are pre-populated as review templates and marked pending where human judgments are still required.

### 8.1 Why AI Use is Declared Explicitly

Declaring AI assistance is a scientific integrity requirement, not a branding statement. AI-generated text can smooth uncertainty language and make weak claims sound stronger if not constrained. Atlas counters that risk by enforcing claim-level evidence mapping and mandatory caveats on uncertain findings.

The practical standard is simple: prose quality does not raise evidence quality. A polished paragraph still inherits the uncertainty of its underlying claim. Atlas documents this boundary explicitly so readers can evaluate conclusions on evidence strength rather than rhetorical fluency.

All narrative artifacts in this phase include direct traceability to registries in the same workspace, making independent review possible without rerunning the full pipeline.

## 9. Reproducibility and Artifact Map

Reproducibility for this narrative package depends on seven linked files: claim registry, evidence ledger, dataset registry, ingestion registry, failure registry, contradiction log, and open questions. The generated narrative outputs add an evidence-map file and QA/consistency reports so reviewers can move directly from paragraph-level claims to source anchors.

This architecture is intended to support both academic and operational reuse. Academic readers can audit methods and findings claims. Engineering readers can trace which runtime and validation artifacts back each statement. Policy readers can review caveats and confidence framing without reading raw model files.

As of this package generation, unresolved contradictions are 0 and orchestrated task closure is 8 tasks closed. API surface remains router=45;app=2;total=47. These controls do not prove findings correctness by themselves, but they materially reduce preventable reporting errors in high-volume synthesis workflows (Evidence: CLM-0051, CLM-0052, CLM-0060).


## 10. Statistical Formulation and Assumption Register

### 10.1 Stage A2 Test Formulation

Stage A2 uses a vector-autoregressive framing of pairwise Granger causality. For a candidate source series $X_t$ and target series $Y_t$, Atlas compares a restricted model where $Y_t$ is regressed on its own lag history with an unrestricted model that also includes lagged values of $X_t$. If adding lagged $X$ terms materially improves fit, Atlas records temporal predictive precedence for the candidate edge. In practice this is a screening test, not a final causal claim. The test asks whether history helps prediction under the observed panel process; it does not establish intervention invariance by itself (Evidence: CLM-0008, CLM-0010).

False discovery control is applied after testing at scale. Atlas uses Benjamini-Hochberg style control in the documented A2 workflow and retains edges at q<0.05 in the canonical count path. This matters because pairwise testing at Atlas scale naturally produces many low p-values by chance. FDR control protects the retained set from becoming a noise-dominated candidate pool while still preserving medium-strength signals needed for downstream structural pruning (Evidence: CLM-0009).

A2 assumptions are explicit. The first assumption is that lagged dependence captures useful temporal ordering signals in the observed data process. The second is that the selected lag horizon is long enough to capture medium-run dependencies without collapsing sample size in sparse series. The third is that unobserved confounding does not fully explain all observed pairwise predictive gains. Atlas does not treat these assumptions as hidden defaults; they are surfaced because they shape what A2 can and cannot say.

### 10.2 Stage A3 Structural Testing Logic

A3 introduces conditional-independence reasoning. Informally, if $X$ and $Y$ are no longer associated when conditioning on a candidate separator set $S$, the direct edge is considered less plausible. The PC-Stable family of algorithms does this systematically across conditioning set sizes while controlling orientation updates to reduce order dependence. Atlas records A3 as the stage that changes candidate temporal links into a structurally constrained DAG edge set.

This stage is the methodological bridge between predictive precedence and graph structure. A2 alone can admit edges that are predictive but not structurally direct. A3 removes many such edges by asking whether association persists after accounting for plausible confounders and mediator parents. The retained graph is therefore more interpretable for simulation, even though it still remains an observational estimate under finite covariate coverage (Evidence: CLM-0011).

A3 assumptions include adequate confounder representation in observed variables and stable partial-correlation behavior under finite samples. When these assumptions fail, A3 can still include spurious edges or remove true but weak edges. Atlas addresses this through A4 resampling checks and by explicitly communicating uncertainty classes in findings narratives.

### 10.3 Stage A4 Bootstrap Retention and Interval Interpretation

A4 quantifies effect size stability using repeated resampling. For each candidate edge retained from A3, Atlas estimates coefficients over bootstrap samples and computes retention and interval summaries where available. Edges that fail stability criteria or interval-sign coherence constraints are removed from the validated set. This yields the canonical retained edge count for downstream simulation and findings extraction (Evidence: CLM-0012, CLM-0013).

Bootstrap assumptions are narrower than many users expect. Resampling captures variability induced by finite sample composition under observed data structure; it does not add new information about unobserved confounding, measurement error processes, or policy implementation shocks. Atlas therefore uses bootstrap as a robustness filter and uncertainty proxy, not as complete uncertainty characterization.

Atlas also documents known CI miscalibration history. Earlier pipeline phases produced intervals that were too narrow for deployment-grade confidence framing. That failure is now part of publication policy: interval claims must be conservative when findings carry CI sparsity flags, and policy text must avoid precision language not supported by evidence (Evidence: FAIL-0003).

### 10.4 Assumption Register for Readers and Reviewers

The assumption register in Atlas is intentionally reader-facing. Every major stage has assumptions that can fail in real data. Instead of burying these assumptions in code comments, Atlas presents them in prose so reviewers can evaluate whether claims overreach their support. This is especially important when findings are communicated outside technical audiences.

The most important assumption-level guardrail is the comparative-use rule. Atlas does not claim that simulation outputs are absolute forecasts. That boundary prevents misuse of structurally estimated graphs as deterministic planning calculators. By centering comparative deltas and caveat-rich interpretation, Atlas keeps claims aligned with what the data and methods can defend (Evidence: FAIL-0001).

## 11. Validation Protocol Catalog

### 11.1 System Certification Checks

Certification checks cover schema validity, file integrity, cross-reference completeness, and value-range sanity across artifacts. Phase-level counts provide quantitative checkpoints so quality status is not based on subjective review. In the current release, Phase 2A and Phase 2B pass rates exceed 98%, with both phases passing the release threshold for production readiness (Evidence: CLM-0003, CLM-0004).

These checks are necessary because discovery pipelines can fail silently at scale. A single malformed batch or key mismatch can corrupt downstream analysis without obvious runtime errors. Atlas prevents this by treating structural checks as hard gates and by recording pass/fail outcomes in auditable artifacts.

### 11.2 Panel Integrity Checks

Panel integrity checks verify row counts, entity counts, and indicator counts against frozen release expectations. This is not a cosmetic report step; it detects accidental sample shifts that can materially change model behavior. Atlas records these counts in claim-level artifacts and reuses them across methodology, findings, and policy documents to enforce consistency (Evidence: CLM-0005, CLM-0006, CLM-0007).

A key lesson from earlier iterations is that panel integrity must be monitored after every major transformation, not only at ingest. Feature engineering, filtering, and merge operations can all change effective sample structure. Atlas therefore repeats integrity checks at validated milestones rather than assuming upstream correctness propagates automatically.

### 11.3 Runtime Asset Coherence Checks

Runtime coherence checks ensure that graph, SHAP, and baseline assets align by scope and year so simulation services do not operate on partial or mismatched inputs. Atlas reports separate counts for temporal and regional assets to avoid masking scope-specific gaps. This is especially important when regional capabilities are newly integrated and still accumulating operational history (Evidence: CLM-0014, CLM-0015, CLM-0016, CLM-0017, CLM-0018, CLM-0019).

Coherence checks also support fallback transparency. If an exact year asset is unavailable for a scope, runtime services can use nearest-year fallback with warnings. Atlas treats warning emission as part of evidence quality and requires warning-aware interpretation in narrative outputs.

### 11.4 Citation and Contradiction Checks

Atlas runs citation completeness checks to verify that factual narrative claims map to registered evidence IDs. In this cycle, the citation audit reported zero missing and zero unknown evidence links. This metric is a direct control against narrative hallucination and stale reference drift (Evidence: CLM-0054).

Contradiction checks compare values across artifacts and flag mismatches. Atlas tracks contradictions as first-class records and requires explicit closure notes. Current unresolved contradiction count is zero, which means outstanding numeric conflicts are not known at package freeze (Evidence: CLM-0051).

## 12. Findings Extraction Governance

### 12.1 Candidate Generation and Coverage

Findings extraction evaluates a large candidate pool and ranks candidates under a robustness-first scoring policy. In the current package, 11,632 candidates were evaluated over a 140-graph, 35-year coverage frame. This broad candidate pool is critical: it reduces cherry-picking pressure and allows class-diverse shortlisting under transparent criteria (Evidence: CLM-0026, CLM-0028, CLM-0029).

Coverage framing is strict. A finding can be surprising and still be demoted if coverage is weak. Atlas prefers findings that are interpretable and persistent, then uses class diversity constraints to prevent overconcentration in one mechanism family.

### 12.2 Diversity Constraint and Public Subset Policy

Atlas top-10 class composition is fixed to include multiple mechanism families. In the current package the mix is 4 reversal, 3 mediation, 2 threshold, and 1 outcome-surprise. This prevents top findings from collapsing into sign-reversal monoculture and improves policy interpretability because each class requires different design responses (Evidence: CLM-0030).

The public top-4 subset preserves one finding from each class family: F02 reversal, F08 mediation, F06 threshold, and F01 outcome-surprise. This selection policy was explicitly chosen to balance public clarity and methodological honesty (Evidence: CLM-0031, CLM-0032).

### 12.3 Finding-Level Reliability Practices

Each public finding includes four minimum evidence fields: availability, effect summary, uncertainty flags, and caveat language. Availability provides robustness context. Effect summary provides directional and magnitude context. Uncertainty flags identify risk type. Caveat language translates risk type into practical interpretation limits.

This structure directly addresses common miscommunication patterns. Without availability, readers overgeneralize narrow findings. Without uncertainty flags, readers overtrust fluent prose. Without caveats, policy translation becomes headline-driven and brittle.

## 13. Replication Workflow

### 13.1 What a Reproducer Needs

An independent reproducer needs the registry set, findings package JSON, and runtime validation artifacts. Atlas narrative outputs were generated from registered claims and findings package values, then checked for cross-document consistency. This means a reproducer can validate narrative numbers without recomputing the entire causal pipeline.

For full computational replication, the reproducer should also use stage-level scripts and frozen artifacts from V2.1/V3.1 lineage paths. Atlas provides these in the repository with accompanying documentation and checkpoints.

### 13.2 Replication Sequence

First, load claim registry and validate core metrics against evidence IDs. Second, load findings package and verify F01/F02/F06/F08 values used in narrative sections. Third, run consistency checks across documents for canonical metrics. Fourth, review human gate logs and ensure pending reviews are completed before publication.

This sequence separates mechanical verification from judgment calls. Mechanical checks confirm numeric and citation integrity. Human gates evaluate scientific framing, caveat adequacy, and readability for target audiences.

### 13.3 Reproducibility Boundaries

Atlas reproducibility in this phase is document-reproducibility, not model-retraining reproducibility. The goal is to regenerate narrative outputs from frozen claims and artifact references. This keeps publication workflows stable even when full model reruns are expensive.

If model reruns are performed later, Atlas recommends creating a new claim snapshot rather than editing historical claim values in place. This preserves lineage clarity across releases.

## 14. Extended Validity Threats

### 14.1 Internal Validity Threats

Internal validity can be threatened by unmeasured confounding, measurement noise, and finite-sample instability in conditional tests. Atlas mitigates these threats through staged filtering, bootstrap retention, and uncertainty-forward reporting, but does not claim elimination of threat sources.

A critical internal threat is interpretation drift when users treat predictive contribution signals as direct intervention effects. Atlas addresses this by pairing SHAP interpretation with causal-edge context and by blocking deterministic policy claims.

### 14.2 External Validity Threats

External validity is limited by context transfer. Even high-coverage findings can change behavior when applied to different institutional systems, measurement conventions, or policy implementation capacities. Atlas therefore promotes local validation before high-cost deployment.

Threshold and reversal findings are especially sensitive to external validity risk. Their value lies in identifying where simple linear transfer assumptions are unsafe, not in supplying universal policy constants.

### 14.3 Construct Validity Threats

Construct validity risk appears when indicator codes are treated as direct proxies for complex social constructs. Atlas reduces this by preserving indicator labels and source provenance in findings outputs, but construct mismatch can still occur in interpretation.

Policy teams should use Atlas outputs as structured hypotheses linked to measurable indicators, then bring local domain knowledge to validate construct meaning before implementation decisions.

### 14.4 Conclusion on Validity

Atlas does not present validity as binary pass/fail. It presents a layered evidence state: robust where coverage and persistence are high, cautious where uncertainty flags exist, and explicit where known failures constrain interpretation. That layered framing is the basis for research-grade communication in this project.


## 15. Stage-by-Stage Decision Rationale

### 15.1 Why Atlas Keeps A2 Broad

Atlas intentionally keeps A2 broader than final publication scope because early over-pruning creates irreversible information loss. If weak-but-real edges are removed before structural testing, later stages cannot recover them. The A2 design therefore accepts a larger candidate set and relies on downstream structure and stability checks for reliability contraction.

This approach is computationally heavier than aggressive pre-pruning, but it is more defensible for causal discovery where omitted pathways can bias interpretation. The A2-to-A3-to-A4 contraction sequence reflects this philosophy: preserve options early, enforce reliability later.

### 15.2 Why Atlas Uses Structural and Stability Filters Separately

Combining structure and stability in one stage can hide failure origin. If an edge disappears, reviewers should know whether it failed conditional-independence logic or bootstrap stability logic. Atlas separates these steps so errors and disagreements are diagnosable.

This separation also improves documentation quality. Methodology sections can explain each stage with clear assumptions, and reviewers can reproduce stage-level outputs independently.

### 15.3 Why Atlas Prioritizes Class Diversity in Findings

A robustness-only ranking can over-select one class, typically reversals, because they are easy to detect across strata. Atlas adds class diversity constraints so public outputs represent multiple mechanism families. This improves decision utility because different mechanism classes imply different policy actions.

The class-diverse top-4 policy subset is therefore a methodological choice tied to usability and rigor. It reduces narrative bias and forces explicit communication of heterogeneous uncertainty types.

## 16. Documentation and Publication Controls

### 16.1 Narrative Conversion Controls

Narrative conversion in Atlas follows strict controls to prevent registry-style dumping and unsupported prose inflation. Drafting packets are section-bounded, evidence-bounded, and reviewed for caveat completeness. Documents are regenerated when quality checks fail rather than patched with ad hoc edits.

A key control is citation placement. Atlas requires evidence tags in quantitative paragraphs and disallows replacing prose with claim-ID lists. This preserves readability without sacrificing traceability.

### 16.2 Human Gate Design

The human-gate model has three checkpoints with distinct purposes. H1 tests finding strength and mechanistic credibility. H2 tests scientific framing and caveat adequacy at full-draft level. H3 tests publication readiness and fresh-reader trust in policy outputs.

Separating these gates prevents late-stage surprises. If weak findings are identified at H1, the team can reframe early. If framing gaps are identified at H2, targeted revisions can be made before public packaging.

### 16.3 Freeze and Audit Rules

Atlas freeze policy requires contradiction closure, citation integrity checks, and stable claim snapshots before final publication. This ensures documents are generated from a coherent evidence state. If claims change after freeze, a new snapshot and rerun are required.

This rule avoids silent drift where prose stays fixed but underlying numbers change. The project treats that drift as a scientific integrity risk.

## 17. Extended Reproducibility Checklist

### 17.1 Minimum Reproduction Artifacts

To reproduce this narrative package, reviewers should verify claim registry values, findings package values, and generated QA/consistency outputs. If these three checks pass, the narrative can be considered numerically aligned to the frozen evidence state.

For deeper reproduction, reviewers can inspect stage documentation and scripts in V2.1 and V3.1 to confirm method implementation details. Atlas keeps these assets in-repo to support transparent methods review.

### 17.2 Recommended Review Order

Recommended review order is: methods counts, findings values, uncertainty flags, then policy implications. This order reduces the chance of evaluating recommendations before checking evidence quality.

For each finding, reviewers should ask four questions: Is availability high? Is direction stable? Are intervals informative? Are caveats proportional to uncertainty? Atlas templates are designed to make these checks fast.

### 17.3 What Counts as Publication-Ready

Publication readiness in Atlas means more than complete prose. It means complete traceability, explicit limitations, and consistent numbers across all released documents. Pending human gates must be resolved before final external release.

This definition intentionally sets a higher bar than internal draft readiness. The difference protects credibility in public and academic contexts.


## 18. Practical Audit Playbook

### 18.1 How to Audit a Single Quantitative Claim

A robust audit of one claim follows a reproducible loop. First, locate the claim sentence in narrative text. Second, identify the claim ID in the paragraph citation. Third, open claim registry and confirm claim value and key. Fourth, resolve evidence ID in evidence ledger and check artifact path. Fifth, verify the artifact value directly in source file. Sixth, return to narrative context and confirm interpretation is proportional to the value.

This six-step loop matters because errors can occur at any layer: wrong value, stale value, wrong artifact, or overstated interpretation. Atlas documentation is designed so each failure point is visible and correctable.

### 18.2 How to Audit a Finding Narrative

For finding narratives, audit sequence starts with availability, then effect metrics, then uncertainty flags, then policy language. Availability checks confirm robustness baseline. Effect checks confirm sign and magnitude claims. Uncertainty checks confirm caveat requirements. Policy-language checks confirm recommendations do not exceed evidence scope.

If any one layer fails, the section should be revised before publication. Atlas treats this as a quality gate rather than optional review.

### 18.3 How to Audit Scope and Version Drift

Version drift risk is high in multi-iteration projects. Atlas controls this by freezing claim snapshots and requiring contradiction closure before narrative generation. Auditors should verify that claim snapshot date, findings package date, and document generation date are aligned. If they are not aligned, publication should pause until alignment is restored.

Auditors should also verify unresolved contradiction count and open-question status. A low unresolved count does not guarantee correctness, but high unresolved count is a clear publication risk. Current unresolved contradiction count is zero in this package state (Evidence: CLM-0051).

### 18.4 Audit Outcomes and Action Classes

Atlas uses three outcome classes for audits. Class A: no changes required. Class B: minor wording or rounding corrections with no claim-value change. Class C: value or caveat defects requiring targeted redraft. Class C findings must be resolved before release.

This classification prevents overreaction to stylistic issues while ensuring numerical and caveat defects receive immediate attention.

### 18.5 Why This Playbook Is Included in Methodology

Many methodology documents explain algorithms but not publication controls. Atlas includes both because publication control is where high-quality analysis can still fail. A reproducible model without reproducible reporting is insufficient for research-grade communication.

The audit playbook also improves onboarding for new collaborators. Team members can contribute to review without needing full pipeline implementation context, because claim-level audit steps are explicit and mechanical.


## 19. Research-Grade Writing Standards Applied in This Conversion

Atlas applies a writing standard designed for mixed audiences without sacrificing evidence discipline. The standard has five rules. First, define technical terms at first use. Second, pair each major quantitative statement with interpretation. Third, include caveat paragraphs for uncertainty-flagged findings. Fourth, preserve one-to-one mapping between narrative claims and evidence anchors. Fifth, separate method description from policy recommendation language.

These rules are operationalized through pre-flight checks, generation constraints, and post-generation audits. They are not left to editor preference. This is important in long projects where many collaborators contribute across phases and style drift can introduce subtle overclaiming.

The writing standard also reduces “registry prose” failure mode. Registry prose lists values without explaining what they mean, why they matter, or what limits they have. Atlas narrative sections explicitly add interpretation and limitation language so readers can evaluate both significance and uncertainty.

A related standard is caveat proportionality. Caveats are not generic disclaimers added at the end of documents. They are tied to specific uncertainty classes and inserted in the same section as the related finding. This local caveat placement improves reader calibration and reduces selective interpretation.

Finally, Atlas requires that AI-assistance disclosure be explicit and bounded. Disclosure includes what AI did, what AI did not do, and how human review gates govern final acceptance. This keeps method trust grounded in workflow controls rather than tool branding.


## 20. Final Methodological Position

The methodological position of Atlas can be summarized as staged inference plus governed communication. Staged inference means no single statistic carries the full causal burden; evidence accumulates through temporal, structural, and stability filters. Governed communication means findings are publishable only when provenance, uncertainty, and failure context are visible in the same narrative surface.

This position is intentionally conservative, but it is also practical. It allows Atlas to support policy-relevant analysis at scale while reducing avoidable overclaiming risk. For a six-month, multi-iteration project with heterogeneous data and multiple audiences, this balance is the most defensible path to research-grade output.


### 20.1 Practical Takeaway for Replication Teams

Replication teams should treat Atlas as a package-level system. Verifying only model outputs is not enough; verify claim registries, evidence mappings, and caveat completeness together. When these layers are checked jointly, reviewers can distinguish numerical correctness from interpretive correctness and identify exactly where revisions are needed.


Atlas publication policy treats methodological transparency as part of result validity. A result without traceable evidence and uncertainty framing is considered incomplete, even when the underlying computation is correct.

Method rigor and communication rigor are treated as one integrated research obligation in Atlas.


This principle guides every conversion step in the present narrative package and is enforced through automated and human review gates.


## 21. Extended Methodological Notes for Reviewers

### 21.1 Why Atlas Treats Uncertainty as a Primary Output

Atlas treats uncertainty as a primary output because policy harm often comes from overconfident interpretation, not from model imperfection alone. In practical settings, decision makers rarely inspect raw model artifacts. They act on summaries, briefs, and recommendations. If those summaries suppress uncertainty, even statistically careful models can be operationally unsafe.

For this reason Atlas embeds uncertainty in finding-level narrative structure rather than in distant appendices. Each anchor finding includes a dedicated caveat paragraph that explains uncertainty type in plain terms. Reversal findings emphasize transfer risk across strata. Threshold findings emphasize regime-position dependence and interval sparsity. Mediation findings emphasize pathway confidence versus magnitude confidence. Stable-upstream findings emphasize non-determinism despite persistence.

This pattern was selected because it is auditable and teachable. New reviewers can inspect one section and immediately check whether caveat language matches uncertainty flags. Policy teams can also reuse the same language in implementation memos without reinterpreting technical metadata.

### 21.2 How Atlas Balances Scientific Detail and Readability

A recurring challenge in long-form methodology documents is balancing technical depth with readability. Atlas addresses this by using a layered explanation strategy. Each stage is first explained in intuitive language, then linked to statistical rationale, then bounded by limitations. This sequence preserves readability for non-specialist readers while still giving specialists enough detail to evaluate method validity.

Atlas also avoids table-only communication for core methods. Tables and counts are useful references, but they do not explain why choices were made or how limitations affect interpretation. Narrative explanation is therefore required for every major quantitative section.

### 21.3 Reviewer Checklist for Method Sections

Reviewers can use a short method checklist: does each stage include purpose, method, assumptions, and limitations? Are key counts traceable to claim IDs? Are known failures documented with replacement decisions? Are public recommendations consistent with simulation framing limits? If all checks pass, the method narrative is likely publication-ready pending final human gates.

### 21.4 Evidence Scope Discipline in Practice

Scope discipline was enforced throughout this conversion. Quantitative Atlas claims were sourced from registries and findings package artifacts. Contextual method descriptions were drawn from repository documents already in-project. New external empirical claims were excluded in line with scope policy. This protected the narrative from accidental claim inflation during drafting.

### 21.5 Closing Extension

This extended note exists to help reviewers evaluate not just whether Atlas has methods, but whether Atlas explains those methods in a way that can be scrutinized, replicated, and responsibly used. The core standard remains unchanged: traceable claims, explicit uncertainty, documented failures, and human-reviewed interpretation.


Additional reviewer note: publication readiness requires completion of H1, H2, and H3 human gates with explicit rationale logs, even when automated QA and consistency checks pass. This requirement protects against overreliance on automation in final scientific judgment.


Method summary extension: Atlas combines staged causal inference, runtime hardening, and evidence-governed narrative conversion as one integrated research process. Each layer is auditable, and each published claim is constrained by traceability and uncertainty policy.


These safeguards are designed for long-duration, multi-artifact projects where credibility depends on both statistical rigor and reporting discipline.

Final checkpoint statement: transparency, traceability, and caveat discipline are mandatory release conditions in Atlas.

Release discipline remains non-negotiable across all Atlas narrative outputs.
