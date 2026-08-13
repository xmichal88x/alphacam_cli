# Raport: Automation Manager (CDM) — pełny inwentarz wdrożeniowy Przemysłu 4.0

> Data: 2026-08-09 | Maszyna: laptop-monika (Windows 11, AlphaCAM 2025 Router) | Dostęp: SSH + gateway RPC (port 8721)
> Źródła audytu: (a) baza `C:\ALPHACAM\LICOMDAT\Automation Manager Data\AutomationManager.vdb5` (VistaDB 5, odczyt przez PowerShell + VistaDB.5.NET40.dll — 37 tabel, schema GETSchema), (b) typelib/DLL `AcamAddIns.dll` (interfejsy `Alphacam.AddIns.I*`), (c) `AMSettings.acamcore` (XML konfiguracji GUI), (d) stan implementacji w repo `alphacam_cli`.

---

## 1. Kontekst

- **Audyt Automation Managera (CDM — Cabinet Door Manufacturing, dodatek AlphaDOOR/Hexagon do AlphaCAM 2025 Router)** wykonany 2026-08-09 na żywej maszynie produkcyjnej laptop-monika.
- Zakres: pełny inwentarz wdrożeniowy pod kątem Przemysłu 4.0 — co jest zaimplementowane w CLI, co kryje baza VistaDB, co udostępnia API COM, co zostało do wdrożenia.
- Dostęp produkcyjny: gateway RPC Session 0 (usługa AlphaCAMGateway, port 8721, `alphacam --remote --host 100.71.109.69`), SSH `48797@100.71.109.69`.

---

## 2. Stan obecny CLI (co jest zaimplementowane)

Komendy `alphacam cdm ...`:

| Komenda | Zachowanie | Detale |
|---|---|---|
| `create JOB TYPE --width --length --quantity --bypass-nest --material` | Tworzenie joba CDM | NewCDMJob → JobName → SaveToDatabase → AddCDMOrderDetail → Width/Length/Quantity/ByPassNest → SaveToDatabase; materiał (nazwa→ID z SQLite sheet database lub default z vdb5); walidacja; duplikat nazwy; czyszczenie sierot przy błędzie |
| `types` | Lista typów drzwi | CDM_DoorTypes z vdb5 + typy z jobów, merge dedupe |
| `jobs` | Lista jobów | nazwa |
| `import CSV --name --config --job --separator --header --material` | Import CSV | Własny parser CSV (Style,Quantity,Width,Height,DesignDims[,Material]), walidacja przed utworzeniem joba, czyszczenie pustych jobów |
| `delete JOB` | Usuwanie joba | DeleteFromDB |

**Jakość:** testy 564 passed, ruff 0, mypy 0. E2E na żywym AlphaCAM — pełny cykl potwierdzony.

---

## 3. Inwentarz bazy (37 tabel)

### Tabele `AM_*`

AM_AssembliesCustomPropertyMapping, AM_AssembliesNonMachinedLayerNames, AM_ConfigurationSettings, AM_CustomerDetails, AM_DBVersion, AM_Drilling, AM_ExtensionData, AM_ExtensionDataRow, AM_Extensions, AM_FileNameConfiguration, AM_FittingGeos, AM_Fittings, AM_ImportSettings, AM_ImportSettingsParameter, AM_JobDetails, AM_JobFileComponentFolder, AM_JobFileDefaults, AM_JobFileDetails, AM_LayerMapping, AM_MachiningOrder, AM_Materials, AM_Multidrill, AM_NestZones, AM_ParametricVariables, AM_SelectedDrillingConfigurations, AM_SelectedSheetDefaults, AM_SelectedSheets, AM_Settings, AM_Setups, AM_ToolOrder, AM_ToolOrderLists

### Tabele `CDM_*`

CDM_ConfigurationSettings, CDM_DoorPaths, CDM_DoorTypes, CDM_OrderDetails, CDM_SelectedDrillingConfigurations, CDM_UserStyles

---

## 4. API COM (AcamAddIns.dll) — 21 kolekcji IAutomationManager*

### Kolekcje

