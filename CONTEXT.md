# Colav-Simulator Validation

Language for assembling and running maritime collision-avoidance validation sessions.

## Language

**Validation Draft**:
An editable proposed configuration for one validation run. It is distinct from the specification owned by the current session.
_Avoid_: Active configuration, applied configuration

**Run Specification**:
An immutable configuration snapshot submitted to create a validation session.
_Avoid_: Draft, live configuration

**Exact Tuple**:
A Rule, Scenario, Algorithm, and Tracker combination recognized by the capability catalog as one indivisible execution choice.
_Avoid_: Cartesian product, independent selections

**Verified Tuple**:
An Exact Tuple backed by the catalog's verified capability evidence. Its evidence applies to that tuple, not to every use of its Algorithm or Tracker.
_Avoid_: Globally validated algorithm

**Experimental Tuple**:
An Exact Tuple permitted for experimental execution without the evidence claim of a Verified Tuple.
_Avoid_: Verified, G3 qualified

**Active Session**:
The system's single current validation session and its authoritative Run Specification.
_Avoid_: Current Draft, concurrent run
