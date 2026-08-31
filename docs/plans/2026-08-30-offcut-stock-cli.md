# Offcut Stock CLI Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add safe, independently callable offcut stock operations to the AlphaCAM core, Application facade, gateway and Typer CLI, with stable-ID targeting, fail-closed deletion, verified COM creation, and read-only machine-status checks.

**Architecture:** Extend the existing `core/stock.py` stock blocks rather than adding an end-to-end workflow. Every operation remains atomic and returns a serializable result; `Application`, gateway server/client/remote, and CLI each expose only their own thin block. Offcut creation is allowed only after a real COM `ISheetPaths` object has been obtained and validated; otherwise the operation returns an explicit unsupported/error result and must not call `NewOffcut` or `SaveOffcutToDatabase`.

**Tech Stack:** Python 3.11+, pywin32 COM/AlphaCAM Nesting typelib, pytest, Typer, Rich, JSON-RPC gateway, mypy, ruff, LXC123 and the Monika laptop gateway at `100.71.109.69:8721`.

---

## Scope and Guardrails

- Preserve the existing untracked `C:\ALPHACAM\LICOMDAT\sheet_database_v2.db`; do not add, modify, stage, or commit it.
- Use `gencache.EnsureModule("{6702E3DF-142C-4627-8EA2-4C47EBC78441}", 0, 1, 3)` before accessing `App.Nesting` or `SheetDatabase`.
- Use `FindSheetByDatabaseID(id)` for stable-ID lookup. Name lookup may be retained only as a display/filter operation and must not be the deletion identity.
- Deletion is permitted only after reading `sheet.IsOffcut is True`; a found whole sheet, unknown type, ambiguous target, failed type read, or stale target must fail closed without calling `Delete()`.
- `IDatabaseThickness.NewOffcut(SheetPaths)` requires a genuine COM `ISheetPaths` collection. Do not pass a Python list, `IPaths`, wrapper object, fake object, or guessed conversion.
- `INesting.SaveOffcutToDatabase(i_sheet, i_drw)` is called only with the newly created offcut and the real COM drawing used to obtain its paths. If a valid drawing/path source cannot be supplied, return an explicit error and perform no partial write.
- Do not add nesting, NC generation, machine movement, milling, or any other end-to-end orchestration to this feature.
- SimCNC support is a separate read-only status block: query/report state only; no NC upload, execution, spindle, axis, tool, or feed command.
- Any live-machine test must use a disposable uniquely named fixture and clean it up by stable ID in `finally`; never use the production database file as a repository fixture.

## COM Facts to Confirm During Implementation

The local generated typelib at `docs/alphacam-ecosystem/alphacam-provided-examples/API/Python/PyCharm Examples/NestingFromCSV/Alphacam_Nesting.py` documents:

- `IDatabaseThickness.NewOffcut(SheetPaths)` returns an unsaved `IDatabaseSheet` and expects a `SheetPaths` COM collection.
- `INesting.SaveOffcutToDatabase(i_sheet, i_drw)` accepts the offcut and drawing and returns a string.
- `INesting.FindSheetByDatabaseID(Id)` is the stable-ID lookup.
- `IDatabaseSheet.IsOffcut` is read-only and `IDatabaseSheet.Delete()` deletes the sheet and zones.
- `IDatabaseSheet.InsertInActiveDrawingAtPoint()` returns `IPaths`, which is not automatically proof that the value is the required `ISheetPaths`; the implementation must establish the exact source/type on the Windows probe before exposing creation.

If the Windows probe cannot produce a valid `ISheetPaths` accepted by `NewOffcut`, the final implementation must keep offcut creation explicitly unavailable rather than simulate it with `NewSheet`, `WholeSheets.Add`, or a Python-side shape.

## TDD Task Sequence

### Task 1: Define stable-ID result and safety contracts

**Files:**

- Modify: `src/alphacam_cli/core/stock.py`
- Test: `tests/unit/test_stock.py`

**Step 1: Write the failing tests**

Add tests for a lookup helper or public operation contract that verify:

