// Auto-embedded canonical schemas for browser/pure-TS portability without filesystem IO.

export const commonSchema = {
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "common.schema.json",
  "title": "Common",
  "$comment": "v1.4. Building blocks shared by plan, step, workflow, event and tutorial-spec schemas. See contracts/README.md for the schema rules.",
  "$defs": {
    "Language": {
      "title": "Language",
      "description": "A tutorial language (#132, L3). en is the original; the others are translations. Narration: en, de, es, fr; hi and kn get captions only (L7).",
      "enum": [
        "en",
        "hi",
        "kn",
        "de",
        "es",
        "fr"
      ]
    },
    "PerformedBy": {
      "title": "PerformedBy",
      "description": "Who did a step: Krama, or the run's owner by hand in a takeover (ADR 0008).",
      "enum": [
        "krama",
        "human"
      ]
    },
    "TakeoverEndReason": {
      "title": "TakeoverEndReason",
      "description": "Why a takeover ended. handed_back: the owner said what they did; idle: 5 min without input; closed: the screen connection went away; cancelled: the run was cancelled.",
      "enum": [
        "handed_back",
        "idle",
        "closed",
        "cancelled"
      ]
    },
    "HandBackDone": {
      "title": "HandBackDone",
      "description": "What the owner did in a takeover. barrier: cleared a login wall or challenge (Krama re-checks and retries the step); step: did the paused step (Krama verifies it without acting); rest: did the rest of the task (Krama runs the final check).",
      "enum": [
        "barrier",
        "step",
        "rest"
      ]
    },
    "Risk": {
      "title": "Risk",
      "enum": [
        "low",
        "medium",
        "high"
      ]
    },
    "ActionType": {
      "title": "ActionType",
      "enum": [
        "click",
        "fill",
        "select",
        "navigate",
        "press",
        "wait"
      ]
    },
    "Action": {
      "title": "Action",
      "type": "object",
      "required": [
        "type"
      ],
      "additionalProperties": false,
      "properties": {
        "type": {
          "$ref": "#/$defs/ActionType"
        },
        "value": {
          "type": [
            "string",
            "null"
          ],
          "description": "Text to fill, option to select, URL path to navigate to, or key to press. Null for click/wait."
        }
      }
    },
    "ElementRef": {
      "title": "ElementRef",
      "type": "object",
      "description": "An element found by ARIA role and accessible name (name matched as a substring, e.g. 'Repository Name' matches 'Repository Name *').",
      "required": [
        "role",
        "name"
      ],
      "additionalProperties": false,
      "properties": {
        "role": {
          "type": "string",
          "minLength": 1
        },
        "name": {
          "type": "string",
          "minLength": 1
        }
      }
    },
    "Target": {
      "title": "Target",
      "type": "object",
      "description": "How to find the element to act on: role + name first, CSS selector as a fallback.",
      "additionalProperties": false,
      "properties": {
        "role": {
          "type": [
            "string",
            "null"
          ]
        },
        "name": {
          "type": [
            "string",
            "null"
          ]
        },
        "selector": {
          "type": [
            "string",
            "null"
          ]
        }
      }
    },
    "FieldValue": {
      "title": "FieldValue",
      "type": "object",
      "required": [
        "role",
        "name",
        "value"
      ],
      "additionalProperties": false,
      "properties": {
        "role": {
          "type": "string",
          "minLength": 1
        },
        "name": {
          "type": "string",
          "minLength": 1
        },
        "value": {
          "type": "string"
        }
      }
    },
    "ExpectedState": {
      "title": "ExpectedState",
      "type": "object",
      "description": "What must be true after a step. Every listed condition must hold.",
      "minProperties": 1,
      "additionalProperties": false,
      "properties": {
        "url_matches": {
          "type": "string",
          "description": "Regex on the URL path only (no scheme or host), e.g. ^/repo/create$"
        },
        "title_contains": {
          "type": "string"
        },
        "visible": {
          "type": "array",
          "items": {
            "$ref": "#/$defs/ElementRef"
          }
        },
        "absent": {
          "type": "array",
          "items": {
            "$ref": "#/$defs/ElementRef"
          },
          "description": "Elements that must NOT be present, e.g. an error banner."
        },
        "field_values": {
          "type": "array",
          "items": {
            "$ref": "#/$defs/FieldValue"
          }
        },
        "checked": {
          "type": "array",
          "items": {
            "$ref": "#/$defs/ElementRef"
          }
        }
      }
    },
    "VerificationMethod": {
      "title": "VerificationMethod",
      "enum": [
        "url",
        "dom",
        "aria",
        "network",
        "vision"
      ]
    },
    "BoundingBox": {
      "title": "BoundingBox",
      "type": "array",
      "description": "[x, y, width, height] in CSS pixels, page coordinates.",
      "prefixItems": [
        {
          "type": "number"
        },
        {
          "type": "number"
        },
        {
          "type": "number"
        },
        {
          "type": "number"
        }
      ],
      "items": false,
      "minItems": 4,
      "maxItems": 4
    },
    "ScrollOffset": {
      "title": "ScrollOffset",
      "type": "object",
      "description": "Window scroll position (window.scrollX / scrollY) in CSS pixels. viewport box = page bbox - scroll.",
      "required": [
        "x",
        "y"
      ],
      "additionalProperties": false,
      "properties": {
        "x": {
          "type": "number",
          "minimum": 0
        },
        "y": {
          "type": "number",
          "minimum": 0
        }
      }
    },
    "ErrorCode": {
      "title": "ErrorCode",
      "enum": [
        "validation_error",
        "not_found",
        "conflict",
        "plan_not_editable",
        "run_not_active",
        "rate_limited",
        "llm_unavailable",
        "unauthorized",
        "forbidden",
        "internal"
      ]
    },
    "ApiError": {
      "title": "ApiError",
      "type": "object",
      "required": [
        "code",
        "message"
      ],
      "additionalProperties": false,
      "properties": {
        "code": {
          "$ref": "#/$defs/ErrorCode"
        },
        "message": {
          "type": "string"
        },
        "details": {
          "type": "object"
        }
      }
    },
    "ErrorResponse": {
      "title": "ErrorResponse",
      "type": "object",
      "description": "Body of every error response (docs/api-contract.md).",
      "required": [
        "error"
      ],
      "additionalProperties": false,
      "properties": {
        "error": {
          "$ref": "#/$defs/ApiError"
        }
      }
    }
  }
} as const;