IAutomationManagerJobs, JobFiles, Customers, ConfigurationSettings, ImportSettings, ImportSettingFields, Setups, Fittings, LayerMappings, NestMaterials, MachiningOrders, MachiningOrderLists, MultidrillHeads, DrillingConfigurations, ParametricVariables, ExtensionDataItems, ExtensionDialogItems, JobFileComponentFolders.

### Kluczowe metody CDM

- **Tworzenie:** NewCDMJob, AddCDMOrderDetail (FromExisting / InsertedDrawing / ToParentAndChildrenFromStyle), AddFileToCDMJob, AddFileToAMJob
- **CSV:** CreateJobsFromCSVFile, CreateAndRunJobFromCSV, ImportCSVToJob, ImportCDMCSVImport
- **Import danych:** ImportCDMDatabase, ImportCDMDoorTypes, ImportCDMMaterialLibrary, ImportCDMOrders, ImportCDMToolOrdering
- **Procesowanie:** ProcessFile, ProcessJobFile, ProcessMultiProcJobs, ActivateJobFileInProcess, ActivateOrderDetailInProcess
- **Inne:** IsCDMAuthorised, DeleteFromDB, CopyGlobalSettingsBetweenJobs / JobFiles / OrderDetails

---

## 5. Ustawienia globalne — AM_Settings (10+ kolumn, obecne wartości)

| Kolumna | Wartość |
|---|---|
| fkConfigurationSettingID | 41 (Fronty) |
| fkSetupID | 1 |
| fkToolOrderID | 1 |
| CustomField1..25 | — |
| SuppressGeometryError | — |
| GenerateProcessingLogs | False |
| LogFileLocation | `''` |
| WizardPreview, WizardPreviewUseISO | — |
| AMVisibleCustomColumns, CDMVisibleCustomColumns | — |
| AMCompiledCustomColumnsString, CDMCompiledCustomColumnsString | — |
| Multidrill | False |

---

## 6. Konfiguracje — AM_ConfigurationSettings (~180 kolumn)

3 rekordy: **1 "Not Selected"**, **40 "CDM_Materiał 17mm"**, **41 "Fronty"** (aktywna).

### Podstawowe

ConfigurationSettingName, PostProcessor, DrawingFileOutputLocation, NCFileOutputLocation, ReportFileOutputLocation, NCFileExtension, ReplaceSpaceWithUnderscore, CustomVBAMacro, DisableScreenUpdates, ClearOutputFolders, GenerateNC, GenerateReports, CreateDefaultMaterial, CreateDefaultMaterialUsingGeometry, SaveGeneratedAutostyles, ReadFileInformationOnImport, ShowMaterialSelectorAfterImport, CompiledFileName, CompiledBaseName

### Nesting (~60)

