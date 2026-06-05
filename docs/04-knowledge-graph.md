# 04 — Knowledge Graph Schema

OSINTENAL uses **graph-native storage**. The graph is the shared state of the quorum; it is
a *materialized view* over the append-only Provenance Ledger (doc 03 §13), which guarantees
replay and tamper-evidence. **Nothing enters the graph without a source.**

## 1. Backend Strategy

| Phase | Backend | Why |
|-------|---------|-----|
| 1 (dev/default) | **Embedded graph engine over SQLite** (e.g. Kùzu, or a thin property-graph layer on SQLite) + SQLite ledger table | Zero-ops, laptop-runnable, transactional, easy replay/tests |
| 3+ (scale) | **Neo4j** (or compatible) via the same `GraphStore` port | Cypher, mature viz, clustering |

The graph is accessed only through a `GraphStore` port (interface), so the backend is
swappable without touching agents. Two operations exist: **write** (runtime-only, always via a
ledger event) and **read** (`GraphView`, available to agents).

## 2. Node Types

Every node carries a common envelope: `node_id` (UUIDv7), `node_type`, `epistemic_class`,
`provenance` (doc 03 §1), `created_event_id`, `attributes` (type-specific), and
`confidence` where applicable.

Node types (**but not limited to** — the schema is extensible):

| Node type | Represents | Key attributes |
|-----------|------------|----------------|
| `Person` | A natural person | names, handles, attributes (all evidence-backed) |
| `Organization` | Company/group/agency | names, registrations, domains |
| `Domain` | DNS domain | fqdn, registrar, first/last seen |
| `IPAddress` | IPv4/IPv6 | address, asn, geolocation (as hypotheses) |
| `Location` | Geographic place | coords, admin hierarchy, confidence radius |
| `Image` | Image artifact | hash, dimensions, exif ref, payload_ref |
| `Document` | Document artifact | hash, mime, page count, payload_ref |
| `Event` | Something that happened | time span, place ref, participants |
| `Observation` | Aggregation output (doc 03 §2) | type, content, modality |
| `EvidenceObject` | Acquired evidence (doc 03 §3) | kind, summary, structured |
| `Explanation` | A competing explanation (doc 03 §4b) | statement, `SPECULATION`/`EXTRAPOLATION`, confidence |
| `Hypothesis` | Synthesized from explanations (doc 03 §5) | statement, status, confidence_history |
| `HypothesisSet` | Group of competing explanations/hypotheses | question, residual_mass |
| `Speculation` | Possibility-engine item (doc 03 §6) | speculative_confidence, limitations |
| `Investigation` | An investigation root | objective, config, status |
| `Source` | A distinct origin of data | publisher, independence_group, reputation |

`Source` is modeled explicitly so that **source independence** (a Confidence factor) and
**source monoculture** (a UU-indicator) are computable as graph queries rather than guesses.

## 3. Edge Types

Every edge carries: `edge_id`, `edge_type`, `from`, `to`, `provenance`, `weight`
(signed strength where meaningful), `created_event_id`.

Edge types (**but not limited to** — extensible):

| Edge type | Semantics | Typical endpoints |
|-----------|-----------|-------------------|
| `owns` | ownership | Person/Org → Domain/Org/IP |
| `associated_with` | generic association | any ↔ any (weakest link) |
| `located_at` | spatial placement | Person/Org/Event/Image → Location |
| `referenced_by` | citation/mention | any → Document/Web/Source |
| `observed_in` | datum seen in artifact | Observation → Image/Document/Event |
| `supports` | evidence raises a hypothesis | EvidenceObject/Observation → Hypothesis (weight>0) |
| `contradicts` | evidence lowers a hypothesis | EvidenceObject/Observation → Hypothesis (weight<0) |
| `synthesized_from` | a hypothesis built from its explanations | Hypothesis → Explanation |
| `derived_from` | provenance/derivation | any derived node → its upstream node(s) |

**Epistemic-ladder enforcement (doc 00 §3):** an `INSIGHT` node (a promoted hypothesis) may
only attach to evidence through the `Hypothesis → synthesized_from → Explanation →
supports/contradicts → EvidenceObject → derived_from → Observation` chain. A direct
`Insight → Source` edge that skips the hypothesis/explanation layers is rejected by a
write-time constraint. This is how "no component may bypass the distinctions" becomes a
database invariant.