export const stepSchema = {
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "step.schema.json",
  "title": "Step",
  "$comment": "v1.4. One executed and verified step of a Verified Workflow (docs/phases/README.md §3.1, docs/database-schema.md).",
  "type": "object",
  "required": [
    "id",
    "seq",
    "action",
    "target",
    "instruction_text",
    "expected_state",
    "observed_state",
    "verification",
    "risk"
  ],
  "additionalProperties": false,
  "properties": {
    "id": {
      "type": "string",
      "format": "uuid"
    },
    "workflow_id": {
      "type": [
        "string",
        "null"
      ],
      "format": "uuid"
    },
    "seq": {
      "type": "integer",
      "minimum": 1
    },
    "action": {
      "$ref": "common.schema.json#/$defs/Action"
    },
    "target": {
      "$ref": "#/$defs/StepTarget"
    },
    "instruction_text": {
      "type": "string",
      "minLength": 1
    },
    "section": {
      "type": [
        "string",
        "null"
      ],
      "description": "Step mode (ADR 0011): the outline item this step belongs to, shown as a section title. Null for upfront workflows."
    },
    "before_state": {
      "oneOf": [
        {
          "$ref": "#/$defs/ObservedState"
        },
        {
          "type": "null"
        }
      ]
    },
    "expected_state": {
      "$ref": "common.schema.json#/$defs/ExpectedState"
    },
    "observed_state": {
      "$ref": "#/$defs/ObservedState"
    },
    "verification": {
      "$ref": "#/$defs/StepVerification"
    },
    "risk": {
      "$ref": "common.schema.json#/$defs/Risk"
    },
    "sensitive": {
      "type": "boolean",
      "default": false
    },
    "performed_by": {
      "$ref": "common.schema.json#/$defs/PerformedBy",
      "default": "krama",
      "description": "human: the run's owner did this step in a takeover; its confidence is capped and the tutorial shows it as a do-it-yourself step (ADR 0008)."
    },
    "screenshot_path": {
      "type": [
        "string",
        "null"
      ]
    },
    "timing": {
      "oneOf": [
        {
          "$ref": "#/$defs/StepTiming"
        },
        {
          "type": "null"
        }
      ]
    },
    "start_ms": {
      "type": [
        "integer",
        "null"
      ],
      "minimum": 0
    },
    "end_ms": {
      "type": [
        "integer",
        "null"
      ],
      "minimum": 0
    }
  },
  "$defs": {
    "VerificationResult": {
      "title": "VerificationResult",
      "enum": [
        "verified",
        "failed",
        "skipped"
      ]
    },
    "StepVerification": {
      "title": "StepVerification",
      "type": "object",
      "required": [
        "result",
        "method",
        "confidence"
      ],
      "additionalProperties": false,
      "properties": {
        "result": {
          "$ref": "#/$defs/VerificationResult"
        },
        "method": {
          "type": "array",
          "minItems": 1,
          "items": {
            "$ref": "common.schema.json#/$defs/VerificationMethod"
          }
        },
        "confidence": {
          "type": "number",
          "minimum": 0,
          "maximum": 1
        }
      }
    },
    "StepTarget": {
      "title": "StepTarget",
      "type": "object",
      "description": "How to locate the element, and its resolved bounding box if observed.",
      "additionalProperties": false,
      "properties": {
        "role": {
          "type": [
            "string",
            "null"
          ]
        },
        "name": {
          "type": [
            "string",
            "null"
          ]
        },
        "selector": {
          "type": [
            "string",
            "null"
          ]
        },
        "bbox": {
          "oneOf": [
            {
              "$ref": "common.schema.json#/$defs/BoundingBox"
            },
            {
              "type": "null"
            }
          ]
        },
        "scroll": {
          "description": "Window scroll when the action ran (measured after scrolling the element into view). Lets a replay place bbox without relying on rrweb's scroll events, which can land just after the click.",
          "oneOf": [
            {
              "$ref": "common.schema.json#/$defs/ScrollOffset"
            },
            {
              "type": "null"
            }
          ]
        }
      }
    },
    "StepTiming": {
      "title": "StepTiming",
      "type": "object",
      "required": [
        "start_ms",
        "end_ms"
      ],
      "additionalProperties": false,
      "properties": {
        "start_ms": {
          "type": "integer",
          "minimum": 0
        },
        "end_ms": {
          "type": "integer",
          "minimum": 0
        }
      }
    },
    "ObservedState": {
      "title": "ObservedState",
      "type": "object",
      "description": "The page state captured after executing the step.",
      "required": [
        "url"
      ],
      "additionalProperties": false,
      "properties": {
        "url": {
          "type": "string",
          "description": "URL path only, e.g. /repo/create"
        },
        "query": {
          "type": [
            "string",
            "null"
          ],
          "description": "The URL's query string without the '?', masked like other page text, e.g. query=Bengaluru. url_matches is tried on the path first, then on path?query (#463)."
        },
        "title": {
          "type": [
            "string",
            "null"
          ]
        },
        "headings": {
          "type": "array",
          "items": {
            "type": "string"
          }
        },
        "aria_excerpt": {
          "type": [
            "string",
            "null"
          ]
        },
        "screenshot": {
          "type": [
            "string",
            "null"
          ]
        },
        "screenshot_path": {
          "type": [
            "string",
            "null"
          ]
        },
        "captured_at": {
          "type": [
            "string",
            "null"
          ],
          "format": "date-time"
        }
      }
    }
  }
} as const;