- `FindSheetByDatabaseID(123)` is called with an integer stable ID.
- The returned result includes `sheet_id`, `name`, `material`, `is_offcut`, dimensions/quantity where available, and a deterministic status.
- `None` from `FindSheetByDatabaseID` returns `success=False` with a not-found error.
- COM failure while looking up or reading `Id`/`IsOffcut` is returned as an explicit error and never treated as an offcut.
- Duplicate names do not affect stable-ID lookup; two sheets with the same mocked name remain distinguishable by ID.

**Step 2: Run tests to verify they fail**

Run:

```bash
python -m pytest tests/unit/test_stock.py -k 'stable_id or lookup' -v
```

Expected: FAIL because the stable-ID operation/helper and result contract do not yet exist.

**Step 3: Implement the minimal core contract**

Add the smallest typed helper/public block needed to call `SheetDatabase.FindSheetByDatabaseID`, read the stable ID and type, and serialize success/not-found/COM-error results. Keep name-based functions unchanged until their callers are migrated in later tasks.

**Step 4: Run tests to verify they pass**

Run:

```bash
python -m pytest tests/unit/test_stock.py -k 'stable_id or lookup' -v
```

Expected: all selected tests PASS.

### Verification

After implementation:

1. **Format & Lint** — `ruff format --check src/alphacam_cli/core/stock.py tests/unit/test_stock.py && ruff check src/alphacam_cli/core/stock.py tests/unit/test_stock.py`
2. **Type check** — `mypy src/alphacam_cli/core/stock.py`
3. **Regression** — `python -m pytest tests/unit/test_stock.py -v`
4. **Safety** — assert no `Delete()` call occurs in lookup/read tests and no result converts COM errors into success.
5. **Kaizen** — remove duplicate lookup loops only if this task’s tests prove the helper can replace them without changing unrelated stock behavior.

### Task 2: Make deletion fail closed and ID-only

**Files:**

- Modify: `src/alphacam_cli/core/stock.py`
- Modify: `tests/unit/test_stock.py`

**Step 1: Write the failing tests**

Cover:

- offcut stable ID is deleted exactly once;
- whole-sheet stable ID returns `success=False`, `status="wrong_type"` (or the repository’s final equivalent), and does not call `Delete()`;
- not-found ID does not call `Delete()`;
- duplicate names cannot delete a different sheet;
- a false/unknown/COM-error `IsOffcut` read fails closed and does not call `Delete()`;
- successful deletion includes the stable ID and a postcondition suitable for readback.

Update the old name-based deletion tests so they no longer authorize deletion by name. If a compatibility command is retained temporarily, it must first resolve one stable ID, reject ambiguity, then pass through the same offcut-only guard.

**Step 2: Run tests to verify they fail**

Run:

```bash
python -m pytest tests/unit/test_stock.py -k 'delete or wrong_type or duplicate' -v
```

Expected: FAIL because the current implementation searches both collections by name and deletes whole sheets.

**Step 3: Implement the minimal fail-closed delete**

Change the core block to accept a stable database ID, use `FindSheetByDatabaseID`, read `IsOffcut` before any mutation, reject every non-`True` value, call `Delete()` only for an offcut, and return a structured result. Do not infer type from the collection in which a mock or COM object was found.

**Step 4: Run tests to verify they pass**

Run:

```bash
python -m pytest tests/unit/test_stock.py -k 'delete or wrong_type or duplicate' -v
```

Expected: all selected tests PASS, including the assertion that whole sheets are untouched.

### Verification

After implementation:

1. **Format & Lint** — `ruff format --check src/alphacam_cli/core/stock.py tests/unit/test_stock.py && ruff check src/alphacam_cli/core/stock.py tests/unit/test_stock.py`
2. **Type check** — `mypy src/alphacam_cli/core/stock.py`
3. **Regression** — `python -m pytest tests/unit/test_stock.py -v`
4. **Error handling** — test not-found, wrong type, duplicate-name, `IsOffcut` COM error, `Delete` COM error, and readback error separately.
5. **Kaizen** — keep one guarded deletion path; do not duplicate safety checks in name and ID branches.

### Task 3: Establish the real `ISheetPaths` creation probe

**Files:**

- Create: `C:/temp/probe_offcut_paths.py` (Windows-only probe, not a production API)
- Modify: `docs/alphacam-ecosystem/alphacam-provided-examples/API/Python/PyCharm Examples/NestingFromCSV/Alphacam_Nesting.py` only if a regenerated/local typelib reference is needed
- Test: `tests/contract/test_offcut_com_probe.py`

