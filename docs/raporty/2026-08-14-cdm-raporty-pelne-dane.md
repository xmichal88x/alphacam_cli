# CDM Raporty — pełne dane CDM we wbudowanych raportach AlphaCAM (2026-08-14)

## Cel

Wbudowane raporty AlphaCAM (PDF/XLSX, layout "CDM Nest Extra Details Portrait" +
`raport_test.acreps`, generowane przez Automation Manager podczas `cdm process`)
mają PUSTE dane CDM (klient, zamówienie, typ, wymiary, custom fields).
Custom manifest CLI (`cdm manifest --json`) ma wszystko. Cel: doprowadzić
raporty AlphaCAM do pełnych danych.

## Decyzje właściciela (istotne)

1. Produkcyjne wzory (door types) TYLKO z `C:\ALPHACAM\LICOMDIR\Alphadoor User Styles\Alphadoor Included` (np. P003/PS_03 — panele ścienne z podziałem).
2. Testowy CSV (csv3, 8 kolumn) działa TYLKO z P003 — inne wzory nie do testów.
3. **Raport PER ARKUSZ jest celowy** (pliki NC muszą być per arkusz) —
   `Reports_NestedSplitOption=2` NIE zmieniać na 0.
4. Pliki konfiguracyjne raportów: `C:\ALPHACAM\LICOMDIR\Reports` — nowe pliki
   tworzyć pod NOWĄ nazwą, istniejących NIE edytować.
5. Wcześniejsze raporty z pełnymi danymi były generowane przez CLI (stary
   system), teraz raport generuje CDM (wbudowany) — i stąd puste dane.

## Konfiguracja raportów — gdzie jest

### Baza AM (AutomationManager.vdb5)

`AM_ConfigurationSettings` (config 41 "Fronty"):
- `Reports_NestedReportDataOutputSettings = LICOMDIR\Reports\Settings\raport_test.acreps`
- `Reports_NestedReportLayout1/2 = LICOMDIR\Reports\CDM\Router Nest Reports\CDM Nest Extra Details Portrait.acrepx`
- `Reports_SilentReportGeneration = True`
- `Reports_NestedSplitOption = 2` (per arkusz — CELOWE)
- `Reports_ExportReportFormat = 15`
- `GenerateReports = True`, `ReportFileOutputLocation = LICOMDIR\Przetworzone Pliki Menadżera Automatyzacji`

### Pliki ustawień (C:\ALPHACAM\LICOMDIR\Reports)

- `Settings\raport_test.acreps` — data output settings: CaptureCDMData=true,
  CaptureCadToCamData=true, CaptureCustomAttributeData=true, obrazy wireframe
- `CDM\Router Nest Reports\CDM Nest Extra Details Portrait.acrepx` — layout DevExpress
  (ma bindingi CDMPartCSVCustomerName, CDMPartCSVCustomerOrderNumber, CDMPartWidth,
  CDMPartLength, CDMPartType, CDMPartProductionComment, CDMPartCustom*)
- `Data\*.acrepd` — dane raportu (XML VistaDB DataSet)
- `Layouts\...` — inne layouty (Full Sheet Reports, Sheet Labels, Single Part Report)

## Wyniki raportów .acrepd — stan na 2026-08-14 23:52

| Raport | Czas | generator | type | w/l | cust | ord | custom1 |
|---|---|---|---|---|---|---|---|
| CusPO 003 | 10:03 | CDM(?) | Typ Frontu 3 | 600/400 | Klient XYZ | PO-2026-888 | - |
| .acrepd (Csv3Test 002) | 10:41 | **CLI** | P003 | 500/500 | Klient 7 | PO-2026-007 | - |
| E2E Test 196 | 17:38 | CDM | (puste) | 0/0 | - | - | - |
| E2E Klient 196 | 23:10 | CDM | (puste) | 0/0 | - | - | - |
| RAP E2E 001 | 23:38 | CDM | (puste) | 0/0 | - | - | - |
| RAP E2E 002 (Typ Frontu 3) | 23:44 | CDM | Typ Frontu 3 | 600/400 | Michał Siemko | 196 | p_test_31 |
| RAP E2E 003 (L_B_10mm) | 23:52 | CDM | L_B_10mm | 400/500 | Michał Siemko | 196 | p_test_41 |