## 4. Provenance Binding

- Every node and edge has a `provenance` and a `created_event_id` pointing into the ledger.
- The ledger event stores the *raw* captured content hash; the node stores the *normalized*
  value. Both hashes are retained, so any normalization is auditable.
- `derived_from` edges (plus `Provenance.derived_from` ids) make the **evidence chain**
  walkable: from any `Insight` the system can produce the full reasoning chain down to
  `INFORMATION` nodes with non-derived provenance — the auditability guarantee (doc 03 §16.3).

## 5. Hypothesis Representation & Preservation

- A `HypothesisSet` node `--has_member-->` `Hypothesis` nodes (internal structural edge).
- Confidence lives in `Hypothesis.confidence_history` (append-only) — the *current* value is
  the last entry; **history is never overwritten** (Hypothesis Preservation Rule).
- Archival sets `status=archived` and severs nothing; reactivation appends a new history entry
  and a `hypothesis_reactivate` ledger event. Investigation history is always recoverable.
- `residual_mass` on the set is the explicit "none of the above" probability — a first-class
  Unknown-Unknown indicator queried by the Epistemology Agent.

## 6. Representative Queries

Expressed as Cypher-flavored sketches (the `GraphStore` port translates per backend).

**Evidence chain for an insight (audit):**
```cypher
MATCH p = (i:Insight {node_id:$id})-[:derived_from|supports*1..]->(o:Observation)
RETURN p
```

**Source independence for a hypothesis (Confidence factor):**
```cypher
MATCH (h:Hypothesis {node_id:$id})<-[:supports]-(e:EvidenceObject)-[:derived_from]->(:Source)<-[:from_source]-(s:Source)
RETURN count(DISTINCT s.independence_group) AS independent_sources
```

**Source-monoculture detector (UU-indicator):**
```cypher
MATCH (h:Hypothesis {set_id:$set})<-[:supports]-(e)-[:derived_from]->(src:Source)
WITH count(DISTINCT src.independence_group) AS groups, count(e) AS evidence
WHERE evidence >= 3 AND groups = 1
RETURN true AS source_monoculture
```

**Contradiction cluster (Skeptic / UU-indicator):**
```cypher
MATCH (h:Hypothesis {set_id:$set})<-[c:contradicts]-(e:EvidenceObject)
RETURN h.node_id, count(c) AS contradictions ORDER BY contradictions DESC
```

## 7. Consistency & Integrity Rules (write-time)

1. **Provenance-required:** rejects any node/edge lacking valid `provenance` +
   `created_event_id`.
2. **Ladder constraint:** rejects edges that skip the epistemic ladder (doc 00 §3 / §3 above).
3. **Append-only history:** `confidence_history` and the ledger are insert-only; updates that
   would overwrite history are rejected.
4. **Set minimum:** a `HypothesisSet` cannot drop below one active member via deletion;
   archival only.
5. **Speculation quarantine:** `Speculation` nodes cannot carry `supports`/`contradicts`
   edges into the normalized hypothesis sets.
6. **Hash-chain:** each ledger event links to `prev_event_hash`; a broken chain fails
   integrity verification (run in CI and on load).

## 8. Indexing & Performance

- Index `node_type`, `epistemic_class`, `investigation_id`, content hashes, `Source.independence_group`.
- Hot path is "evidence touching hypotheses in set X" and "evidence chain for node Y" —
  covered by the `supports/contradicts` and `derived_from` indexes.
- The materialized graph can always be **rebuilt from the ledger**; corruption recovery =
  replay. This also powers Investigation Replay in the dashboard (doc 06 Phase 7).

## 9. Mapping to Storage (Phase 1)

```
ledger_events(event_id PK, investigation_id, iteration, type, actor,
              payload JSON, prev_event_hash, event_hash, ts)        -- append-only
nodes(node_id PK, node_type, epistemic_class, investigation_id,
      provenance JSON, attributes JSON, created_event_id FK)
edges(edge_id PK, edge_type, from_id, to_id, weight,
      provenance JSON, created_event_id FK)
confidence_history(hypothesis_id, iteration, confidence, delta_reason,
                   by_agent, event_id FK, ts)                       -- append-only
```

Graph traversal uses the embedded engine's native graph layer (Phase 1) or recursive CTEs as
a fallback; the `GraphStore` port hides the difference from agents.