**Step 1: Write the failing contract test**

Define a Windows-marked contract test that records the exact COM source used for `SheetPaths`, the result of `NewOffcut`, and whether `SaveOffcutToDatabase` accepts the object. It must fail when the source is a Python list, an `IPaths` wrapper without proof of the required interface, or a fake object.

**Step 2: Run the probe/test to verify the contract is unresolved**

Run locally on Linux:

```bash
python -m pytest tests/contract/test_offcut_com_probe.py -v
```

Expected: SKIP with a clear Windows/AlphaCAM prerequisite message, not a false PASS.

Run on the Windows laptop only after explicit approval:

```powershell
python C:\temp\probe_offcut_paths.py
```

Expected: a recorded COM type/interface identity and an explicit accepted/rejected result for `NewOffcut(SheetPaths)`.

**Step 3: Implement or explicitly disable the source**

If the probe proves a real `ISheetPaths` source, document its exact acquisition sequence, including active drawing ownership and `raw_dispatch` handling. If it does not, define a typed unsupported result and a guard that prevents any call to `NewOffcut`/`SaveOffcutToDatabase`.

**Step 4: Re-run the contract test**

Run the Windows contract test through the laptop gateway test harness described in Task 10. Expected: PASS only for the proven COM source, otherwise PASS as an explicit unsupported capability with zero write calls.

### Verification

After implementation:

1. **Format & Lint** — `ruff format --check tests/contract/test_offcut_com_probe.py && ruff check tests/contract/test_offcut_com_probe.py`
2. **Type check** — `mypy tests/contract/test_offcut_com_probe.py`
3. **Contract evidence** — retain the probe output in the test report, including COM class/interface and whether the call was accepted.
4. **Safety** — no fallback to `NewSheet`, `WholeSheets.Add`, direct SQLite writes, or guessed wrapper conversion.
5. **Kaizen** — keep the probe disposable and separate from runtime code; do not ship machine-specific probing logic in core.

### Task 4: Implement atomic core offcut creation with readback and cleanup

**Files:**

- Modify: `src/alphacam_cli/core/stock.py`
- Test: `tests/unit/test_stock.py`

**Step 1: Write the failing unit tests**

Test the proven creation contract using strict mocks:

- valid material/thickness and real-path provider call `NewOffcut(sheet_paths)`;
- duplicate requested name is rejected before COM mutation;
- missing material or thickness is rejected;
- invalid dimensions/quantity/name are rejected at the boundary;
- no valid `ISheetPaths` source returns a clear unsupported/error result and neither COM save method is called;
- `NewOffcut` COM error and `SaveOffcutToDatabase` COM error are surfaced with operation context;
- successful creation performs readback by stable ID/name and verifies `IsOffcut=True`, dimensions/name/material, then returns the saved identifier;
- partial failure invokes cleanup for an unsaved/saved temporary object only when the COM contract permits it, and never deletes an existing whole sheet.

**Step 2: Run tests to verify they fail**

```bash
python -m pytest tests/unit/test_stock.py -k 'offcut_create or offcut_name or readback or cleanup' -v
```

Expected: FAIL because no safe creation block exists.

**Step 3: Implement the minimal core block**

Add one atomic `stock_offcut_create` block. Resolve material/thickness, validate duplicate name, acquire the verified real `ISheetPaths`, call `NewOffcut`, set only supported fields, call `SaveOffcutToDatabase(i_sheet, i_drw)`, read back by stable ID, and return a structured result. On any precondition failure, do not mutate. On COM failure, report the phase and attempt only documented cleanup.

**Step 4: Run tests to verify they pass**

```bash
python -m pytest tests/unit/test_stock.py -k 'offcut_create or offcut_name or readback or cleanup' -v
```

Expected: all selected tests PASS.

### Verification

After implementation:

1. **Format & Lint** — `ruff format --check src/alphacam_cli/core/stock.py tests/unit/test_stock.py && ruff check src/alphacam_cli/core/stock.py tests/unit/test_stock.py`
2. **Type check** — `mypy src/alphacam_cli/core/stock.py`
3. **Regression** — `python -m pytest tests/unit/test_stock.py -v`
4. **Error handling** — every COM boundary has a phase-specific error; readback failure is not reported as success.
5. **Security/data safety** — no database path is accepted as a write shortcut and no SQL is issued by the CLI.

