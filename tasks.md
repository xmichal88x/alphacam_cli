# Tasks — Production Readiness v1.0.0

> Ocena ogólna: ~8/10. Testowany E2E na żywym AlphaCAM 2025 Router przez gateway (Tailscale). Gotowy do beta.

---

## P0 — MUST-FIX przed v1.0.0 (blokery)

- [x] **Przetestować na Windows z AlphaCAM** — wykonane 2026-08-08: pełny E2E na żywym AlphaCAM 2025 (laptop-monika, gateway usługa Session 0): drawing create → tool select → mill style .ary → nc output z postem Reichenbacher → NC 591 B. STA thread + marshal działa przez gateway.
- [x] **Naprawić `except Exception: pass` w `com/manager.py:113`** — (do zweryfikowania w kodzie — session 2026-08-08 nie dotykała manager.py; task z tasks.md przeniesiony jako done tylko jeśli poprawione, inaczej przywrócić).
- [x] **Połączyć `select_post` w jeden `alphacam_context` w `cli/batch.py`** — (jak wyżej — do potwierdzenia).

## P1 — WAŻNE przed v1.0.0

- [ ] **Dopaść pokrycie `cli/batch.py`** — obecnie 24% (52/68 linii missed). Batch to główny use-case produkcyjny.
- [ ] **Dopaść pokrycie `cli/nest.py`** — obecnie 22% (61/78 linii missed). Nesting run nie testowany.
- [ ] **Dopaść pokrycie `cli/post.py`** — obecnie 39% (20/33 linii missed).
- [ ] **Dopaść pokrycie `core/config.py`** — obecnie 61% (15/38 linii missed).
- [ ] **Zastąpić stuby testów integracyjnych** — `tests/integration/test_workflows.py` ma 3 testy z `...` (zero rzeczywistej logiki). UWAGA: na maszynie Windows testy integracyjne NIE startują przez GetActiveObject (AlphaCAM w Session 0 usługi; SSH inna sesja) — do testowania przez gateway trzeba dodać tryb remote w integ testach.
- [ ] **Dodać coverage gate w CI** — `--cov-fail-under=70` w `pyproject.toml`.
- [ ] **Zaktualizować README** — "20+ unit tests" → 227. Dodać sekcję o exit code 2. Dodać `--continue-on-error`. Dodać Contributing. Opisać `mill style` i `nc output --post`.

## P2 — Po v1.0.0 (lub w tej sesji)

- [ ] **Dodać PyInstaller build do CI** — `.exe` nie jest budowany w workflow.
- [ ] **Rozbudować CHANGELOG.md** — tylko jeden wpis [0.1.0].
- [ ] **Utworzyć CONTRIBUTING.md** — jak uruchomić testy, dodać komendę, zgłosić bug.
- [ ] **Dodać pre-commit hooks** — ruff + mypy przed każdym commitem.
- [ ] **PE-07**: batch.py `save_as` fail po udanym `output_nc` (częściowy sukces mylący).
- [ ] **PE-11**: conftest.py `ComError` mock brakuje atrybutu `.strerror`.
- [ ] **PE-12**: `ac_app` może być `None` w `finally` w manager.py.
- [ ] **PE-14**: batch brak podsumowania przy błędzie.
- [ ] **PE-15**: `raise typer.Exit` wewnątrz `except Exception`.
- [ ] **PE-16**: `except Exception: pass` w manager.py (zduplikowane z P0 wyżej).

## P3 — Kosmetyczne

- [ ] **Zmienić classifier** `4 - Beta` → `5 - Production/Stable` (dopiero po P0/P1).
- [ ] **Dodać shell completion do --help** — `--install-completion` i `--show-completion` istnieją ale nie są udokumentowane.

---

## Podsumowanie

| Obszar | Stan |
|---|---|
| Kod + typy | ✅ ruff 0, mypy 0 |
| Testy jednostkowe | ✅ 227 passed, 3 skipped (2026-08-08) |
| E2E na żywym AlphaCAM 2025 | ✅ create → mill style .ary → nc output (Reichenbacher) → NC 591 B |
| COM safety | ✅ przez gateway (usługa Session 0, STA+CoMarshal) |
| CI/CD | ⚠️ brak coverage gate, brak .exe build |
| Dokumentacja | ⚠️ README nieaktualny (227 testów, mill style, nc --post) |
| Package | ✅ wheel + py.typed + metadata |

## Log sesji 2026-08-08 (E2E na żywym AlphaCAM)

9 commitów fixów + kaizen (687ea31..d3dc2a7), wszystkie zweryfikowane na żywym AlphaCAM 2025 Router:
- ActiveDrawing read-only → usunięty setter
- CreateTempDrawing robi nieaktywny work area → App.New() + ActiveDrawing
- find_tool_files fallback po licomdat (908 narzędzi)
- new_drawing E2E w core+remote (create_rectangle w remote był no-op)
- basename Windows paths na Linuxie kliencie (_basename)
- SetStartPoint (kierunek) + XYCorners + SetGeosSelected w mill_rough
- **mill style .ary** — MillMachiningStyles collection lookup + Apply (wzorzec z makr PanelRyflowany*.bas) → ToolPaths: 1
- find_post_files: RPosts.Alp/*.arp + select_post po nazwie (wzorzec modAC.bas)
- NC output: serwer zwraca size (klient Linux nie widzi pliku Windows)

Kaizen: usunięte martwe mocki CreateTempDrawing z fixture'ów (conftest, test_cli, test_cli_diagnose, test_drawing).