Nesting_Method, Nesting_PackTo, Nesting_GapBetweenPaths, Nesting_GapAtSheetEdge, Nesting_ExtraGapAtLeadStart, Nesting_TimePerSheet, Nesting_OptimisationLevel, Nesting_SearchResolution, Nesting_CutSmallPartsFirst, Nesting_DrillThenCutInnerPathsFirst, Nesting_LeaveEdgeGapUncut, Nesting_MinimiseToolChanges, Nesting_UseBridged, Nesting_UseOnionSkin, Nesting_PreventNestingInApertures, Nesting_UseSupportTags, Nesting_SplitNestedSheetDrawings, Nesting_OnionSkinMinXYDimension, Nesting_OnionSkinMinPartArea, Nesting_OnionSkinThickness, Nesting_OnionSkinCutOption, Nesting_OnionSkinApplyToInternalThroughCuts, Nesting_UseNameIdentifiers, Nesting_BridgedNestingUseToolWidth, Nesting_BridgedNestingBridgeWidth, Nesting_CutWholePartTogether, Nesting_GroupEachPartSeparately, Nesting_MinimiseSheetPatterns, Nesting_NestSmallPartsFirst, Nesting_OrderByPart, Nesting_RemoveGroups, Nesting_RepeatFirstRowColumn, Nesting_SuppressFinalSort, Nesting_SuppressRedraw, Nesting_TryRotatedPartFirstOnAllParts, Nesting_TotalTime, Nesting_OffcutPreference, Nesting_SheetOrderType, Nesting_EvenlySpacedParts, Nesting_OutputDrawingWithAllNestedSheets, Nesting_SaveRejectedPartsToNewJob, Nesting_OptimiseToolpathOverlapping, Nesting_SaveOffcuts, Nesting_OffcutWidth/Height/Type/MachiningStyle/Side, Nesting_AllowSolidParts, Nesting_AssistedNest, Nesting_SaveOffcutsToDatabase, Nesting_SuppressDuplicateSheets, Nesting_ForceStrictPriorities, Nesting_CommonLineCutting, Nesting_SheetAlignment, Nesting_AlignmentZLevel, Nesting_ReverseSideNesting, Nesting_ReverseSideSheetOrdering/Turning/MachiningOrder/UseAutoStyle/AutoStyle/AutoStyleApplyTo/ToolOrdering/SheetSquaring/SheetEdges/SheetSquaringAmount/SheetSquaringAutoStyle/AddRevPartsAsNonNested/SolidsProcessing/SolidsLayerMappingSetupID, Nesting_UseJoinSawCuts (+Tolerance/Bidirectional/SuppressErrors), Nesting_InactivityTimeout

### Raporty (~30)

Reports_NestedReportDataOutputSettings, Reports_NestedReportLayout1..4, Reports_NonNestedDataOutputSettings, Reports_NonNestedReportLayout1..4, Reports_NestedReportLayout3..4, Reports_NonNestedReportLayout3..4, Reports_SilentReportGeneration, Reports_ExportReportFormat, Reports_NestedSplitOption, Reports_NonNestedSplitOption, Reports_OutputToLabel, ReportsPrinter_NestedLayout1..4, ReportsPrinter_NonNestedLayout1..4, ReportsExportFormat_NestedLayout1..4, ReportsExportFormat_NonNestedLayout1..4

### Zespoły

Assemblies_ProcessAssemblies, Assemblies_NonMachinedPartsQuery, Assemblies_NonMachinedPartsAutoQuery, Assemblies_NonMachinedPartsLayerNames, Assemblies_UseCustomLayerMapping, Assemblies_CustomPropertyMappings, Assemblies_DXFDWGTranslator, Assemblies_HideNonMachinedComponents, Assemblies_PrefixAssemblyNameToOutputFiles

### Inne

MultidrillHeadID, CheckTableCollision, CheckTableCollisionZValue, CheckTableCollisionMethod, CheckTableCollisionTolerance, CheckTableCollisionMaterialZ0Location, AutoAssociateMaterials, AutoAssociateMaterialsTolerance, WorkplanAutomaticSheetReservation

---

## 7. Domyślne joba — AM_JobFileDefaults (per konfiguracja)

fkSetupID, fkToolOrderID, fkMaterialID (czytane przez CLI), NestPart, QuantityRequired, NestPartRotationMethod, NestRotationAngle, AutoAssociateMaterialType, SmallNestedPart, PartOrigin, NestTryMirroredShape, NestPriority, NestKitNumber, CustomField1..25, JobType, NestIncludeSolidParts, NestExtraPartGap, NestIgnore3DPaths, NestIgnorePathsOnWorkPlanes, NestPartRotationMethod2

---

## 8. Setupy — AM_Setups (2 rekordy)

1 **"None"**, 93 **"Nowe Ustawienia 1"**. ~80 kolumn:

