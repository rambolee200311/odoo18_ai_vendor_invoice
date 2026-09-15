# CC-16 — Extraction Profile Framework & UPS Profile Baseline

**Status: FROZEN — NOT AUTHORIZED FOR CODING**

**Method:** GREENFIELD DESIGN
**Predecessors:** CC-15 Markdown Extraction Production Baseline (FROZEN), SPIKE-UPS-INVOICE-001, CC-11 / CC-13 Statement-first Architecture

> This document is a design contract only. It authorizes no production coding,
> Prompt changes, Schema changes, database migration, test changes, or runtime
> experiment.

## 1. Intent

CC-16 defines an Extraction Profile Framework for document-specific extraction
semantics while preserving one common import pipeline and one Canonical result.
The default policy is:

> Generic First, Profile When Needed.

An unknown document uses the Generic Profile. A specialized Profile is justified
only after a stable, reproducible semantic gap is demonstrated. UPS is the
baseline Profile specification; this Contract does not implement it.

## 2. Background and Boundary

The current extraction flow is:

```text
PDF / Markdown / rendered images
              ↓
         Input Mode
              ↓
          Provider
              ↓
        Prompt Registry
              ↓
    Structured Extraction
              ↓
          Canonical
              ↓
         Statement
```

The UPS Spike demonstrated structural compatibility: 31 business records could
be represented by the existing Generic contract. UAT additionally identified
semantic areas that may require a specialized interpretation, including Returned
Date, Charge / Discount / Net Charge, Original Tracking Number, Return Reason,
and Pickup Request meaning. Structural compatibility is not semantic
completeness.

## 3. Goals

The framework must:

- keep the existing Task, Attempt, Provider, Input Mode, Canonical, Projection,
  Statement, retry, queue, audit, and error-handling pipeline;
- make Generic the default for all unknown documents;
- let a Profile add narrowly scoped extraction semantics without copying the
  Generic Prompt;
- keep all Profiles compatible with the same Canonical contract;
- make Profile selection deterministic and auditable;
- allow future Profiles to be added without changing the common pipeline;
- provide an explicit regression boundary around the frozen Generic Profile.

## 4. Non-Goals and Explicit Out-of-Scope

CC-16 does not implement or authorize:

- DHL, FedEx, DPD, GLS, TNT, Maersk, or DSV Profiles;
- an OCR Profile;
- Canonical V2 or a supplier-specific Canonical;
- a new Provider or a new import pipeline;
- Batch, Queue, Retry, Statement, Task, or AI Workspace redesign;
- changes to the CC-15 Generic, Native PDF, Markdown, or Vision Prompts;
- changes to the CC-15 Canonical or Projection;
- production coding;
- Prompt implementation;
- UPS parsing implementation;
- database migration;
- tests or TDD changes;
- User Guide changes;
- administrative Profile configuration UI.

## 5. Core Terminology

### 5.1 Extraction Profile

An Extraction Profile is a code-managed, immutable registry entry containing
document-semantic extraction rules layered above an Input Mode Prompt. It
defines how a document family should preserve facts and labels that Generic
extraction cannot reliably express without semantic loss.

A Profile is not:

- a Provider;
- an Input Mode;
- a supplier model;
- a separate parser pipeline;
- a separate Canonical;
- a Statement type.

### 5.2 Generic Profile

Generic is the mandatory default Profile. It represents the current frozen
behavior and applies when no specialized Profile is mapped to the supplier.
Generic is not a silent fallback for an explicitly selected but invalid or
incompatible specialized Profile.

### 5.3 Specialized Profile

A specialized Profile adds semantic rules for a documented document family. It
must be smaller than a replacement Prompt: it may add terminology, field
preservation requirements, record-family distinctions, and normalization
constraints, but must not duplicate the full Generic contract. In CC-16 v1,
Profiles are code-managed and immutable; administrative lifecycle and version
management are future work.

## 6. Profile Model

CC-16 v1 uses a code-managed Profile Registry. It contains a small immutable
set of entries such as `generic` and `ups_transport_v1`; it is not an Odoo
configuration model.

| Attribute | Contract |
|---|---|
| Profile key | Stable machine identity, independent of display name |
| Display name | Human-readable name |
| Version | Immutable semantic version of the Profile rules |
| Input Mode relationship | No ownership; the Profile Extension composes with the selected Input-Mode Prompt |
| Document family | Semantic classification, not a runtime discovery mechanism |
| Extension reference | Reference to the registered Prompt/semantic extension |
| Evidence | UAT, Spike, sample set, and known limitations |

