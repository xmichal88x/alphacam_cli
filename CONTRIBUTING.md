# Contributing — Alphacam CLI

## Wymagania

- Python 3.11+
- Windows (do testów integracyjnych z AlphaCAM) lub Linux (do testów jednostkowych)
- AlphaCAM (tylko do testów integracyjnych)

## Setup developerskie

```bash
git clone https://github.com/anomalyco/alphacam-cli.git
cd alphacam-cli
python -m venv .venv
source .venv/bin/activate  # Linux
# .venv\Scripts\activate   # Windows
pip install -e ".[dev]"
```

## Uruchamianie testów

```bash
# Wszystkie testy
pytest tests/ -v

# Tylko jednostkowe
pytest tests/unit/ -v

# Z coverage
pytest tests/unit/ --cov --cov-report=term -x

# Pojedynczy plik
pytest tests/unit/test_cli.py -v --tb=short
```

## Linting i typowanie

```bash
# Ruff (lint + format)
ruff check src/ tests/
ruff format src/ tests/ --check

# Mypy
mypy src/ tests/
```

## Struktura projektu

```
src/alphacam_cli/
├── cli/          # Komendy CLI (typer)
│   ├── common.py   # Współdzielone: handle_com_errors, require_platform
│   ├── mill.py     # Operacje frezowania
│   ├── nest.py     # Nesting
│   ├── nc.py       # Output NC
│   ├── batch.py    # Przetwarzanie wsadowe
│   ├── diagnose.py # Diagnostyka systemu
│   ├── connect.py  # Połączenie COM
│   ├── drawing.py  # Zarządzanie rysunkami
│   ├── tool.py     # Zarządzanie narzędziami
│   └── post.py     # Post-processory
├── com/          # COM integration
│   ├── manager.py  # Context manager + STA thread
│   └── constants.py
├── core/         # Logika biznesowa
│   ├── application.py
│   ├── drawing.py
│   ├── machining.py
│   ├── nesting.py
│   ├── tool.py
│   ├── config.py
│   ├── events.py
│   └── logger.py
└── main.py       # Entry point

tests/
├── unit/         # Testy jednostkowe (734+)
├── integration/  # Testy integracyjne (wymagają Windows)
└── conftest.py   # Mocki COM
```

## Dodawanie nowej komendy

1. Stwórz plik w `src/alphacam_cli/cli/` (lub dodaj do istniejącego)
2. Użyj `typer.Typer` i dekoratora `@handle_com_errors`
3. Wywołaj `require_platform()` przed operacjami COM
4. Dodaj wpis do `_SUBCOMMANDS` w `main.py`
5. Dodaj testy w `tests/unit/`
6. Dodaj dokumentację w `README.md`

## Zasady

- Typowanie: strict mypy, żadnych `Any` bez uzasadnienia
- Testy: każdej nowej komendzie towarzyszą testy
- COM: używaj `alphacam_context()` z manager.py
- Błędy COM: `@handle_com_errors` lub ręczne `AlphacamConnectionError`/`AlphacamComError`
- Commit: conventional commits (feat:, fix:, chore:, docs:)