SetupName, FE_WhatToExtract, FE_DatumPointX/Y/Z, FE_AutoAlignPart, FE_UsePanelAlignment, FE_ChordTolerance, FE_ZLevelStep, FE_UseOpenAirPocketMethod, FE_AddZLevels, FE_ExtractAllFaces/TopFace/BottomFace/LeftFace/RightFace/FrontFace/BackFace, FE_RemoveDuplicateFeatures, GeometryQuery, GeometryAutoQuery, FE_LimitThroughHoles, FE_ConcentricHolesTopZLevel, FE_MaxDiaDrilledHoles, FE_MaxAnglePartialHoles, FE_IncludePartialHoles, FE_OptimisePlanes, FE_RetainSolid, FE_CreateWorkVolume, FE_AlignLongestEdgeWithXAxis, WPO_OrderWorkplanes, WPO_RotateAbout, WPO_RotateCW, WPO_FiveAxisControl(+CW), WPO_ClearEmptyPlanes, IMP_CreateZFromParallelPlanes, FE_ContourExtractionMode, FE_DrillableHolesExtractionMode, FE_ExtractFromFaceMode, FE_ExtractFromFaceBodyOutlines, FE_AlignVectorWithXAxis, FE_ContourQuery, FE_DrillableHoleQuery, FE_UseContourQuery, FE_UseDrillableHoleQuery, FE_ContourExtractionMethod, IMP_Project3Dto2D, IMP_StepLength, IMP_ChordToleranceForArcs, IMP_CommonLineRemoval, IMP_JoinResultingGeos, IMP_ConvertSpline, IMP_Tolerance, IMP_DeleteOriginal, IMP_JoinResultingLinesOrArcs, IMP_SetElementZLevels, IMP_DistanceAboveSpline, IMP_DistanceBelowSpline, UseMinimumBoundingBoxAlignment, MinimumBoundingBoxAlignmentAxis, SetupSeqNum

---

## 9. Materiały — AM_Materials (4 rekordy)

| MaterialID | Nazwa | Wymiary |
|---|---|---|
| 1 | Not Selected | 0x0x0 |
| 2 | Material 2 - 2070 x 2800 | 2070 x 2800 x 19 |
| 3 | Material 3 - 2440 x 1220 | 2440 x 1220 x 19 |
| 4 | Material 4 - Imperial 96 x 48 | 96 x 48 x 0.75 |

Kolumny: MaterialID, MaterialName, SheetWidth, SheetLength, SheetThickness, GrainRestriction.

---

## 10. Klienci — AM_CustomerDetails (1 rekord)

CustomerID, CustomerName, AddressLine1/2, City, Country, PostZipCode, ContactName, TelephoneNumber, EmailAddress, WebsiteAddress.

---

## 11. Ustawienia importu CSV — AM_ImportSettings + AM_ImportSettingsParameter (2 rekordy + mapowanie)

| id | Nazwa | Kluczowe flagi |
|---|---|---|
| 3 | "sklep CSV" | DelimiterChar=`,`, IgnoreHeader=False, IsCDMImport=True, CreateJob=True, **Selected=True** |
| 4 | "Ustawienia Importu CSV 2" | kol6→260 (zamiast 524) |

### Mapowanie kolumn (AM_ImportSettingsParameter)

- **id=3 "sklep CSV":** kol1→256, kol2→259, kol3→257, kol4→258, kol5→264, kol6→524, kol7→512, kol8→513
- **id=4 "Ustawienia Importu CSV 2":** kol6→260 (zamiast 524)

### Mapowanie typów pól

| ID | Pole |
|---|---|
| 256 | cdmDoorType |
| 257 | cdmDoorWidth |
| 258 | cdmDoorHeight |
| 259 | cdmDoorQuantity |
| 260 | cdmDoorMaterial |
| 261 | cdmDoorCustomerName |
| 262 | cdmDoorOrderNumber |
| 263 | cdmDoorItemNumber |
| 264 | cdmDoorDesignDimensions |
| 265 | cdmDoorProductionComment |
| 266+ | cdmDoorCustomField1..25 |
| 271 | rotation |
| 272 | angle |
| 274 | nest priority |
| 298 | drilling |
| 299 | small nest |
| 512 / 513 / 524 | pola ogólne AM (klient / nr zamówienia / materiał) |

> **KLUCZOWE:** CLI używa własnego sztywnego parsera (5-6 kolumn) i **IGNORUJE** to mapowanie z bazy.

---

## 12. Pozycje zamówień — CDM_OrderDetails (~70 kolumn)