### Task 5: Add the Application facade block

**Files:**

- Modify: `src/alphacam_cli/core/application.py`
- Test: `tests/unit/test_application.py`

**Step 1: Write the failing tests**

Verify `Application.stock_offcut_create`, `Application.stock_offcut_get`, and `Application.stock_offcut_delete` delegate exactly once to core with explicit stable-ID/request parameters, preserve structured failures, and do not invoke nesting/NC/milling methods. Add a test proving no end-to-end method is introduced.

**Step 2: Run tests to verify they fail**

```bash
python -m pytest tests/unit/test_application.py -k 'offcut or stock' -v
```

Expected: FAIL because the new facade methods do not exist.

**Step 3: Implement the thin facade**

Add only direct delegations following the existing lazy-import pattern. Keep COM lifecycle/session ownership in the existing Application context; do not compose create, nest, NC, or SimCNC operations.

**Step 4: Run tests to verify they pass**

```bash
python -m pytest tests/unit/test_application.py -k 'offcut or stock' -v
```

Expected: all selected tests PASS.

### Verification

After implementation:

1. **Format & Lint** — `ruff format --check src/alphacam_cli/core/application.py tests/unit/test_application.py && ruff check src/alphacam_cli/core/application.py tests/unit/test_application.py`
2. **Type check** — `mypy src/alphacam_cli/core/application.py`
3. **Regression** — `python -m pytest tests/unit/test_application.py tests/unit/test_stock.py -v`
4. **Kaizen** — no duplicated COM logic in Application; all safety remains in core.

### Task 6: Add gateway server/client/remote blocks

**Files:**

- Modify: `src/alphacam_cli/gateway/server.py`
- Modify: `src/alphacam_cli/gateway/client.py`
- Modify: `src/alphacam_cli/gateway/remote.py`
- Modify: `docs/gateway.md`
- Test: `tests/unit/test_gateway_server.py`
- Test: `tests/unit/test_remote.py`
- Test: `tests/unit/test_gateway_client.py` (create if no focused client test file exists)

**Step 1: Write the failing transport tests**

Cover:

- exact RPC method names and JSON parameters for get/create/delete;
- stable ID is transmitted as an integer, not a name-only selector;
- duplicate-name, wrong-type, not-found, unsupported-path, and COM errors preserve useful status/error text;
- server handlers delegate to Application exactly once and wrap unexpected COM errors as the existing gateway `COMError`;
- remote proxy exposes independent methods and does not chain operations;
- client timeout/connection behavior remains unchanged;
- the gateway contract documents no NC or machining side effect.

**Step 2: Run tests to verify they fail**

```bash
python -m pytest tests/unit/test_gateway_server.py tests/unit/test_remote.py tests/unit/test_gateway_client.py -k 'offcut or stock' -v
```

Expected: FAIL because the RPC blocks and contract entries do not exist.

**Step 3: Implement the transport blocks**

Add independent server handlers, `RemoteSession` methods, and `RemoteApplication` methods. Validate required parameters at the server boundary, delegate to Application, and never create a gateway-level workflow. Update the RPC table and error examples in `docs/gateway.md`.

**Step 4: Run tests to verify they pass**

```bash
python -m pytest tests/unit/test_gateway_server.py tests/unit/test_remote.py tests/unit/test_gateway_client.py -k 'offcut or stock' -v
```

Expected: all selected tests PASS.

### Verification

After implementation:

1. **Format & Lint** — `ruff format --check src/alphacam_cli/gateway/server.py src/alphacam_cli/gateway/client.py src/alphacam_cli/gateway/remote.py tests/unit/test_gateway_server.py tests/unit/test_remote.py tests/unit/test_gateway_client.py && ruff check ...`
2. **Type check** — `mypy src/alphacam_cli/gateway src/alphacam_cli/core/application.py`
3. **Regression** — `python -m pytest tests/unit/test_gateway_server.py tests/unit/test_remote.py tests/unit/test_gateway_client.py -v`
4. **Error handling** — malformed/missing IDs, transport errors, JSON-RPC errors, and COM errors are tested independently.
5. **Architecture** — grep the new handlers and confirm none call `nest`, `output_nc`, `mill_*`, or a multi-step orchestrator.

