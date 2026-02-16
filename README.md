# omop_semantics

**omop_semantics** is a Python library for defining and managing **semantic conventions on top of OMOP CDM**.

It lets you describe conventions in code

- which OMOP concepts you want to have on hand as named key concepts to improve ergonomics in analytic code,
- how they are grouped,
- what roles they play 
- and provide profiles to render these targets uniformly into CDM tables.

The goal is to make these conventions **explicit, versioned, and reusable**, instead of being buried in code, SQL, or documentation. They are also extensible so that you can add opinionated layers on top of default specifications that may be relevant in a domain-specific context only.

---

## Key ideas

- **Human-authored**  
  Semantic rules and concept groups are written in YAML and validated with schemas.

- **Portable**  
  No database or graph store required.

- **Versionable**  
  Conventions can evolve over time and be tracked in git.

- **Integrates with pipelines**  
  Can drive ETL logic, validation, and documentation so they stay in sync.

---

## Typical workflow

1. **Define a schema**  
   Describes what kinds of semantic objects and roles exist (e.g. staging, modifiers).

2. **Write YAML instances**  
   Lists actual OMOP concepts and groups used in your project.

3. **Load a runtime registry**  
   This gives you a programmatic API to query concepts, groups, and relationships.

4. **Use it in code**  
   For validation, cohort logic, ETL constraints, or documentation.

---

## When should you use this?

Use **omop_semantics** if you:

- have project-specific rules about which OMOP concepts are valid,  
- need consistent concept groupings across ETL and analytics,  
- want semantic conventions to be explicit, testable, and versioned,  
- are working in domains like oncology where OMOP alone is too permissive.