CDMOrderDetailID, fkJobDetailID, fkMaterialID, CDM_PK, CDM_OrderID, StyleNumber, StyleName, fkTypeID, Quantity, OrderDetailDoorWidth, OrderDetailDoorLength, CornerRadius, UserVariableString, UserDescriptionString, UserValue_0..6, IgnoreOuterGeometry, ByPassNest, RotationMethod, RotationAngle, NestingPriority, CSV_CustomerName, CSV_OrderNumber, CSV_ItemNumber, OversizeX, OversizeY, ProductionComment, CDMCustomField1..25, PressID, ColourID, ColourRotationMethod, PostProcessor, ComponentGrouping, ReverseMachiningFilename, NestZoneID, HandleID, fkParentOrderDetailID, ActiveInProcess, HasDrilling, SmallNestPart

---

## 13. Typy drzwi — CDM_DoorTypes (35 rekordów)

DoorTypeID, CDM_ID, TypeName, CreatorName, DateAdded, Comment, Width, Length, CornerRadius, ByPassNest, RotationMethod, RotationAngle, UserStyleName, UserVariableString, UserDescriptionString, UserValue_0..6, OversizeX, OversizeY, PressID, ColourID, ColourRotationMethod, IgnoreOuterGeometry, HandleID, HasDrilling, SmallNestPart

---

## 14. Ścieżki drzwi — CDM_DoorPaths (34 rekordy, ~100 kolumn)

PathID, CDM_PathID, DoorTypeID, PathName, PathNumber, LastModified, GroupID, ToolName, ToolFullPath, ToolNumber, ToolOffset, MachiningMethod, SafeRapid, RapidDownTo, FinalDepth, FinalDepthPercentage, IsFinalDepthPercent, McComp, CompOnRapid, XYCorners, SpindleSpeed, DownFeed, CutFeed, CutDirection, LeadIn, LeadOut, SlopeIn, SlopeOut, MaterialTop, NumberOfCuts, Stock, ChordError, DepthsOfCutSpecified, ThicknessFirstCut/LastCut(+Percent), Diameter, FinalPassIsland, PocketType, StartCutting, StepLength, MultiplePasses, PathOffsetSide/From/Value, PocketBoundary, ToolDirectionCW/Reversed, ToolInOut, ToolSide, LeadLineLength(+Out), LeadArcRadius, LeadApproachAngle, LeadOverlap, Lead3DApproachAngle/Approach, LeadEntryPointIsCorner, WidthOfCut, InsertFilePath, InsertFileReferencePoint, InsertFilePointX/Y, EngraveCornerAngle, Pocket3DApproach, CreationMethod, MachiningStyle, CutType, PartialStartElemIndex/Dist, PartialEndElemIndex/Dist, SlowDownForCorners, DecelerationDistance, NumberOfSteps, SlowDownTo, DoNotSlowDownRadius, IgnoreAngleGreaterThan, AccelerateOutOfCorner, InsertParametricGroupNumber, ToolSidePartialReverse, SimpleEngraveFeed, SimpleEngraveClearance

---

## 15. Style użytkownika — CDM_UserStyles (265 rekordów)

UserStyleID, FullFileName, VBAProjectName

---

## 16. Job files — AM_JobFileDetails (0 rekordów)

JobFileID, fkJobDetailID, fkSetupID, fkMaterialID, fkToolOrderID, fkNestZoneID, Filename, PartName, ItemNumber, Length, Width, Thickness, QuantityRequired, NestPart, NestPartRotationMethod, NestRotationAngle, NestTryMirroredShape, NestPriority, NestKitNumber, ReverseSideNesting, PartOrigin, CustomField1..25, SmallNestedPart, UseVectorAlignment, VectorAlignmentX/Y/Z, SubcomponentParentID, HasSubcomponents, SubComponentFolderID, HasFittings, AutoAssociateMaterialsThicknessID, AutoAssociateMaterialName, fkParentJobFileID, ActiveInProcess, TurnPartOver(+Axis), NestIncludeSolidParts, IsAssemblyMaster, DoNotMachine, NestExtraPartGap, HasDrilling, NestIgnore3DPaths, NestIgnorePathsOnWorkPlanes, NestPartRotationMethod2, UseMinimumBoundingBoxAlignment(+Axis), UseInitialAngleAlignment, InitialAlignmentAngle, PartAlignmentMethod