A material semantic change creates a new immutable registry entry/version. Draft,
Active, Deprecated, administrator priority, effective dates, and dynamic
activation are deferred until a future configurable Profile model is justified.

## 7. Profile Resolver

### 7.1 Resolver Inputs

CC-16 v1 intentionally limits resolver inputs to:

1. explicit Profile assignment, when supplied by a trusted caller;
2. identified supplier identity from a trusted pre-extraction source and its
   code-managed Profile mapping;
3. selected Provider and Input Mode, only for compatibility validation.

The trusted supplier source is external to the current AI extraction result for
the same Attempt. A supplier name extracted by that Attempt MUST NOT select a
Profile for that Attempt. If no trusted pre-extraction supplier identity exists
and no explicit Profile is supplied, the Resolver selects Generic.

VAT, country, currency, filename, and inferred document family are not v1
selection signals. `document_family` remains a Profile semantic classification,
not a runtime pre-classification step.

### 7.2 Matching Order

The Resolver applies this order:

1. validate an explicit Profile assignment, if one exists;
2. otherwise resolve an exact supplier-to-Profile mapping;
3. otherwise select Generic.

There is no v1 specificity ranking or priority engine. Duplicate supplier
mappings and incompatible mappings are configuration errors.

### 7.3 Fallback

The following cases are distinct:

- **No specialized Profile mapped:** select Generic.
- **Explicit or supplier-mapped specialized Profile is valid:** select that
  Profile.
- **Explicit or supplier-mapped specialized Profile is invalid, missing, or
  incompatible with Provider/Input Mode:** raise a
  controlled resolution error; do not silently select Generic.

No resolver outcome may change Provider or Input Mode. A Profile cannot silently
force Native PDF, Markdown, Vision, GPT, or DeepSeek.

### 7.4 Resolver Sequence

```text
Task / Parse request
        │
        ├─ explicit Profile assignment
        ├─ identified supplier mapping
        ├─ selected Provider
        └─ selected Input Mode
        ↓
Profile Resolver
        │
        ├─ explicit assignment valid? ── yes → assigned Profile
        ├─ explicit/mapped Profile invalid? ── error
        │
        ├─ supplier mapping exists? ── yes → mapped Profile
        │
        └─ no mapping → Generic Profile
        ↓
Prompt Composition
        ↓
Existing Provider + Input Adapter
        ↓
Existing Structured Extraction → Existing Canonical
```

## 8. Generic Profile Contract

Generic is the frozen baseline, not an incomplete placeholder. It must:

- support all currently supported Input Modes;
- preserve existing Provider selection;
- preserve existing Prompt Registry ownership;
- preserve existing Canonical field meanings;
- preserve current fallback and error behavior;
- remain the result for unknown suppliers and unproven document families;
- avoid supplier-specific assumptions.

No specialized Profile may change Generic behavior by modifying shared Generic
Prompt text or shared fallback semantics.

## 9. UPS Profile Baseline

The UPS Profile is a specification baseline only. It is not an implementation
authorization.

### 9.1 Confirmed UAT Requirements

The current evidence supports only these UPS Profile requirements:

- preserve the explicit Returned Date semantic without inferring that it is a
  Loading Date or Unloading Date;
- preserve Charge, Discount, and Net Charge together for a charge component.

These are the minimum semantic extensions eligible for the first UPS Profile.
They are business requirements, not an assumption that the current Canonical
already has lossless target fields for them. If the existing Canonical cannot
represent either requirement without semantic loss, the implementation must
surface a Canonical contract gap. It must not create UPS-specific storage or
force the fact into an unrelated Canonical field.

### 9.2 UAT Observations Pending Evidence

The following observations are not frozen as UPS Profile requirements. They
remain candidates for the continued manual UAT corpus:

- Original Tracking Number;
- Return Reason;
- Pickup Request typed semantics;
- Adjustment typed semantics;
- Shipped From / Returned To labels;
- package count and service description;
- line-level tax rate, tax amount, and printed tax label.

They may become Profile requirements only after repeated, reproducible evidence
shows that Generic extraction loses a business fact that must be preserved.

### 9.3 UPS Override vs Addition Matrix