### Task 7: Add standalone Typer CLI commands

**Files:**

- Modify: `src/alphacam_cli/cli/cdm.py`
- Test: `tests/unit/test_cli_cdm.py`

**Step 1: Write the failing CLI tests**

Add isolated command tests for:

- `stock offcut-get ID` or the final stable-ID command name;
- `stock offcut-create ...` with explicit dimensions/material/thickness/name/path-source options;
- `stock offcut-delete ID` with confirmation and `--force` behavior;
- JSON output preserving stable ID and statuses;
- exit code 2 for invalid input, exit code 1 for not-found/wrong-type/duplicate/COM/unsupported failures, and exit code 0 only for verified success;
- no CLI command invokes another command or performs nesting/NC/milling.

**Step 2: Run tests to verify they fail**

```bash
python -m pytest tests/unit/test_cli_cdm.py -k 'offcut or stock' -v
```

Expected: FAIL because the standalone commands do not exist.

**Step 3: Implement the CLI blocks**

Expose thin commands under the existing stock app. Use the existing `require_platform`, `alphacam_context`, `resolve_app`, and COM error decorator patterns. Print a clear refusal when creation lacks a real path source; never pretend that a rectangle/list is an `ISheetPaths`. Keep confirmation before delete and display the stable ID in every destructive prompt/result.

**Step 4: Run tests to verify they pass**

```bash
python -m pytest tests/unit/test_cli_cdm.py -k 'offcut or stock' -v
```

Expected: all selected tests PASS.

### Verification

After implementation:

1. **Format & Lint** — `ruff format --check src/alphacam_cli/cli/cdm.py tests/unit/test_cli_cdm.py && ruff check src/alphacam_cli/cli/cdm.py tests/unit/test_cli_cdm.py`
2. **Type check** — `mypy src/alphacam_cli/cli/cdm.py`
3. **Regression** — `python -m pytest tests/unit/test_cli_cdm.py -v`
4. **UX/error handling** — verify readable messages and stable exit codes for every required failure class.
5. **Architecture** — commands remain one operation each; no hidden end-to-end flow.

### Task 8: Add read-only SimCNC status block

**Files:**

- Create: `src/alphacam_cli/core/simcnc_status.py`
- Modify: `src/alphacam_cli/core/application.py`
- Modify: `src/alphacam_cli/gateway/server.py`
- Modify: `src/alphacam_cli/gateway/client.py`
- Modify: `src/alphacam_cli/gateway/remote.py`
- Modify: `src/alphacam_cli/cli/cdm.py` or the existing diagnostics CLI entry point, choosing the established status location after inspection
- Test: `tests/unit/test_simcnc_status.py`
- Test: `tests/unit/test_gateway_server.py`
- Test: `tests/unit/test_remote.py`
- Test: `tests/unit/test_cli_diagnose.py` or `tests/unit/test_cli_cdm.py`

**Step 1: Write the failing tests**

Test a status query returning connection/state/last-seen fields from an injected read-only adapter, plus timeout, unavailable, malformed response, and permission errors. Assert that the adapter has no methods for NC upload, execution, movement, spindle, feed, or milling and that the RPC/CLI invokes only the read operation.

**Step 2: Run tests to verify they fail**

```bash
python -m pytest tests/unit/test_simcnc_status.py -v
```

Expected: FAIL because no SimCNC status block exists.

**Step 3: Implement the read-only block**

Use the project’s existing machine/gateway adapter if one exists; otherwise define the smallest injected interface required for a status read. Do not add write capabilities or couple this command to offcut creation.

**Step 4: Run tests to verify they pass**

```bash
python -m pytest tests/unit/test_simcnc_status.py tests/unit/test_cli_diagnose.py -v
```

Expected: all selected tests PASS and no write-call assertion is triggered.

### Verification

After implementation:

1. **Format & Lint** — `ruff format --check src/alphacam_cli/core/simcnc_status.py && ruff check src/alphacam_cli/core/simcnc_status.py`
2. **Type check** — `mypy src/alphacam_cli/core/simcnc_status.py src/alphacam_cli/gateway src/alphacam_cli/cli`
3. **Regression** — `python -m pytest tests/unit/test_simcnc_status.py tests/unit/test_gateway_server.py tests/unit/test_remote.py tests/unit/test_cli_diagnose.py -v`
4. **Safety** — review the diff for any NC/running/motion/milling API and reject it if present.

### Task 9: Add local integration/contract validation and cleanup harness

**Files:**

- Create: `tests/contract/test_offcut_stock_contract.py`
- Create: `tests/contract/conftest.py` if contract markers/connection fixtures are not already centralized
- Modify: `tests/integration/test_workflows.py`
- Create: `tools/scripts/offcut_cleanup.py` only if an existing cleanup utility cannot be reused
- Modify: `README.md` only for the final standalone command/status usage documented by the implementation

**Step 1: Write failing contract tests**

Define opt-in tests for:

- list/get a known sheet by stable ID and verify readback fields;
- create a uniquely named offcut only if the real `ISheetPaths` probe is available;
- reject duplicate name before mutation;
- reject whole-sheet deletion and missing ID;
- read back the created offcut with `IsOffcut=True`;
- delete the created offcut by stable ID and verify it is no longer found;
- cleanup executes in `finally`, is idempotent, and refuses to delete a whole sheet;
- concurrent/parallel calls are marked unsupported or serialized according to the chosen single-gateway policy.

**Step 2: Run local tests to verify gating**

```bash
python -m pytest tests/contract/test_offcut_stock_contract.py -m 'not live' -v
```

Expected: deterministic mock/skip results; no live mutation.

**Step 3: Implement the opt-in harness**

Reuse existing gateway/remote fixtures and add explicit environment/marker gating. Require a unique test prefix, record the returned stable ID, and use stable-ID cleanup only. Never discover cleanup targets by name alone.

**Step 4: Run local verification**

```bash
python -m pytest tests/unit tests/contract/test_offcut_stock_contract.py -m 'not live' -q
```

Expected: all local tests pass; live tests remain deselected.

### Verification

After implementation:

1. **Format & Lint** — `ruff format --check tests/contract tools/scripts && ruff check tests/contract tools/scripts`
2. **Type check** — `mypy tests/contract tools/scripts`
3. **Regression** — `python -m pytest tests/unit tests/contract/test_offcut_stock_contract.py -m 'not live' -q`
4. **Cleanup safety** — a failed setup, failed readback, and interrupted test each exercise `finally` cleanup without touching whole sheets.
5. **Concurrency risk** — document whether gateway serialization is relied upon and whether stable IDs are re-read immediately before destructive operations.

### Task 10: Run the Monika laptop contract through LXC123 and gateway

**Files:**

- Modify: `tests/contract/test_offcut_stock_contract.py`
- Create: `tools/scripts/run_offcut_laptop_contract.sh`
- Modify: `docs/gateway.md` only if the command requires a new documented invocation

**Step 1: Add the live test cases**

Mark the live suite with an explicit `live_laptop` marker and require gateway host `100.71.109.69`, port `8721`, and an opt-in environment variable. Include ping/info preflight and assert the gateway is the only COM execution path.

**Step 2: Run preflight from LXC123**

From the project environment, first verify connectivity without mutation:

```bash
ssh -i ~/.ssh/id_ed25519 48797@100.71.109.69 "python -c \"print('windows ssh ok')\""
tailscale status
.venv/bin/alphacam --remote --host 100.71.109.69 connect info
```

Expected: SSH works, Tailscale shows the stable DERP route (`relay "waw"`), and `connect info` reports AlphaCAM 2025/Router. If the route is direct or connectivity is unstable, stop the live test.

**Step 3: Run the opt-in contract**

From LXC123/project checkout:

```bash
OFFCUT_LIVE=1 OFFCUT_GATEWAY_HOST=100.71.109.69 \
  python -m pytest tests/contract/test_offcut_stock_contract.py -m live_laptop -v
```

Expected: preflight passes; creation either passes with proven `ISheetPaths` and readback or returns the documented explicit unsupported error; duplicate/wrong-type/not-found/delete safety tests pass; cleanup completes.

**Step 4: Confirm post-test state**

```bash
.venv/bin/alphacam --remote --host 100.71.109.69 stock list --json
```