---

## 17. Pozostałe obszary (z ilością rekordów)

| Obszar | Rekordy | Kluczowe kolumny |
|---|---|---|
| AM_MachiningOrder | 28 | ToolOrderID, fkToolOrderListID, MachiningStyleName, LayerName, SeqNum, IsMultidrill |
| AM_ToolOrderLists | — | ToolOrderListID, Name, IsCDMMachiningOrderList, CompareToolName/Number/Offset |
| AM_Multidrill | 0 | MultidrillHeadID, Name, Selected, ConfigurationDB, FeedRate, SpindleSpeed, SafeRapidDistance, RapidDownTo, MaterialTop, BottomOfHole, DrillToHoleTolerance, HoleCentreToCentre, HoleDepthAt, TraverseAt, ShowSlaved, UseAutoZHoleDepths, ApplyBottomOfHoleNonAutoZHoles, AutoZStockAmount |
| AM_Drilling + AM_SelectedDrillingConfigurations + CDM_SelectedDrillingConfigurations | — | wiercenie per detal |
| AM_Fittings (+ AM_FittingGeos) | 1 | FittingID, fkJobFileID, FittingType, FittingFile |
| AM_LayerMapping | — | LayerMappingID, fkSetupID, LayerName, MachiningStyleName, MachiningOrder, IsFeatureLayer, ToolSideClosedGeo/OpenGeo, ToolDirectionClosedGeo/OpenGeo, StartPoint, UseGeoZLevelsIfPresent, AutoZLevelTop/Bottom, LayerOrder, StartPointPreference, ApplyIndividuallyToEachGeometry |
| AM_ParametricVariables | 0 | ParametricVariableID, fkJobFileID, ParametricVariableName, ParametricVariableValue |
| AM_NestZones | — | strefy nestingu (fkNestZoneID) |
| AM_FileNameConfiguration | — | szablony nazw plików wyjściowych |
| AM_ExtensionData/Row + AM_Extensions | — | dane rozszerzeń |
| CDM_ConfigurationSettings | 4 (cfg 40/41) | CDMConfigurationSettingID, fkConfigurationSettingID, PartRecoveryX/Y, PartRecoveryIgnoreGrain, CaptureNestedPartPositions, DisableNesting, DisableNestingOversizeX/Y, UseDefaultPress, PressGroupByMaterialThickness, CustomMacro, UseDataFromToolFile, UseSameStartPoint, UseDrawingExtentsForInsertedDrawingOperations, GenerateNCForParts, ZDepthTolerance, PreviewMaterialThickness |
| AMSettings.acamcore | — | ShowCDM=1, UseSQLServer=0, UseCVMaterialsLibrary=0, UseWorkplan=0, ShowPartProcessing=0 |

---

## 18. Co NIE jest zaimplementowane (podsumowanie luk)

1. **Import CSV:** brak użycia mapowania z bazy (AM_ImportSettings), brak kolumn klient / nr zamówienia / komentarz produkcyjny / oversize
2. **OrderDetails:** ~60 pól nieobsługiwanych (CornerRadius, Rotation, NestingPriority, Press/Colour/Handle, CustomFields 1-25, ParentOrderDetail, HasDrilling, SmallNestPart, OversizeX/Y, ProductionComment, ActiveInProcess...)
3. **Konfiguracje:** tylko odczyt nazwy i ustawienie na jobie; ~180 ustawień (NC, raporty, nesting, zespoły) nieczytane / niededykowane
4. **JobFileDefaults:** tylko fkMaterialID
5. **Setupy:** zero (80+ parametrów ekstrakcji)
6. **Materiały:** tylko nazwa→ID (brak wymiarów / edycji / importu biblioteki)
7. **Klienci:** zero (1 rekord w bazie)
8. **Typy drzwi:** tylko listowanie (35); brak tworzenia / edycji / importu
9. **Ścieżki drzwi:** zero (34 toolpathy — serce frezowania frontów!)
10. **UserStyles:** zero (265!)
11. **Job files:** zero (AddFileToCDMJob)
12. **Procesowanie:** świadomie nie (Process* wisi w Session 0 — wymaga GUI)
13. **Pozostałe:** zlecenia obróbki (28), ToolOrderLists, Multidrill (0), wiercenie, okucia (1), mapowanie warstw, zmienne parametryczne (0), strefy nestingu, nazwy plików, extension data, CDM per-konfiguracja (4) — wszystko bez obsługi