export const workflowSchema = {
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "workflow.schema.json",
  "title": "Workflow",
  "$comment": "v1.6. The verified workflow, the core object of Krama (docs/phases/README.md §3.1, docs/database-schema.md).",
  "type": "object",
  "required": [
    "id",
    "title",
    "status",
    "steps"
  ],
  "additionalProperties": false,
  "properties": {
    "id": {
      "type": "string",
      "format": "uuid"
    },
    "version": {
      "type": "string",
      "default": "1.0",
      "description": "Workflow format version (e.g. 1.0)."
    },
    "revision": {
      "type": [
        "integer",
        "null"
      ],
      "minimum": 1,
      "description": "Number of the workflow version whose steps and recording this is (1 = as first recorded). Not the format `version` above."
    },
    "current_version_source": {
      "description": "How the current version was made. With status `verified`, `heal` means a self-heal updated it: the `auto-updated` badge (#114, #382). Null for workflows from before versions.",
      "oneOf": [
        {
          "$ref": "#/$defs/WorkflowVersionSource"
        },
        {
          "type": "null"
        }
      ]
    },
    "task_id": {
      "type": [
        "string",
        "null"
      ],
      "format": "uuid"
    },
    "run_id": {
      "type": [
        "string",
        "null"
      ],
      "format": "uuid"
    },
    "title": {
      "type": "string",
      "minLength": 1,
      "description": "Human-readable title describing the workflow."
    },
    "task": {
      "type": [
        "string",
        "null"
      ],
      "description": "Original task prompt or goal."
    },
    "target": {
      "oneOf": [
        {
          "$ref": "#/$defs/WorkflowTarget"
        },
        {
          "type": "null"
        }
      ]
    },
    "target_app": {
      "type": [
        "string",
        "null"
      ],
      "description": "Application name, e.g. gitea, github."
    },
    "target_url": {
      "type": [
        "string",
        "null"
      ],
      "format": "uri"
    },
    "status": {
      "$ref": "#/$defs/WorkflowStatus"
    },
    "confidence": {
      "type": [
        "number",
        "null"
      ],
      "minimum": 0,
      "maximum": 1,
      "description": "Overall verification confidence score."
    },
    "preconditions": {
      "type": [
        "object",
        "null"
      ],
      "description": "Required preconditions before running (e.g. {logged_in_as: 'demo'})."
    },
    "viewport": {
      "oneOf": [
        {
          "$ref": "#/$defs/WorkflowViewport"
        },
        {
          "type": "null"
        }
      ]
    },
    "recording": {
      "oneOf": [
        {
          "$ref": "#/$defs/WorkflowRecording"
        },
        {
          "type": "null"
        }
      ]
    },
    "recording_path": {
      "type": [
        "string",
        "null"
      ],
      "description": "Relative artifact path to rrweb recording."
    },
    "steps": {
      "type": "array",
      "items": {
        "$ref": "step.schema.json"
      },
      "description": "The ordered sequence of verified steps."
    },
    "created_at": {
      "type": [
        "string",
        "null"
      ],
      "format": "date-time"
    },
    "updated_at": {
      "type": [
        "string",
        "null"
      ],
      "format": "date-time"
    }
  },
  "$defs": {
    "WorkflowStatus": {
      "title": "WorkflowStatus",
      "enum": [
        "draft",
        "approved",
        "running",
        "verified",
        "failed",
        "outdated"
      ]
    },
    "WorkflowTarget": {
      "title": "WorkflowTarget",
      "type": "object",
      "required": [
        "app"
      ],
      "additionalProperties": false,
      "properties": {
        "app": {
          "type": "string",
          "minLength": 1
        },
        "base_url": {
          "type": [
            "string",
            "null"
          ],
          "format": "uri"
        }
      }
    },
    "WorkflowViewport": {
      "title": "WorkflowViewport",
      "type": "object",
      "required": [
        "width",
        "height"
      ],
      "additionalProperties": false,
      "properties": {
        "width": {
          "type": "integer",
          "minimum": 1
        },
        "height": {
          "type": "integer",
          "minimum": 1
        },
        "device_scale_factor": {
          "type": [
            "number",
            "null"
          ],
          "minimum": 0
        }
      }
    },
    "WorkflowRecording": {
      "title": "WorkflowRecording",
      "type": "object",
      "additionalProperties": false,
      "properties": {
        "rrweb": {
          "type": [
            "string",
            "null"
          ]
        },
        "path": {
          "type": [
            "string",
            "null"
          ]
        },
        "event_count": {
          "type": [
            "integer",
            "null"
          ],
          "minimum": 0
        },
        "started_at": {
          "type": [
            "string",
            "null"
          ],
          "format": "date-time"
        },
        "ended_at": {
          "type": [
            "string",
            "null"
          ],
          "format": "date-time"
        }
      }
    },
    "WorkflowSummary": {
      "title": "WorkflowSummary",
      "type": "object",
      "required": [
        "id",
        "title",
        "status",
        "step_count"
      ],
      "additionalProperties": false,
      "properties": {
        "id": {
          "type": "string",
          "format": "uuid"
        },
        "title": {
          "type": "string",
          "minLength": 1
        },
        "status": {
          "$ref": "#/$defs/WorkflowStatus"
        },
        "current_version_source": {
          "description": "How the current version was made. With status `verified`, `heal` means a self-heal updated it: the `auto-updated` badge (#114, #382). Null for workflows from before versions.",
          "oneOf": [
            {
              "$ref": "#/$defs/WorkflowVersionSource"
            },
            {
              "type": "null"
            }
          ]
        },
        "target_app": {
          "type": [
            "string",
            "null"
          ]
        },
        "step_count": {
          "type": "integer",
          "minimum": 0
        },
        "confidence": {
          "type": [
            "number",
            "null"
          ],
          "minimum": 0,
          "maximum": 1
        },
        "created_at": {
          "type": [
            "string",
            "null"
          ],
          "format": "date-time"
        },
        "last_validated_at": {
          "type": [
            "string",
            "null"
          ],
          "format": "date-time",
          "description": "When validation last checked it (#135); null if never."
        },
        "score": {
          "type": [
            "number",
            "null"
          ],
          "minimum": 0,
          "description": "Only with GET /workflows?q=: relevance x status x freshness (higher first, #135 S5)."
        },
        "match": {
          "description": "Only with GET /workflows?q=: where the words matched best.",
          "oneOf": [
            {
              "$ref": "#/$defs/WorkflowMatch"
            },
            {
              "type": "null"
            }
          ]
        }
      }
    },
    "TranslationStatus": {
      "title": "TranslationStatus",
      "enum": [
        "translating",
        "ready",
        "failed"
      ]
    },
    "TranslatedStep": {
      "title": "TranslatedStep",
      "type": "object",
      "required": [
        "step_seq",
        "text"
      ],
      "additionalProperties": false,
      "properties": {
        "step_seq": {
          "type": "integer",
          "minimum": 1
        },
        "text": {
          "type": "string",
          "description": "The step text in the language. Quoted UI labels are byte for byte the site's own."
        },
        "translated": {
          "type": "boolean",
          "default": true,
          "description": "False when this step kept its English text (its translation failed the label check)."
        }
      }
    },
    "Translation": {
      "title": "Translation",
      "type": "object",
      "description": "GET /workflows/{id}/translations/{language}: the current version's title and step texts in a language (#132, L4-L6). Made once, on first request, then cached.",
      "required": [
        "workflow_id",
        "revision",
        "language",
        "status",
        "steps"
      ],
      "additionalProperties": false,
      "properties": {
        "workflow_id": {
          "type": "string",
          "format": "uuid"
        },
        "revision": {
          "type": "integer",
          "minimum": 1
        },
        "language": {
          "$ref": "common.schema.json#/$defs/Language"
        },
        "status": {
          "$ref": "#/$defs/TranslationStatus"
        },
        "title": {
          "type": [
            "string",
            "null"
          ]
        },
        "steps": {
          "type": "array",
          "items": {
            "$ref": "#/$defs/TranslatedStep"
          }
        },
        "error": {
          "type": [
            "string",
            "null"
          ],
          "description": "Why it failed (status failed); ask again to retry."
        }
      }
    },
    "WorkflowMatch": {
      "title": "WorkflowMatch",
      "type": "object",
      "required": [
        "snippet"
      ],
      "additionalProperties": false,
      "properties": {
        "step_seq": {
          "type": [
            "integer",
            "null"
          ],
          "minimum": 1,
          "description": "The step whose text matched best; null when the title or request matched."
        },
        "snippet": {
          "type": "string",
          "description": "Plain text with the matched words wrapped in <mark></mark>. Show it as text plus marks, never as HTML."
        }
      }
    },
    "WorkflowPage": {
      "title": "WorkflowPage",
      "type": "object",
      "required": [
        "items"
      ],
      "additionalProperties": false,
      "properties": {
        "items": {
          "type": "array",
          "items": {
            "$ref": "#/$defs/WorkflowSummary"
          }
        },
        "next_cursor": {
          "type": [
            "string",
            "null"
          ]
        }
      }
    },
    "WorkflowInput": {
      "title": "WorkflowInput",
      "type": "object",
      "description": "A value the user chooses when Krama runs the workflow for them (#129, P3): one non-sensitive single-line value the recorded run typed. The recorded value is only an example; the user's value replaces it in every step where it reappears.",
      "required": [
        "key",
        "label",
        "example",
        "kind",
        "min_length",
        "steps"
      ],
      "additionalProperties": false,
      "properties": {
        "key": {
          "type": "string",
          "pattern": "^[a-z][a-z0-9_]*$",
          "description": "Stable name of the input in RunWorkflowRequest.inputs (e.g. repository_name)."
        },
        "label": {
          "type": "string",
          "minLength": 1,
          "description": "What to ask for, from the field's label (e.g. \"Repository name\")."
        },
        "example": {
          "type": "string",
          "minLength": 1,
          "description": "The value the recorded run typed, shown as a placeholder, never as the default."
        },
        "kind": {
          "enum": [
            "text"
          ],
          "description": "text only in v1; dropdowns replay the recorded option (P15)."
        },
        "pattern": {
          "type": [
            "string",
            "null"
          ],
          "description": "A regular expression a value must match: the example's character class (P5), e.g. ^[A-Za-z0-9._-]+$. Null when any single-line text is accepted."
        },
        "min_length": {
          "type": "integer",
          "minimum": 1,
          "description": "Shortest value accepted (3 in v1, P5)."
        },
        "steps": {
          "type": "array",
          "minItems": 1,
          "items": {
            "title": "StepSeq",
            "type": "integer",
            "minimum": 1
          },
          "description": "Seq of every step the value is typed in or reappears in (URL checks, headings, later targets, step text)."
        }
      }
    },
    "WorkflowInputList": {
      "title": "WorkflowInputList",
      "type": "object",
      "description": "GET /workflows/{id}/inputs: what the owner fills in before \"Do it for me\" runs the current version.",
      "required": [
        "workflow_id",
        "revision",
        "inputs"
      ],
      "additionalProperties": false,
      "properties": {
        "workflow_id": {
          "type": "string",
          "format": "uuid"
        },
        "revision": {
          "type": "integer",
          "minimum": 1,
          "description": "The version the inputs belong to; send it back in RunWorkflowRequest."
        },
        "inputs": {
          "type": "array",
          "items": {
            "$ref": "#/$defs/WorkflowInput"
          }
        },
        "account": {
          "type": [
            "string",
            "null"
          ],
          "description": "The site account the run will act in: the user's own (ADR 0007). Null when unknown or not signed in yet."
        },
        "sign_in_site": {
          "type": [
            "string",
            "null"
          ],
          "description": "The site the user must sign in to first (POST /sites/{site}/sign-in), else null."
        }
      }
    },
    "RunWorkflowRequest": {
      "title": "RunWorkflowRequest",
      "type": "object",
      "description": "POST /workflows/{id}/run: run the workflow's current version for its owner with these values (\"Do it for me\", #129). Starting it approves the steps; risky steps still pause for confirmation.",
      "required": [
        "revision",
        "inputs"
      ],
      "additionalProperties": false,
      "properties": {
        "revision": {
          "type": "integer",
          "minimum": 1,
          "description": "The version the user previewed (from WorkflowInputList); a newer current version gives 409 stale_revision."
        },
        "inputs": {
          "type": "object",
          "description": "One value per WorkflowInput.key; every input is required (the server checks min_length and pattern).",
          "additionalProperties": {
            "type": "string"
          }
        }
      }
    },
    "WorkflowVersionSource": {
      "title": "WorkflowVersionSource",
      "description": "What made the version: the first verified run, a self-heal, a regenerated plan, or a human edit.",
      "enum": [
        "initial",
        "heal",
        "regenerate",
        "edit"
      ]
    },
    "WorkflowVersionStatus": {
      "title": "WorkflowVersionStatus",
      "description": "current: the one shown. pending_review: waits for the owner to accept it. superseded: an older current one. rejected: the owner turned it down.",
      "enum": [
        "current",
        "pending_review",
        "superseded",
        "rejected"
      ]
    },
    "WorkflowVersion": {
      "title": "WorkflowVersion",
      "type": "object",
      "required": [
        "id",
        "workflow_id",
        "revision",
        "source",
        "status",
        "step_count",
        "created_at"
      ],
      "additionalProperties": false,
      "properties": {
        "recorded_as": {
          "type": [
            "string",
            "null"
          ],
          "description": "The site account the version was recorded in (ADR 0007). Do it for me swaps it for the user's own account. Null for versions from before 1.18 (they were recorded in the shared test account)."
        },
        "id": {
          "type": "string",
          "format": "uuid"
        },
        "workflow_id": {
          "type": "string",
          "format": "uuid"
        },
        "revision": {
          "type": "integer",
          "minimum": 1
        },
        "source": {
          "$ref": "#/$defs/WorkflowVersionSource"
        },
        "status": {
          "$ref": "#/$defs/WorkflowVersionStatus"
        },
        "parent_version_id": {
          "type": [
            "string",
            "null"
          ],
          "format": "uuid",
          "description": "The version this one was made from; null for the first."
        },
        "run_id": {
          "type": [
            "string",
            "null"
          ],
          "format": "uuid",
          "description": "The run that recorded this version."
        },
        "confidence": {
          "type": [
            "number",
            "null"
          ],
          "minimum": 0,
          "maximum": 1
        },
        "step_count": {
          "type": "integer",
          "minimum": 0
        },
        "change_summary": {
          "oneOf": [
            {
              "$ref": "#/$defs/StepDiff"
            },
            {
              "type": "null"
            }
          ],
          "description": "How the steps differ from the parent version; null for the first."
        },
        "created_at": {
          "type": "string",
          "format": "date-time"
        }
      }
    },
    "WorkflowVersionList": {
      "title": "WorkflowVersionList",
      "type": "object",
      "required": [
        "items"
      ],
      "additionalProperties": false,
      "properties": {
        "items": {
          "type": "array",
          "items": {
            "$ref": "#/$defs/WorkflowVersion"
          },
          "description": "Newest first."
        }
      }
    },
    "StepDiff": {
      "title": "StepDiff",
      "type": "object",
      "required": [
        "from_revision",
        "to_revision",
        "steps"
      ],
      "additionalProperties": false,
      "properties": {
        "from_revision": {
          "type": "integer",
          "minimum": 1
        },
        "to_revision": {
          "type": "integer",
          "minimum": 1
        },
        "steps": {
          "type": "array",
          "items": {
            "$ref": "#/$defs/StepChange"
          },
          "description": "Every step of both versions, aligned by meaning, in the new version's order."
        }
      }
    },
    "StepChangeKind": {
      "title": "StepChangeKind",
      "enum": [
        "same",
        "changed",
        "added",
        "removed"
      ]
    },
    "StepChangeCategory": {
      "title": "StepChangeCategory",
      "description": "behaviour: what the step does or acts on. check: its expected state. wording: only its instruction text (the UI may collapse these). risk: its risk level.",
      "enum": [
        "behaviour",
        "check",
        "wording",
        "risk"
      ]
    },
    "StepChange": {
      "title": "StepChange",
      "type": "object",
      "required": [
        "kind"
      ],
      "additionalProperties": false,
      "properties": {
        "kind": {
          "$ref": "#/$defs/StepChangeKind"
        },
        "old_seq": {
          "type": [
            "integer",
            "null"
          ],
          "minimum": 1,
          "description": "Null for an added step."
        },
        "new_seq": {
          "type": [
            "integer",
            "null"
          ],
          "minimum": 1,
          "description": "Null for a removed step."
        },
        "category": {
          "oneOf": [
            {
              "$ref": "#/$defs/StepChangeCategory"
            },
            {
              "type": "null"
            }
          ],
          "description": "The most important category among the changes; null for a same step."
        },
        "fields": {
          "type": "array",
          "items": {
            "$ref": "#/$defs/FieldChange"
          },
          "default": []
        },
        "summary": {
          "type": [
            "string",
            "null"
          ],
          "description": "Short text for an added or removed step, e.g. 'click button “Confirm”'."
        }
      }
    },
    "FieldChange": {
      "title": "FieldChange",
      "type": "object",
      "required": [
        "field"
      ],
      "additionalProperties": false,
      "properties": {
        "field": {
          "type": "string",
          "minLength": 1,
          "description": "Dotted path in the step, e.g. target.name, action.value, expected_state."
        },
        "from": {
          "description": "The old value (any JSON); absent or null if there was none."
        },
        "to": {
          "description": "The new value (any JSON); absent or null if there is none."
        }
      }
    },
    "ValidationStatus": {
      "title": "ValidationStatus",
      "description": "Result of one validation of a stored workflow (docs/research/phase-4-decisions-alignment.md): passed, healed (a new current version), heal_pending (a new version waits for review), outdated, blocked (the environment stopped it; the workflow's status is unchanged), skipped (not replayable).",
      "enum": [
        "passed",
        "healed",
        "heal_pending",
        "outdated",
        "blocked",
        "skipped"
      ]
    }
  }
} as const;

