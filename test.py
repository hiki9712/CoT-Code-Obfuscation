from pymongo import MongoClient

client = MongoClient("mongodb://localhost:27017")
db = client['policy']
strategies = db["strategies"]
failures = db["failure_strategies"]
strategy = {
  "_id": "STR_CONTROL_FLOW_FLATTENING_V2",

  "meta": {
    "name": "Control Flow Flattening",
    "version": "v2",
    "category": "control_flow",
    "tags": [
      "break_linear_reasoning",
      "state_machine",
      "dispatcher"
    ],
    "description": "Rewrite structured control flow into a dispatcher-based state machine",
    "created_by": "agent",
    "created_at": "2025-03-18"
  },

  "applicability": {
    "languages": ["Python", "C++"],
    "cwe": ["CWE-79", "CWE-416"],
    "paradigm": ["procedural", "object_oriented"],
    "code_granularity": ["function", "block"]
  },

  "preconditions": {
    "ast_must_contain": ["if", "loop"],
    "ast_must_not_contain": ["goto"],
    "requires": ["basic_block"],
    "avoid": ["eval", "exec"],
    "complexity_limit": "medium"
  },

  "transformation": {
    "type": "control_flow_rewrite",
    "mechanism": "dispatcher_state_machine",
    "abstract_steps": [
      "introduce state variable",
      "map basic blocks to states",
      "replace branches with state transitions",
      "dispatch via loop or switch"
    ]
  },

  "constraints": {
    "semantic_preserving": True,
    "no_dynamic_eval": True,
    "no_external_dependency": True,
    "max_code_bloat": "moderate"
  },

  "effects": {
    "static_analysis_evasion": True,
    "cot_instability": "high",
    "llm_confusion_signals": [
      "inconsistent control-flow explanation",
      "hallucinated execution paths"
    ]
  },

  "stats": {
    "priority": 0.72,
    "success_count": 8,
    "failure_count": 2,
    "avg_phi": 0.68,
    "transferability": 0.51,
    "last_used": "2025-03-15"
  },

  "history": {
    "failure_reasons": [
      "Detected when state machine is too shallow",
      "Flagged under deep reasoning depth"
    ],
    "notes": "Combine with API indirection for stronger effect"
  },

  "relations": {
    "composable_with": [
      "STR_STRING_ENCODING_BASE64",
      "STR_API_INDIRECTION"
    ],
    "conflicts_with": [
      "STR_INLINE_EVAL"
    ],
    "derived_from": "STR_CONTROL_FLOW_FLATTENING_V1"
  }
}


#strategies.insert_one(strategy)
candidates = list(strategies.find({
    "applicability.languages": "Python"
}).sort("priority", -1).limit(5))
print(candidates)