---

## 19. Recepty/pułapki techniczne (sprawdzone na żywej maszynie)

- `GetAutomationManagerAddInGUI()` zamiast `GetAutomationManagerAddIn()` (bezparametrowe **WISI** w Session 0); CLSID addins `{39BFE38A-D3E4-43EA-89D0-584C776B97A9}` + `GetAddInsInterface(app)` — uniwersalna brama do wszystkich addinów
- `ImportCSVToJob`, `CreateJobsFromCSVFile`, `ImportCDM*` — wymagają UserInteractive (dialogi) — w Session 0 wiszą lub rzucają; **własny parser + NewCDMJob/AddCDMOrderDetail = droga headless**
- `Process*` (ProcessFile/JobFile/MultiProcJobs) — **GUI tylko**
- `DeleteFromDB` na świeżym obiekcie z NewCDMJob = cichy no-op; na obiekcie z kolekcji am.Jobs działa (po no-op); kolekcja `am.Jobs` **STĘCHŁA** po usunięciu — weryfikacja tylko przez VistaDB (scripts/vdb5_job_count.ps1)
- VistaDB: `[fkMaterialID]` — **MATERIAL to keyword**; UPDATE po JobDetailID (nie po nazwie); schemat DBO; PowerShell + VistaDB.5.NET40.dll; odczyt przez `GetSchema('Tables'/'Columns')`
- reg copy `HKCU\SOFTWARE\Hexagon` → `HKU\.DEFAULT\SOFTWARE\Hexagon` po zmianach ustawień w GUI + restart usługi (Session 0 = LocalSystem)
- `str()` na obiektach COM wywołuje default method → **zawsze `repr()`**
- Po probe: `taskkill /F /IM Acam.exe` przed restartem usługi
- Zapisywanie plików ps1 na maszynie: `$input | Out-File` przez stdin SSH (cmd niszczy quoting)

---

## 20. Co można wdrożyć — mapa wdrożeniowa Przemysł 4.0 (fazy)

### Faza 1 — Produkcja (import pełny, szybkie zyski)

- `cdm import` z mapowaniem pól z AM_ImportSettings (odczyt mapy z bazy; obsługa kolumn 7-8: klient / nr zamówienia; wybór ustawienia `--import-setting N`)
- Nowe pola OrderDetails w import: CSV_CustomerName, CSV_OrderNumber, CSV_ItemNumber, ProductionComment, OversizeX/Y, CornerRadius, RotationMethod/Angle, NestingPriority, IgnoreOuterGeometry, SmallNestPart, HasDrilling, CDMCustomField1..25 (przez kolumny mapowania)
- `cdm import --preview CSV` (sucho — pokaż co zostanie zaimportowane)

### Faza 2 — Audyt/podgląd (komendy read)

- `cdm order-details list JOB` (pełne pola: Press, Colour, Handle, custom, oversize, drilling)
- `cdm doorpaths list [TYPE]` (34 toolpathy: narzędzia, prędkości, głębokości, lead-in/out)
- `cdm materials list` (wymiary arkuszy)
- `cdm config list/show` (NC/raporty/nesting per konfiguracja)
- `cdm setups list`
- `cdm customers list`
- `cdm importsettings list`
- `cdm machining-orders list`
- `cdm doorstyles list` (265 UserStyles)
- `cdm multidrill list`
- `cdm fittings list`
- `cdm layers-mapping list`

