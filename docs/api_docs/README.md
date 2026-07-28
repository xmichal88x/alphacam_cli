# AlphaCAM API Documentation - Podzielona dokumentacja

Dokumentacja została podzielona na kategorie, aby agent mógł szybko znajdować odpowiednie funkcje API.

## Struktura katalogów

```
API_Docs_Split/
├── 01_Events/                    # Zdarzenia (Before/After)
│   ├── Common_Events.txt          # Zdarzenia wspólne (BeforeClose, AfterOpenFile, etc.)
│   ├── Lathe_Events.txt          # Zdarzenia dla tokarek
│   ├── Mill_Router_Events.txt   # Zdarzenia dla frezarek/ploterów
│   ├── Laser_Flame_Events.txt   # Zdarzenia dla laser/plazma
│   └── Wire_Events.txt           # Zdarzenia dla cięcia drutem
│
├── 02_Application/              # Metody obiektu Application
│   ├── Common_Methods.txt        # OpenDrawing, SelectTool, Run, New, Quit
│   ├── Lathe_Methods.txt        # SelectToolInLatheTurret, GetCurrentToolInLatheTurret
│   ├── Mill_Methods.txt         # CreateMillData, CreateMillStyle
│   ├── Laser_Methods.txt        # CreateLaserData
│   └── Wire_Methods.txt         # CreateWireData
│
├── 03_Application_Properties.txt  # Właściwości Application
│
├── 04_Drawing/                  # Metody i właściwości Drawing
│   ├── Drawing_Methods.txt
│   └── Drawing_Properties.txt
│
├── 05_Geometry/                # Geometria
│   ├── Geometry_Methods.txt
│   └── Geometry_Properties.txt
│
├── 06_Tools/                   # Narzędzia
│   ├── MillTool.txt
│   └── LatheTool.txt
│
├── 07_Machining/               # Obróbka - NAJWAŻNIEJSZE
│   ├── MillData.txt            # RoughFinish, DrillTap, Pocket, Engrave, Saw
│   ├── TurnData.txt            # Obróbka tokarska
│   ├── LaserData.txt           # CutPath, ClearArea, CutHoles, CutPolylines
│   ├── WireData.txt            # Cut2AxisShape, Cut4AxisShape
│   └── LeadData.txt            # Lead-In/Out
│
├── 08_Styles/                   # Style obróbki
│   └── MillStyle.txt
│
├── 09_PostProcessor.txt         # Postprocesor
│
└── 10_Utilities/                # Narzędzia
    ├── Utilities.txt
    └── Other.txt
```

## Jak szukać

### Szukasz jak wyciąć otwory na frezarce?
→ `07_Machining/MillData.txt` → szukaj "DrillTap" lub "CutHoles"

### Szukasz jak wyciąć kontur na laserze?
→ `07_Machining/LaserData.txt` → szukaj "CutPath"

### Szukasz jak wyciąć drutem?
→ `07_Machining/WireData.txt` → szukaj "Cut2AxisShape"

### Szukasz zdarzenia przed otwarciem pliku?
→ `01_Events/Common_Events.txt` → szukaj "BeforeOpenFile"

### Szukasz jak wybrać narzędzie?
→ `02_Application/Common_Methods.txt` → szukaj "SelectTool"

### Szukasz właściwości narzędzia?
→ `06_Tools/MillTool.txt` → szukaj właściwości (Diameter, Length, etc.)

## Typy maszyn

Dokumentacja zawiera oznaczenia dla różnych typów maszyn:
- **(Lathe only)** - Tylko dla tokarek
- **(Mill/Router only)** - Tylko dla frezarek/ploterów
- **(Laser/Flame only)** - Tylko dla laser/plazma
- **(Wire only)** - Tylko dla cięcia drutem
- **(Mill and Turn only)** - Dla frezarko-tokarek

## Wspólne dla wszystkich typów

Niektóre funkcje są wspólne dla wszystkich typów maszyn i znajdują się w katalogach "Common".