Expected: no uniquely prefixed test offcuts remain. The output is captured in the test report without committing the database.

### Verification

After implementation:

1. **Test evidence** — record exact command, gateway host, AlphaCAM version, result counts, and cleanup result.
2. **Safety** — no NC command, milling command, machine movement, or SimCNC write operation is run.
3. **Rollback** — if the test fails after creation, rerun stable-ID read/delete cleanup only; if cleanup cannot prove `IsOffcut=True`, stop and escalate rather than guessing.
4. **Concurrency** — run no parallel destructive calls against the single gateway; document serialization and possible ID/name races.

### Task 11: Final review, verification, and implementation report

**Files:**

- Modify: all implementation/test/docs files listed above as needed during review
- Create: `docs/reports/2026-08-30-offcut-stock-cli.md`
- Modify: `TASKS.md` only after implementation results are known and the owner approves the persistent task update

**Step 1: Re-read the plan and inspect the complete diff**

Confirm every requirement has a corresponding test: stable ID, offcut-only delete, duplicate name, wrong type, not found, COM errors, real `ISheetPaths` or explicit refusal, readback, cleanup, gateway/CLI independence, SimCNC read-only behavior, laptop contract, and no end-to-end flow.

**Step 2: Dispatch final code review**

Use the project `code-reviewer` workflow for a full review of changed source, tests, transport contracts, error paths, secrets, and live-test safeguards. Require findings with `file:line`, severity, evidence, and fix; do not proceed with unresolved blockers.

**Step 3: Run the complete local verification**

```bash
ruff format --check src tests tools
ruff check src tests tools
mypy src
python -m pytest -q
python -m build
git diff --check
git status --short --untracked-files=all
```

Expected: formatting/lint/typecheck/tests/build succeed; diff check is clean; the only pre-existing untracked database remains untracked and unstaged.

**Step 4: Write the report**

Document facts and sources, decisions and alternatives, test outputs, laptop/gateway evidence, failures as `symptom -> root cause -> fix -> lesson`, unresolved research questions, risks, rollback steps, and explicitly what was not implemented (NC/motion/frezerowanie and any unsupported offcut creation path).

**Step 5: Commit only approved implementation changes**

After owner approval and successful verification, stage only the intended source/tests/docs/report files. Explicitly verify that `C:\ALPHACAM\LICOMDAT\sheet_database_v2.db` is not staged before any commit.

### Verification

After implementation:

1. **Full quality gate** — run every command in Step 3 and inspect complete output/exit codes.
2. **Final code review** — zero unresolved blocker/high findings; medium findings are fixed or explicitly recorded with owner decision.
3. **Repository safety** — `git diff --cached --name-only` contains no database file or secrets.
4. **Report completeness** — report contains evidence, rollback/cleanup, concurrency/stable-ID risks, and non-goals.
5. **Kaizen** — record only verified, reusable lessons; do not alter project knowledge or persistent task files without approval.

## Risks and Decisions to Preserve

- **Stable ID race:** an ID can become invalid between lookup and delete; re-read immediately before deletion and require `IsOffcut=True` on the same COM object/path. The single gateway serializes requests but does not remove external GUI/concurrent-client races.
- **Duplicate names:** names are human labels, not identities. Reject duplicate creation deterministically and never use a name to select a destructive target.
- **COM type ambiguity:** `IPaths`, `ISheetPaths`, wrapper objects, and raw dispatch are not interchangeable by appearance. A failed proof means unsupported, not “best effort.”
- **Partial persistence:** `NewOffcut` may return an unsaved object while `SaveOffcutToDatabase` may fail after mutation. Return phase-specific failure, read back if possible, and clean only a proven temporary offcut.
- **Session 0 configuration:** the gateway depends on the existing Nesting typelib and LocalSystem registry configuration. Missing `HKU\\.DEFAULT\\SOFTWARE\\Hexagon\\ALPHACAM` is an environment failure, not a reason to bypass validation.
- **Live data risk:** use a unique test prefix, stable-ID cleanup, and no repository copy of the production SQLite database. Stop on uncertain type/readback/cleanup state.
- **Scope risk:** no NC, machine movement, milling, nesting orchestration, or SimCNC write operation belongs in this implementation.