| Concern | Generic behavior | UPS Profile behavior | Type |
|---|---|---|---|
| Business-record granularity | One independent business record per line | Existing Generic behavior remains the baseline | Observe |
| Returned Date | Generic date mapping | Preserve the explicit Returned Date semantic; prohibit unsupported inference to Loading/Unloading Date | Confirmed requirement |
| Charge details | Label and amount | Preserve Charge, Discount, and Net Charge together | Confirmed addition |
| Tracking references | Generic reconciliation clues | Candidate: preserve current and Original Tracking separately | Pending |
| Return reason | Generic may omit an unclassified fact | Candidate: preserve explicit Return Reason | Pending |
| Pickup Request | Generic transport record | Candidate: preserve typed Pickup Request meaning | Pending |
| Tax | Generic explicit tax handling | Candidate: preserve UPS line-level tax semantics | Pending |
| Canonical | Existing shared Canonical | Use only if it represents the confirmed requirement losslessly; otherwise surface a Canonical gap | Constraint |
| Statement | Existing Statement | Same Statement and line model | Constraint |

The UPS Profile must not copy the Generic Prompt. It specifies only the
additional semantics that Generic does not reliably preserve.

## 10. Prompt Composition Contract

CC-16 does not redefine CC-15 Prompt ownership. Composition starts from the
existing Input-Mode Prompt Registry result:

```text
prompt_for_mode(input_mode)
        +
Profile Extension
```

The selected Provider continues to own Provider transport instructions, and the
existing Input Mode continues to select the baseline Prompt family. A Profile
Extension is composed on top of that existing Input-Mode Prompt result.
Profile Extensions must:

- declare their Profile key and version;
- contain only additive or explicitly scoped semantic rules;
- not repeat the existing Input-Mode Prompt, schema, safety rules, or transport
  instructions;
- not select a Provider or Input Mode;
- not change the Canonical shape;
- be checksumed and recorded in Attempt evidence.

If a Profile Extension conflicts with the existing Input-Mode Prompt contract,
the Profile is invalid and cannot be selected.

## 11. Canonical Compatibility

All Profiles target the existing Canonical contract. There is no UPS Canonical,
DHL Canonical, or Canonical V2 in CC-16. Compatibility must be demonstrated for
each confirmed semantic requirement; it must not be assumed from the existence
of a similarly named generic field.

When the existing Canonical can represent a Profile fact losslessly, the fact
may use existing generic locations and labels, such as:

- description;
- charge details;
- reconciliation clues;
- line tax fields;
- existing header and line values.

If a confirmed Profile requirement cannot be represented without semantic loss,
the result is a Canonical contract gap. It must be surfaced for Canonical
design review; it is not permission to introduce UPS-specific storage or force
the fact into an unrelated Canonical field.

## 12. Statement Compatibility

Statement remains unaware of Profile semantics. It consumes the same Canonical
projection and retains the existing Statement-first lifecycle.

Task may expose the resolved Profile for operational context, but it is not the
authority for historical extraction semantics. ParseAttempt **MUST** snapshot
the Profile key, Profile version, Profile Extension version, and Extension
checksum that were actually executed. This snapshot is an audit fact for each
Attempt, including Generic.

Profile selection must not create a new Task type, Attempt type, Statement
type, or UI workflow. No Statement authority is delegated to Profile.

Provider does not own Profile. Provider only executes the selected extraction
contract. Input Mode remains independent and continues to distinguish Native
PDF, Markdown, and rendered images.

The UI is not required to display Profile in CC-16. Audit evidence must still
make the selected Profile visible to diagnostics and reviewers.

## 13. Future Configurable Profile Model

The code-managed registry is the only v1 model. A future phase may explore
administration configuration. The following are non-contractual examples only,
not frozen requirements:

- Supplier Mapping;
- VAT and country matching;
- document-family assignment;
- Profile assignment;
- Profile priority;
- Profile activation and lifecycle;
- Prompt Extension version and checksum.

This is deferred design only. CC-16 does not implement an administration UI,
configuration views, access rules, database records, Draft/Active/Deprecated
lifecycle, or a priority engine.

## 14. Architecture Diagram