Kluczowa obserwacja: **raporty generowane przez CLI mają pełne dane CDM,
generowane przez CDM (wbudowany GenerateReports) mają puste** — ale UWAGA:
RAP E2E 002/003 (typy spoza biblioteki Included) też generowane przez CDM
miały pełne dane. Różnica między P003 (puste) a Typ Frontu 3/L_B_10mm (pełne)
wymaga dalszej weryfikacji — wg użytkownika CSV testowy pasuje TYLKO do P003,
więc testy z innymi typami nie są miarodajne dla produkcji.

## Eksperymenty (log)

### E1 — split option 2→0 (2026-08-14 ~23:39)
- Zmiana: `UPDATE AM_ConfigurationSettings SET Reports_NestedSplitOption = 0 WHERE ConfigurationSettingID = 41`
- Efekt: raport zamiast "RAP E2E 001 - MDF_18_18 (A1).acrepd" → "RAP E2E 001.acrepd" (jeden plik, bez podziału na arkusze)
- Dane CDM: NADAL PUSTE → split NIE jest przyczyną pustych danych CDM
- **PRZYWRÓCONO split=2** (celowe ustawienie właściciela — NC per arkusz)

### E2 — reprocess CusPO 003 (23:41)
- Ten sam job co rano (10:03, pełne dane) przetworzony ponownie → dalej PEŁNE dane CDM
- CusPO 003: fkType=4 (Typ Frontu 3, UserStyleName=F_01 — wzorzec .arb z Alphadoor Included/Wzornik_1/F_FRAME)
- Wniosek: wzorzec .arb SAM w sobie nie czyści danych CDM

### E3 — RAP E2E 002 (23:44), Typ Frontu 3 przez csv3
- Pełne dane CDM: type=Typ Frontu 3, w=600 l=400, cust=Michał Siemko, ord=196, custom1=p_test_31
- fkType=4, JobType=1 (finalize CLI) — działa

### E4 — RAP E2E 003 (23:52), L_B_10mm przez csv3
- Pełne dane CDM (type=L_B_10mm, cust=Michał Siemko, ord=196, custom1=p_test_41)
- ⚠️ NIE testować więcej z L_B_10mm — CSV testowy nie pasuje do tego wzoru (decyzja właściciela)

### E5 — RAP E2E 001 (23:35/23:38), P003 przez csv3 (właściwy test produkcyjny)
- BAZA: fkType=68 (P003), w=500 l=500, cust='Michał Siemko', ord='196', qty=1, ActiveInProcess=True, UVS dopełniony
- RAPORT .acrepd: CDMPartWidth=0, CDMPartLength=0, cust/ord/type/style PUSTE; CDMPartReportID=1..5 istnieją
- **Root cause do zbadania: P003 (wzorzec paneli ściennych z podziałem A1/A2, PS_03.arb) traci dane CDM przy generowaniu przez CDM**

## Hipotezy do przetestowania

1. H1: CaptureCDMData w raporcie wymaga, by order detail miał CDM_PK/CDM_OrderID > 0 (u nas 0 — import przez CLI) — porównać z jobem utworzonym w GUI
2. H2: Wzorzec P003 generuje WIELE części z 1 order detail (podział A1/A2) — raport nie wiąże CDM data per część
3. H3: Ustawienia raportów w GUI (zakładka Raporty) mają osobną konfigurację per config, inną niż baza
4. H4: `SuppressItemNumbersFromNestedSheetImages`/inne opcje .acreps wpływają na capture
5. H5: Makro Process() generuje raport z rysunku (drawing) bez dostępu do joba CDM — dane CDM brane z geometrii, nie z bazy

## Notatki użytkownika (cytaty)

- "wzory tylko z tej lokalizacji: C:\ALPHACAM\LICOMDIR\Alphadoor User Styles\Alphadoor Included"
- "Zmieniło się to że tamten raport był wygenerowany przez cli. teraz generuje przez cdm."
- "dodatkowo zmieniłem że raport jest per arkusz bo pliki nc muszą być per arkusz a nie jeden dla wszystkich"
- "przesłany przykład csv działa tylko z p003 i zadnym innym wzorem"
- "do testów możesz używać różnych ustawień aby zbadać przyczynę."
