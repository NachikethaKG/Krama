# Benchmark Task Specification

This directory contains standardized, single-file YAML benchmark task definitions for Krama agent evaluation. Each task defines an end-to-end user goal, the target environment, pre-run setup hooks, and deterministic external success verification.

## Schema Overview

Every benchmark task is defined in a `.yaml` file adhering to the following structure:

```yaml
name: <task-identifier>
prompt: "<natural language instructions given to the agent>"
target: "<base URL or target site endpoint>"
setup:
  command: "<optional shell/curl command executed prior to run>"
  api_call:
    method: "<HTTP method>"
    url: "<endpoint URL>"
    body: <optional request payload>
success_check:
  type: "<api | command | dom>"
  assertion:
    method: "<HTTP method, if api>"
    url: "<endpoint URL, if api>"
    expected_status: <HTTP status code, if api>
```

---

## Field Reference

### Core Fields

| Field | Type | Required | Description |
|---|---|---|---|
| `name` | string | Yes | Unique hyphen-separated task identifier (e.g., `gitea-create-repo`). |
| `prompt` | string | Yes | The exact plaintext instruction supplied to the agent. Must clearly state what to create, configure, or find. |
| `target` | string | Yes | Target application base URL or entrypoint (e.g., `http://localhost:3000` or `http://localhost:3001`). |
| `setup` | object | No | Pre-run reset hooks executed prior to each trial to ensure pristine initial state. |
| `success_check` | object | Yes | External deterministic validation mechanism checking functional state after agent completion. |

### `setup` Configuration

The `setup` block ensures repeatable benchmarks by resetting the environment before each trial:

- `command` *(string, optional)*: Shell command executed to wipe existing state (e.g., `curl -s -X DELETE http://localhost:3000/api/v1/repos/krama-user/test-repo || true`).
- `api_call` *(object, optional)*: Structured API invocation parameters (`method`, `url`, `headers`, `body`) for programmatic resets.

### `success_check` Configuration

The agent never grades itself. The benchmark harness executes an independent external check to verify functional correctness:

- `type` *(string, required)*: Type of check. Supported types:
  - `api`: Makes an HTTP request and verifies status code and/or response payload.
  - `command`: Runs an external CLI verification command and asserts zero exit code.
  - `dom`: Runs an automated browser/DOM assertion against final page state.
- `assertion` *(object or string, required)*:
  - For `type: api`:
    - `method` *(string)*: HTTP method (`GET`, `POST`, `HEAD`).
    - `url` *(string)*: Verification endpoint.
    - `expected_status` *(integer)*: Expected HTTP response status code (e.g., `200`).
  - For `type: command`: String command expecting zero return code or matching output.
  - For `type: dom`: Dict containing selector and expected element attributes or text.

---

## Canonical Example: `gitea-create-repo.yaml`

```yaml
name: gitea-create-repo
prompt: "Create a new public repository named 'test-repo' with a README in local Gitea."
target: "http://localhost:3000"
setup:
  command: "curl -s -X DELETE http://localhost:3000/api/v1/repos/krama-user/test-repo || true"
success_check:
  type: api
  assertion:
    method: GET
    url: "http://localhost:3000/api/v1/repos/krama-user/test-repo"
    expected_status: 200
```

---

## Authoring Guidelines

1. **Independent Evaluation:** Success checks must rely on ground-truth state (database, REST API, or final DOM inspection), never internal agent thoughts or self-reports.
2. **Deterministic Cleanup:** Always define pre-run cleanup in `setup` (or rely on the harness reset hook) so trials can run $N$ times consecutively without collision.
3. **No Secrets:** Never embed real passwords, tokens, or private credentials in task files. Throwaway local development credentials should match `.env.example`.
4. **Validation:** All task files in this folder are automatically validated by the benchmark test suite (`pytest benchmarks/tests/test_tasks.py`).