```text
                         Common Pipeline
                               │
                    Profile Resolver
                               │
                   prompt_for_mode(input_mode)
                               │
                 ┌─────────────┴─────────────┐
                 │                           │
           Generic Profile             Specialized Profile
           (frozen default)             (UPS / future families)
                 │                           │
                 └─────────────┬─────────────┘
                               │
                        Profile Extension
                               │
                    Provider / Input Adapter
                               │
                    Structured Extraction
                               │
                         Common Canonical
                               │
                          Projection
                               │
                           Statement
```

## 15. Prompt Composition Diagram

```text
Existing prompt_for_mode(input_mode)
          │
          ├── CC-15 Input-Mode Prompt
          └── Existing transport/schema contract
                    │
                    + Profile Extension
                      ├── Confirmed UPS semantic rules
                      └── Profile-specific additions only
                    │
                    ↓
             Final Profiled Prompt
                    │
                    ↓
          Existing Provider / Input Mode
```

## 16. Generic Regression Protection

Before any Profile is activated, the implementation phase must demonstrate:

- Generic Prompt checksum is unchanged;
- Generic Profile output is unchanged for the existing regression corpus;
- existing Markdown, Native PDF, and Vision routes remain selectable;
- unknown suppliers still resolve to Generic;
- no-match fallback selects Generic, while an invalid mapped Profile produces a
  controlled error;
- fallback does not change Provider or Input Mode;
- historical Attempts remain auditable;
- every ParseAttempt snapshots the actual Profile key/version and Extension
  checksum;
- a specialized Profile cannot alter Generic behavior through shared mutable
  configuration;
- line counts, header values, and existing Canonical fields remain compatible
  for pre-existing transport invoices.

These are implementation acceptance criteria for a future authorized phase, not
tests to be added under this Draft.

## 17. Required Decisions

| Question | Decision |
|---|---|
| 1. Does Profile belong to Prompt Registry? | **Partially.** The existing Prompt Registry remains the owner of Input-Mode Prompt families. Profile owns only a code-managed extension reference; it does not replace or restructure the Registry. |
| 2. Does Profile belong to Provider? | **No.** Provider executes extraction and transport; Profile expresses document semantics. |
| 3. Does Profile belong to Input Mode? | **No.** Input Mode remains a transport distinction. A Profile may declare compatible modes but may not switch modes. |
| 4. Does Profile belong to Supplier? | **No.** Supplier mapping is the v1 resolver assignment mechanism, not the semantic owner. A Profile may later serve several suppliers. |
| 5. Does Profile belong to Document Family? | **Yes, as a semantic classification.** In v1 it is not inferred at runtime; it does not participate in Profile selection. |
| 6. How is Generic Regression protected? | Keep the CC-15 Input-Mode Prompt Registry unchanged, keep Profile Extensions additive, use Generic only for no-match cases, error on invalid mapped Profiles, snapshot Attempt evidence, and require a regression gate before activation. |
| 7. How can a Profile be added without changing the Pipeline? | Add an immutable code-managed registry entry and supplier mapping with a Prompt Extension; the common resolver, `prompt_for_mode`, Provider, Canonical, Projection, and Statement contracts remain unchanged. |

## 18. Acceptance Criteria for a Future Implementation

The future implementation may be considered aligned with CC-16 only if:

- Generic remains the default;
- Generic behavior and checksum are unchanged;
- Profile selection is deterministic and auditable;
- Profile registry entries are immutable;
- no-match resolution selects Generic;
- invalid explicit or supplier-mapped Profiles produce a controlled error;
- Profile resolution does not switch Provider or Input Mode;
- every ParseAttempt snapshots the actual Profile key/version, Extension version,
  and Extension checksum;
- all Profiles produce the same Canonical contract;
- UPS semantics are represented as a narrow extension, not a copied Prompt;
- Statement-first architecture remains unchanged;
- no supplier-specific parser pipeline is introduced;
- no out-of-scope module is changed.

## 19. Not Implemented in CC-16

This Contract implements nothing.

Specifically not implemented:

- Production coding;
- Prompt implementation;
- UPS parsing implementation;
- Database migration;
- Tests;
- TDD changes;
- User Guide changes;
- Profile administration UI and configurable Profile lifecycle;
- Generic Prompt changes;
- Canonical changes;
- Projection changes;
- Provider changes;
- Task, Statement, Queue, Retry, or Batch redesign. The required ParseAttempt
  audit snapshot is a contract decision for the future implementation, not
  implemented by this Draft.

**Final status: FROZEN — NOT AUTHORIZED FOR CODING.**