### Faza 3 — Zarządzanie (write)

- `cdm config update` (PostProcessor, NC/raport katalogi, GenerateNC, GenerateReports, flagi nestingu)
- `cdm materials add/update`
- `cdm customers add/update`
- `cdm door-types add/update`
- `cdm job-files add JOB PLIK` (AddFileToCDMJob — rysunki .ard do pozycji)
- `cdm order-details update JOB ID --field value` (edycja dowolnego pola po mapie typów 256-299)
- `cdm delete` rozszerzony o `--details` (usuwanie pozycji)

### Faza 4 — Pełna automatyzacja (I4.0)

- **Pipeline headless:** CSV (ERP/WooCommerce) → `cdm import` (joby+pozycje+pliki) → weryfikacja → procesowanie przez sesję GUI użytkownika (schtasks /it — bo Process* wymaga GUI) → NC + raporty
- **Integracja z ERP:** pisanie/odczyt bazy VistaDB bezpośrednio (klienci, materiały, zamówienia) — wzorzec scripts/vdb5_*.ps1
- **Raporty produkcyjne:** powiązanie Reports_* z konfiguracji z komendą `reports create`
- **Monitoring:** GenerateProcessingLogs, LogFileLocation, logi gateway (Session 0), statusy jobów (ActiveInProcess)
- **Jakość/diagnostyka:** weryfikacja poprawności joba przed procesowaniem (pola wymagane: materiał, setup, tool order, ścieżki drzwi)
- `cdm audit JOB` — raport kompletności (brakujące materiały/setupy/ścieżki/pliki) przed wysłaniem na maszynę

---

## 21. Rekomendacje priorytetowe

| Priorytet | Pozycja | Uzasadnienie | Faza |
|---|---|---|---|
| P1 | Import z mapowaniem AM_ImportSettings + klient/nr zamówienia | zgodność z konfiguracją GUI "sklep CSV"; pełny zapis danych zamówienia | 1 |
| P1 | `cdm import --preview` | sucho przed realnym importem — kontrola jakości | 1 |
| P2 | `cdm order-details list` | weryfikacja joba przed produkcją | 2 |
| P2 | `cdm doorpaths list` | audyt toolpathów (34) — serce frezowania | 2 |
| P3 | `cdm materials list` | wymiary arkuszy do planowania nestingu | 2 |
| P3 | `cdm config show/update` | konfiguracja wyjść NC/raportów per konfiguracja | 2-3 |
| P4 | `cdm job-files add` | dołączanie rysunków do pozycji (produkcja frontów nietypowych) | 3 |
| P4 | `cdm order-details update --field` | edycja pól po mapie typów | 3 |
| P5 | Pipeline ERP→joby→procesowanie→NC | pełna automatyzacja I4.0 | 4 |
| P5 | `cdm audit JOB` | brama jakości przed maszyną | 4 |

---

## 22. Załącznik: aktualne dane z bazy (2026-08-09)

- **ImportSettings:** 3 "sklep CSV" (Selected, CreateJob), 4 "Ustawienia Importu CSV 2"
- **Ilości rekordów:** CDM_DoorTypes=35, CDM_DoorPaths=34, CDM_UserStyles=265, AM_JobFileDetails=0, AM_CustomerDetails=1, AM_MachiningOrder=28, AM_Fittings=1, AM_Multidrill=0, AM_ParametricVariables=0
- **Konfiguracje:** 1 "Not Selected", 40 "CDM_Materiał 17mm", 41 "Fronty" (aktywna, cfg=41, setup=1, tool=1)
- **Materiały:** 4 (2070x2800x19 / 2440x1220x19 / 96x48x0.75)
- **CDM_ConfigurationSettings:** 4 rekordy (cfg 40×2, 41×2; wszystkie DisableNesting=False, UseDefaultPress=False, GenerateNCForParts=False, CaptureNestedPartPositions=False)

---

> Raport wygenerowany z audytu bazy VistaDB + typelib AcamAddIns na żywej maszynie (laptop-monika, AlphaCAM 2025 Router), 2026-08-09.