export const tutorialSpecSchema = {
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "tutorial-spec.schema.json",
  "title": "TutorialSpec",
  "$comment": "v1.1. Output of packages/tutorial-compiler (Workflow -> TutorialSpec), consumed by the player (Phase 2) and the Remotion export (Phase 5). Design: docs/research/phase-2-together-tutorial-spec-design.md.",
  "description": "An interactive tutorial compiled from one Verified Workflow. Times are integer milliseconds; geometry is CSS pixels in page coordinates. Frames are derived only at video export: frame = round(ms / 1000 * fps).",
  "type": "object",
  "required": [
    "version",
    "workflow_id",
    "title",
    "viewport",
    "total_duration_ms",
    "scenes"
  ],
  "additionalProperties": false,
  "properties": {
    "version": {
      "type": "string",
      "const": "1.0",
      "description": "Spec format version."
    },
    "workflow_id": {
      "type": "string",
      "format": "uuid"
    },
    "title": {
      "type": "string",
      "minLength": 1
    },
    "description": {
      "type": [
        "string",
        "null"
      ]
    },
    "language": {
      "$ref": "common.schema.json#/$defs/Language",
      "default": "en",
      "description": "The language of the captions and titles (#132). UI labels inside them stay in the site's own language."
    },
    "viewport": {
      "$ref": "workflow.schema.json#/$defs/WorkflowViewport",
      "description": "The recording's viewport: the coordinate space of every bbox and point."
    },
    "fps": {
      "type": "integer",
      "minimum": 1,
      "maximum": 120,
      "default": 30,
      "description": "Frame rate for the video export only. The player ignores it."
    },
    "total_duration_ms": {
      "type": "integer",
      "minimum": 0,
      "description": "End of the last scene (start_ms + duration_ms)."
    },
    "scenes": {
      "type": "array",
      "minItems": 1,
      "items": {
        "$ref": "#/$defs/Scene"
      },
      "description": "One scene per workflow step, in step order."
    }
  },
  "$defs": {
    "Scene": {
      "title": "Scene",
      "type": "object",
      "description": "One workflow step. start_ms is on the tutorial timeline; every other time inside a scene (cursor, caption words) is relative to the scene's start.",
      "required": [
        "id",
        "step_seq",
        "start_ms",
        "duration_ms",
        "action",
        "caption",
        "recording"
      ],
      "additionalProperties": false,
      "properties": {
        "id": {
          "type": "string",
          "minLength": 1
        },
        "step_seq": {
          "type": "integer",
          "minimum": 1,
          "description": "seq of the workflow step this scene shows."
        },
        "title": {
          "type": [
            "string",
            "null"
          ],
          "description": "Short label for the step list."
        },
        "section": {
          "type": [
            "string",
            "null"
          ],
          "description": "The workflow step's section (an outline item); the step list shows it when it changes."
        },
        "start_ms": {
          "type": "integer",
          "minimum": 0,
          "description": "Scene start on the tutorial timeline."
        },
        "duration_ms": {
          "type": "integer",
          "minimum": 0
        },
        "action": {
          "$ref": "common.schema.json#/$defs/Action",
          "description": "What the step does. value is copied from the workflow and is already masked if the step is sensitive."
        },
        "sensitive": {
          "type": "boolean",
          "default": false,
          "description": "The step typed a secret: show no typed text, only that something was entered."
        },
        "caption": {
          "$ref": "#/$defs/Caption"
        },
        "recording": {
          "$ref": "#/$defs/RecordingSlice"
        },
        "scroll": {
          "description": "Window scroll during the action, from the step. The highlight's viewport box is highlight.bbox - scroll.",
          "oneOf": [
            {
              "$ref": "common.schema.json#/$defs/ScrollOffset"
            },
            {
              "type": "null"
            }
          ]
        },
        "camera": {
          "description": "Zoom and pan. Null: show the whole viewport.",
          "oneOf": [
            {
              "$ref": "#/$defs/Camera"
            },
            {
              "type": "null"
            }
          ]
        },
        "cursor": {
          "description": "Null for steps without an element (navigate, a key press without target, wait).",
          "oneOf": [
            {
              "$ref": "#/$defs/Cursor"
            },
            {
              "type": "null"
            }
          ]
        },
        "highlight": {
          "description": "Null for steps without an element.",
          "oneOf": [
            {
              "$ref": "#/$defs/Highlight"
            },
            {
              "type": "null"
            }
          ]
        }
      }
    },
    "Caption": {
      "title": "Caption",
      "type": "object",
      "required": [
        "text"
      ],
      "additionalProperties": false,
      "properties": {
        "text": {
          "type": "string",
          "minLength": 1,
          "description": "The step's instruction text, shown and narrated."
        },
        "words": {
          "description": "Word timings relative to the scene start, when known at compile time (Piper, Phase 5). Null when they only exist at playback (Web Speech boundary events).",
          "oneOf": [
            {
              "type": "array",
              "items": {
                "$ref": "#/$defs/WordTiming"
              }
            },
            {
              "type": "null"
            }
          ]
        }
      }
    },
    "WordTiming": {
      "title": "WordTiming",
      "type": "object",
      "required": [
        "word",
        "start_ms",
        "end_ms"
      ],
      "additionalProperties": false,
      "properties": {
        "word": {
          "type": "string",
          "minLength": 1
        },
        "start_ms": {
          "type": "integer",
          "minimum": 0
        },
        "end_ms": {
          "type": "integer",
          "minimum": 0
        }
      }
    },
    "RecordingSlice": {
      "title": "RecordingSlice",
      "type": "object",
      "description": "The part of the workflow's rrweb recording this scene replays.",
      "required": [
        "start_ms",
        "end_ms"
      ],
      "additionalProperties": false,
      "properties": {
        "start_ms": {
          "type": "integer",
          "minimum": 0,
          "description": "Milliseconds since the recording's first event."
        },
        "end_ms": {
          "type": "integer",
          "minimum": 0,
          "description": "Milliseconds since the recording's first event."
        },
        "baseline_snapshot_index": {
          "type": [
            "integer",
            "null"
          ],
          "minimum": 0,
          "description": "Index (in the recording's event list) of the FullSnapshot to start from, so the slice renders on its own."
        }
      }
    },
    "Point": {
      "title": "Point",
      "type": "object",
      "description": "A point in CSS pixels, page coordinates.",
      "required": [
        "x",
        "y"
      ],
      "additionalProperties": false,
      "properties": {
        "x": {
          "type": "number"
        },
        "y": {
          "type": "number"
        }
      }
    },
    "Camera": {
      "title": "Camera",
      "type": "object",
      "required": [
        "scale",
        "center"
      ],
      "additionalProperties": false,
      "properties": {
        "scale": {
          "type": "number",
          "minimum": 1,
          "maximum": 3
        },
        "center": {
          "$ref": "#/$defs/Point"
        },
        "easing": {
          "type": "string",
          "default": "cubic-bezier(0.22, 1, 0.36, 1)",
          "description": "CSS easing function for the pan/zoom."
        },
        "pan_duration_ms": {
          "type": "integer",
          "minimum": 0,
          "default": 450
        }
      }
    },
    "ClickType": {
      "title": "ClickType",
      "enum": [
        "single",
        "double",
        "none"
      ]
    },
    "Cursor": {
      "title": "Cursor",
      "type": "object",
      "description": "A cubic Bezier glide from path[0] to path[3]; times relative to the scene start.",
      "required": [
        "path",
        "start_ms",
        "end_ms",
        "click_type"
      ],
      "additionalProperties": false,
      "properties": {
        "path": {
          "type": "array",
          "items": {
            "$ref": "#/$defs/Point"
          },
          "minItems": 4,
          "maxItems": 4,
          "description": "Bezier control points P0..P3."
        },
        "start_ms": {
          "type": "integer",
          "minimum": 0
        },
        "end_ms": {
          "type": "integer",
          "minimum": 0
        },
        "click_ms": {
          "type": [
            "integer",
            "null"
          ],
          "minimum": 0
        },
        "click_type": {
          "$ref": "#/$defs/ClickType"
        },
        "ripple": {
          "oneOf": [
            {
              "$ref": "#/$defs/Ripple"
            },
            {
              "type": "null"
            }
          ],
          "description": "Click ripple. Null: no ripple."
        }
      }
    },
    "Ripple": {
      "title": "Ripple",
      "type": "object",
      "additionalProperties": false,
      "properties": {
        "radius": {
          "type": "number",
          "minimum": 0,
          "default": 24
        },
        "color": {
          "type": "string",
          "default": "rgba(99, 102, 241, 0.4)"
        }
      }
    },
    "HighlightStyle": {
      "title": "HighlightStyle",
      "enum": [
        "pulsing_ring",
        "solid_box",
        "spotlight"
      ]
    },
    "Highlight": {
      "title": "Highlight",
      "type": "object",
      "required": [
        "bbox",
        "style"
      ],
      "additionalProperties": false,
      "properties": {
        "bbox": {
          "$ref": "common.schema.json#/$defs/BoundingBox"
        },
        "style": {
          "$ref": "#/$defs/HighlightStyle"
        },
        "padding": {
          "type": "number",
          "minimum": 0,
          "default": 8
        },
        "color": {
          "type": "string",
          "default": "#4f46e5"
        }
      }
    }
  }
} as const;
