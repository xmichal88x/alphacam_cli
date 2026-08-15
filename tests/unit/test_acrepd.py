from __future__ import annotations

import os
import pathlib
import textwrap
from typing import Any

import pytest

from alphacam_cli.core import acrepd

_MANIFEST_ROWS = """\
  <AC_02_JOB>
    <JobName>Fronty</JobName>
    <JobCustomerName>Klient A</JobCustomerName>
    <JobMaterial_AutomationManager>MDF_18</JobMaterial_AutomationManager>
    <JobPO>PO-001</JobPO>
    <JobDueDate>2026-08-10</JobDueDate>
    <JobOrderDate>2026-08-01</JobOrderDate>
    <JobProcessedDate>2026-08-10</JobProcessedDate>
    <JobEfficiencyRatePercentage>92.5</JobEfficiencyRatePercentage>
  </AC_02_JOB>
  <AC_03_DRAWINGS>
    <DrawingID>1</DrawingID>
    <DrawingName>Fronty - rys</DrawingName>
    <DrawingFileName>Fronty.amd</DrawingFileName>
  </AC_03_DRAWINGS>
  <AC_04_SHEETS>
    <SheetID>1</SheetID>
    <SheetName>Arkusz A1</SheetName>
    <SheetDatabaseName>MDF_18</SheetDatabaseName>
    <SheetWidth>2800</SheetWidth>
    <SheetLength>2070</SheetLength>
    <SheetThickness>18</SheetThickness>
    <SheetPartCount>2</SheetPartCount>
    <SheetUniquePartCount>2</SheetUniquePartCount>
    <SheetQuantity>1</SheetQuantity>
    <SheetScrap>71</SheetScrap>
    <SheetImage>img1</SheetImage>
  </AC_04_SHEETS>
  <AC_04_SHEETS>
    <SheetID>2</SheetID>
    <SheetName>Arkusz A2</SheetName>
    <SheetDatabaseName>MDF_18</SheetDatabaseName>
    <SheetWidth>2800</SheetWidth>
    <SheetLength>2070</SheetLength>
    <SheetThickness>18</SheetThickness>
    <SheetPartCount>1</SheetPartCount>
    <SheetUniquePartCount>1</SheetUniquePartCount>
    <SheetQuantity>1</SheetQuantity>
  </AC_04_SHEETS>
  <AC_05_PARTS>
    <PartID>1</PartID>
    <PartSheetID>1</PartSheetID>
    <PartDrawingID>1</PartDrawingID>
    <PartJobID>1</PartJobID>
    <PartName>PF-002Small_4</PartName>
    <PartDrawingFileName>a.amd</PartDrawingFileName>
    <PartItemNumber>1</PartItemNumber>
    <PartQuantity>1</PartQuantity>
    <PartQuantityOnSheet>7</PartQuantityOnSheet>
    <PartLocationOnSheetX>79.0</PartLocationOnSheetX>
    <PartLocationOnSheetY>613.0</PartLocationOnSheetY>
    <PartRotationOnSheet>90</PartRotationOnSheet>
    <PartWidth>500</PartWidth>
    <PartLength>600</PartLength>
    <PartThickness>18</PartThickness>
    <PartMaterial>MDF_18</PartMaterial>
    <PartNestKitNumber>3</PartNestKitNumber>
  </AC_05_PARTS>
  <AC_05_PARTS>
    <PartID>2</PartID>
    <PartSheetID>1</PartSheetID>
    <PartName>PF-003</PartName>
    <PartQuantityOnSheet>2</PartQuantityOnSheet>
    <PartLocationOnSheetX>10.5</PartLocationOnSheetX>
    <PartLocationOnSheetY>20.25</PartLocationOnSheetY>
    <PartRotationOnSheet>0</PartRotationOnSheet>
  </AC_05_PARTS>
  <AC_05_PARTS>
    <PartID>3</PartID>
    <PartSheetID>2</PartSheetID>
    <PartName>PF-004</PartName>
    <PartQuantityOnSheet>1</PartQuantityOnSheet>
    <PartLocationOnSheetX>5.5</PartLocationOnSheetX>
    <PartLocationOnSheetY>6.75</PartLocationOnSheetY>
    <PartRotationOnSheet>0</PartRotationOnSheet>
  </AC_05_PARTS>
  <AC_SHEET_CDM>
    <CDMSheetNestNCFileName>Fronty - MDF_18_s1.nc</CDMSheetNestNCFileName>
    <CDMSheetPressName>PRESS-1</CDMSheetPressName>
  </AC_SHEET_CDM>
  <AC_SHEET_CDM>
    <CDMSheetNestNCFileName>Fronty - MDF_18_s2.nc</CDMSheetNestNCFileName>
    <CDMSheetPressName>PRESS-2</CDMSheetPressName>
  </AC_SHEET_CDM>
  <AC_PART_CDM>
    <CDMPartType>P003</CDMPartType>
    <CDMPartHandleName>H-001</CDMPartHandleName>
    <CDMPartCSVCustomerName>Klient A</CDMPartCSVCustomerName>
    <CDMPartCSVCustomerOrderNumber>Z-001</CDMPartCSVCustomerOrderNumber>
    <CDMPartCSVCustomerItemNumber>I-1</CDMPartCSVCustomerItemNumber>
    <CDMPartProductionComment>uwaga produkcyjna</CDMPartProductionComment>
    <CDMPartCustom1>CF1</CDMPartCustom1>
    <CDMPartCustom2>CF2</CDMPartCustom2>
    <CDMPartNestNCFilename>Fronty - MDF_18_p1.nc</CDMPartNestNCFilename>
    <CDMPartPressSheetName>PRESS-1</CDMPartPressSheetName>
  </AC_PART_CDM>
  <AC_PART_CDM>
    <CDMPartType>P003</CDMPartType>
    <CDMPartHandleName>H-002</CDMPartHandleName>
    <CDMPartCSVCustomerName>Klient B</CDMPartCSVCustomerName>
    <CDMPartCSVCustomerOrderNumber>Z-002</CDMPartCSVCustomerOrderNumber>
    <CDMPartCSVCustomerItemNumber>I-2</CDMPartCSVCustomerItemNumber>
    <CDMPartPressSheetName>PRESS-1</CDMPartPressSheetName>
  </AC_PART_CDM>
  <AC_PART_CDM>
    <CDMPartType>P003</CDMPartType>
    <CDMPartHandleName>H-003</CDMPartHandleName>
    <CDMPartCSVCustomerName>Klient C</CDMPartCSVCustomerName>
    <CDMPartCSVCustomerOrderNumber>Z-003</CDMPartCSVCustomerOrderNumber>
    <CDMPartCSVCustomerItemNumber>I-3</CDMPartCSVCustomerItemNumber>
    <CDMPartPressSheetName>PRESS-2</CDMPartPressSheetName>
  </AC_PART_CDM>
"""

_FULL_MANIFEST_XML = f"""\
<?xml version="1.0" encoding="utf-8"?>
<NewDataSet xmlns:msdata="urn:schemas-microsoft-com:xml-msdata">
  <xs:schema id="NewDataSet" xmlns:xs="http://www.w3.org/2001/XMLSchema"
    xmlns:msdata="urn:schemas-microsoft-com:xml-msdata">
    <xs:element name="NewDataSet" msdata:IsDataSet="true">
      <xs:complexType>
        <xs:choice maxOccurs="unbounded">
          <xs:element name="AC_02_JOB" minOccurs="0">
            <xs:complexType>
              <xs:sequence>
                <xs:element name="JobName" type="xs:string" minOccurs="0" />
              </xs:sequence>
            </xs:complexType>
          </xs:element>
        </xs:choice>
      </xs:complexType>
    </xs:element>
  </xs:schema>
{_MANIFEST_ROWS}
</NewDataSet>
"""

_DIFFGRAM_MANIFEST_XML = f"""\
<?xml version="1.0" encoding="utf-8"?>
<NewDataSet xmlns:diffgr="urn:schemas-microsoft-com:xml-diffgram-v1"
  xmlns:msdata="urn:schemas-microsoft-com:xml-msdata">
  <xs:schema id="NewDataSet" xmlns:xs="http://www.w3.org/2001/XMLSchema"
    xmlns:msdata="urn:schemas-microsoft-com:xml-msdata">
    <xs:element name="NewDataSet" msdata:IsDataSet="true">
      <xs:complexType>
        <xs:choice maxOccurs="unbounded">
          <xs:element name="AC_02_JOB" minOccurs="0">
            <xs:complexType>
              <xs:sequence>
                <xs:element name="JobName" type="xs:string" minOccurs="0" />
              </xs:sequence>
            </xs:complexType>
          </xs:element>
        </xs:choice>
      </xs:complexType>
    </xs:element>
  </xs:schema>
  <diffgr:diffgram diffgr:hasChanges="inserted">
{textwrap.indent(_MANIFEST_ROWS, "  ")}
  </diffgr:diffgram>
</NewDataSet>
"""

_DIFFGRAM_WRAPPER_MANIFEST_XML = f"""\
<?xml version="1.0" encoding="utf-8"?>
<NewDataSet xmlns:diffgr="urn:schemas-microsoft-com:xml-diffgram-v1"
  xmlns:msdata="urn:schemas-microsoft-com:xml-msdata">
  <xs:schema id="NewDataSet" xmlns:xs="http://www.w3.org/2001/XMLSchema"
    xmlns:msdata="urn:schemas-microsoft-com:xml-msdata">
    <xs:element name="NewDataSet" msdata:IsDataSet="true">
      <xs:complexType>
        <xs:choice maxOccurs="unbounded">
          <xs:element name="AC_02_JOB" minOccurs="0">
            <xs:complexType>
              <xs:sequence>
                <xs:element name="JobName" type="xs:string" minOccurs="0" />
              </xs:sequence>
            </xs:complexType>
          </xs:element>
        </xs:choice>
      </xs:complexType>
    </xs:element>
  </xs:schema>
  <diffgr:diffgram diffgr:hasChanges="inserted">
    <NewDataSet>
{textwrap.indent(_MANIFEST_ROWS, "      ")}
    </NewDataSet>
  </diffgr:diffgram>
</NewDataSet>
"""

_DIFFGRAM_MODIFIED_MANIFEST_XML = f"""\
<?xml version="1.0" encoding="utf-8"?>
<NewDataSet xmlns:diffgr="urn:schemas-microsoft-com:xml-diffgram-v1"
  xmlns:msdata="urn:schemas-microsoft-com:xml-msdata">
  <xs:schema id="NewDataSet" xmlns:xs="http://www.w3.org/2001/XMLSchema"
    xmlns:msdata="urn:schemas-microsoft-com:xml-msdata">
    <xs:element name="NewDataSet" msdata:IsDataSet="true">
      <xs:complexType>
        <xs:choice maxOccurs="unbounded">
          <xs:element name="AC_02_JOB" minOccurs="0">
            <xs:complexType>
              <xs:sequence>
                <xs:element name="JobName" type="xs:string" minOccurs="0" />
              </xs:sequence>
            </xs:complexType>
          </xs:element>
        </xs:choice>
      </xs:complexType>
    </xs:element>
  </xs:schema>
  <diffgr:diffgram diffgr:hasChanges="modified">
{textwrap.indent(_MANIFEST_ROWS, "    ")}
    <diffgr:before>
      <AC_05_PARTS>
        <PartID>9</PartID>
        <PartSheetID>1</PartSheetID>
        <PartName>PF-STALE-BEFORE</PartName>
      </AC_05_PARTS>
    </diffgr:before>
    <diffgr:after>
      <AC_05_PARTS>
        <PartID>10</PartID>
        <PartSheetID>1</PartSheetID>
        <PartName>PF-STALE-AFTER</PartName>
      </AC_05_PARTS>
      <AC_04_SHEETS>
        <SheetID>99</SheetID>
        <SheetName>Arkusz PO</SheetName>
      </AC_04_SHEETS>
    </diffgr:after>
  </diffgr:diffgram>
</NewDataSet>
"""

_SCHEMA_ONLY_XML = """\
<?xml version="1.0" encoding="utf-8"?>
<NewDataSet>
  <xs:schema id="NewDataSet" xmlns:xs="http://www.w3.org/2001/XMLSchema">
    <xs:element name="AC_02_JOB" type="xs:string" />
    <xs:element name="AC_05_PARTS" type="xs:string" />
  </xs:schema>
</NewDataSet>
"""

_CDM_BY_ID_MANIFEST_XML = (
    _FULL_MANIFEST_XML.replace(
        "<CDMSheetNestNCFileName>Fronty - MDF_18_s1.nc</CDMSheetNestNCFileName>",
        "<CDMSheetReportID>2</CDMSheetReportID>\n"
        "    <CDMSheetNestNCFileName>Fronty - MDF_18_s1.nc</CDMSheetNestNCFileName>",
    )
    .replace(
        "<CDMSheetNestNCFileName>Fronty - MDF_18_s2.nc</CDMSheetNestNCFileName>",
        "<CDMSheetReportID>1</CDMSheetReportID>\n"
        "    <CDMSheetNestNCFileName>Fronty - MDF_18_s2.nc</CDMSheetNestNCFileName>",
    )
    .replace(
        "<CDMPartHandleName>H-001</CDMPartHandleName>",
        "<CDMPartReportID>2</CDMPartReportID>\n    <CDMPartHandleName>H-001</CDMPartHandleName>",
    )
    .replace(
        "<CDMPartHandleName>H-002</CDMPartHandleName>",
        "<CDMPartReportID>1</CDMPartReportID>\n    <CDMPartHandleName>H-002</CDMPartHandleName>",
    )
    .replace(
        "<CDMPartHandleName>H-003</CDMPartHandleName>",
        "<CDMPartReportID>3</CDMPartReportID>\n    <CDMPartHandleName>H-003</CDMPartHandleName>",
    )
)

_CDM_ZERO_MATCH_MANIFEST_XML = _FULL_MANIFEST_XML.replace(
    "<CDMPartHandleName>H-001</CDMPartHandleName>",
    "<CDMPartReportID>999</CDMPartReportID>\n    <CDMPartHandleName>H-001</CDMPartHandleName>",
).replace(
    "<CDMPartHandleName>H-002</CDMPartHandleName>",
    "<CDMPartReportID>1000</CDMPartReportID>\n    <CDMPartHandleName>H-002</CDMPartHandleName>",
)

_CDM_DUPLICATE_ID_MANIFEST_XML = _FULL_MANIFEST_XML.replace(
    """  <AC_PART_CDM>
    <CDMPartType>P003</CDMPartType>
    <CDMPartHandleName>H-001</CDMPartHandleName>
    <CDMPartCSVCustomerName>Klient A</CDMPartCSVCustomerName>
    <CDMPartCSVCustomerOrderNumber>Z-001</CDMPartCSVCustomerOrderNumber>
    <CDMPartCSVCustomerItemNumber>I-1</CDMPartCSVCustomerItemNumber>
    <CDMPartProductionComment>uwaga produkcyjna</CDMPartProductionComment>
    <CDMPartCustom1>CF1</CDMPartCustom1>
    <CDMPartCustom2>CF2</CDMPartCustom2>
    <CDMPartNestNCFilename>Fronty - MDF_18_p1.nc</CDMPartNestNCFilename>
    <CDMPartPressSheetName>PRESS-1</CDMPartPressSheetName>
  </AC_PART_CDM>
  <AC_PART_CDM>
    <CDMPartType>P003</CDMPartType>
    <CDMPartHandleName>H-002</CDMPartHandleName>
    <CDMPartCSVCustomerName>Klient B</CDMPartCSVCustomerName>
    <CDMPartCSVCustomerOrderNumber>Z-002</CDMPartCSVCustomerOrderNumber>
    <CDMPartCSVCustomerItemNumber>I-2</CDMPartCSVCustomerItemNumber>
    <CDMPartPressSheetName>PRESS-1</CDMPartPressSheetName>
  </AC_PART_CDM>
  <AC_PART_CDM>
    <CDMPartType>P003</CDMPartType>
    <CDMPartHandleName>H-003</CDMPartHandleName>
    <CDMPartCSVCustomerName>Klient C</CDMPartCSVCustomerName>
    <CDMPartCSVCustomerOrderNumber>Z-003</CDMPartCSVCustomerOrderNumber>
    <CDMPartCSVCustomerItemNumber>I-3</CDMPartCSVCustomerItemNumber>
    <CDMPartPressSheetName>PRESS-2</CDMPartPressSheetName>
  </AC_PART_CDM>""",
    """  <AC_PART_CDM>
    <CDMPartReportID>1</CDMPartReportID>
    <CDMPartHandleName>HANDLE-A</CDMPartHandleName>
    <CDMPartCSVCustomerName>Klient A</CDMPartCSVCustomerName>
    <CDMPartCSVCustomerOrderNumber>Z-001</CDMPartCSVCustomerOrderNumber>
    <CDMPartCSVCustomerItemNumber>I-1</CDMPartCSVCustomerItemNumber>
    <CDMPartPressSheetName>PRESS-1</CDMPartPressSheetName>
  </AC_PART_CDM>
  <AC_PART_CDM>
    <CDMPartReportID>1</CDMPartReportID>
    <CDMPartCSVCustomerOrderNumber>Z-ORDER-B</CDMPartCSVCustomerOrderNumber>
  </AC_PART_CDM>""",
)


_UNMATCHED_MANIFEST_XML = _FULL_MANIFEST_XML.replace(
    "<PartSheetID>2</PartSheetID>", "<PartSheetID>99</PartSheetID>"
)


@pytest.fixture
def manifest_file(tmp_path: pathlib.Path) -> pathlib.Path:
    path = tmp_path / "Fronty - MDF_18.acrepd"
    path.write_text(_FULL_MANIFEST_XML, encoding="utf-8")
    return path


@pytest.fixture
def manifest_diffgram_file(tmp_path: pathlib.Path) -> pathlib.Path:
    path = tmp_path / "Fronty - MDF_18.acrepd"
    path.write_text(_DIFFGRAM_MANIFEST_XML, encoding="utf-8")
    return path


@pytest.fixture
def manifest_diffgram_wrapper_file(tmp_path: pathlib.Path) -> pathlib.Path:
    path = tmp_path / "Fronty - MDF_18.acrepd"
    path.write_text(_DIFFGRAM_WRAPPER_MANIFEST_XML, encoding="utf-8")
    return path


def test_parse_manifest_full(manifest_file: pathlib.Path) -> None:
    manifest = acrepd.parse_manifest(str(manifest_file))

    assert manifest["job_name"] == "Fronty"
    assert manifest["material"] == "MDF_18"
    assert manifest["path"] == str(manifest_file)

    assert manifest["job"]["job_name"] == "Fronty"
    assert manifest["job"]["customer_name"] == "Klient A"
    assert manifest["job"]["material"] == "MDF_18"
    assert manifest["job"]["po_number"] == "PO-001"
    assert manifest["job"]["due_date"] == "2026-08-10"
    assert manifest["job"]["order_date"] == "2026-08-01"
    assert manifest["job"]["processed_date"] == "2026-08-10"
    assert manifest["job"]["efficiency_rate"] == "92.5"

    assert manifest["drawings"] == [{"name": "Fronty - rys", "file_name": "Fronty.amd"}]

    sheets = manifest["sheets"]
    assert len(sheets) == 2
    s1 = sheets[0]
    assert s1["id"] == 1
    assert s1["name"] == "Arkusz A1"
    assert s1["database_name"] == "MDF_18"
    assert s1["width"] == 2800.0
    assert s1["length"] == 2070.0
    assert s1["thickness"] == 18.0
    assert s1["part_count"] == 2
    assert s1["unique_part_count"] == 2
    assert s1["quantity"] == 1
    assert s1["scrap"] == 71
    assert s1["utilization"] == 29
    assert s1["has_image"] is True
    assert s1["nest_nc_filename"] == "Fronty - MDF_18_s1.nc"
    assert s1["press_name"] == "PRESS-1"
    s2 = sheets[1]
    assert s2["id"] == 2
    assert s2["name"] == "Arkusz A2"
    assert s2["database_name"] == "MDF_18"
    assert s2["width"] == 2800.0
    assert s2["scrap"] is None
    assert s2["utilization"] is None
    assert s2["has_image"] is False
    assert s2["nest_nc_filename"] == "Fronty - MDF_18_s2.nc"
    assert s2["press_name"] == "PRESS-2"

    assert manifest["total_parts"] == 3
    assert manifest["unmatched_parts"] == []
    assert len(s1["parts"]) == 2
    assert len(s2["parts"]) == 1

    p1 = s1["parts"][0]
    assert p1["sheet_id"] == 1
    assert p1["name"] == "PF-002Small_4"
    assert p1["drawing_file_name"] == "a.amd"
    assert p1["item_number"] == "1"
    assert p1["quantity"] == 1
    assert p1["quantity_on_sheet"] == 7
    assert p1["x"] == 79.0
    assert p1["y"] == 613.0
    assert p1["rotation"] == 90
    assert p1["width"] == 500.0
    assert p1["length"] == 600.0
    assert p1["thickness"] == 18.0
    assert p1["material"] == "MDF_18"
    assert p1["nest_kit_number"] == "3"
    assert p1["has_image"] is False
    assert p1["type"] == "P003"
    assert p1["handle_name"] == "H-001"
    assert p1["csv_customer_name"] == "Klient A"
    assert p1["csv_order_number"] == "Z-001"
    assert p1["csv_item_number"] == "I-1"
    assert p1["production_comment"] == "uwaga produkcyjna"
    assert p1["custom_field_1"] == "CF1"
    assert p1["custom_field_2"] == "CF2"
    assert p1["nest_nc_filename"] == "Fronty - MDF_18_p1.nc"
    assert p1["press_sheet_name"] == "PRESS-1"

    p2 = s1["parts"][1]
    assert p2["name"] == "PF-003"
    assert p2["x"] == 10.5
    assert p2["y"] == 20.25
    assert p2["quantity_on_sheet"] == 2
    assert p2["type"] == "P003"
    assert p2["handle_name"] == "H-002"
    assert p2["csv_order_number"] == "Z-002"
    assert p2["csv_item_number"] == "I-2"

    p3 = s2["parts"][0]
    assert p3["name"] == "PF-004"
    assert p3["sheet_id"] == 2
    assert p3["x"] == 5.5
    assert p3["y"] == 6.75
    assert p3["type"] == "P003"
    assert p3["handle_name"] == "H-003"
    assert p3["csv_customer_name"] == "Klient C"
    assert p3["csv_order_number"] == "Z-003"
    assert p3["csv_item_number"] == "I-3"


def test_parse_manifest_sheet_scrap_zero(tmp_path: pathlib.Path) -> None:
    path = tmp_path / "Fronty - MDF_18.acrepd"
    path.write_text(
        _FULL_MANIFEST_XML.replace("<SheetScrap>71</SheetScrap>", "<SheetScrap>0</SheetScrap>"),
        encoding="utf-8",
    )
    manifest = acrepd.parse_manifest(str(path))

    s1 = manifest["sheets"][0]
    assert s1["scrap"] == 0
    assert s1["utilization"] == 100
    assert manifest["sheets"][1]["scrap"] is None
    assert manifest["sheets"][1]["utilization"] is None


def test_parse_manifest_unmatched_parts_list(tmp_path: pathlib.Path) -> None:
    path = tmp_path / "Fronty - MDF_18.acrepd"
    path.write_text(_UNMATCHED_MANIFEST_XML, encoding="utf-8")
    manifest = acrepd.parse_manifest(str(path))

    assert manifest["total_parts"] == 3
    assert len(manifest["sheets"][1]["parts"]) == 0

    unmatched = manifest["unmatched_parts"]
    assert len(unmatched) == 1
    assert unmatched[0]["id"] == 3
    assert unmatched[0]["sheet_id"] == 99
    assert unmatched[0]["name"] == "PF-004"
    assert unmatched[0]["x"] == 5.5
    assert unmatched[0]["quantity_on_sheet"] == 1
    assert unmatched[0]["handle_name"] == "H-003"
    assert unmatched[0]["csv_customer_name"] == "Klient C"


def test_parse_manifest_cdm_by_id(tmp_path: pathlib.Path) -> None:
    path = tmp_path / "Fronty - MDF_18.acrepd"
    path.write_text(_CDM_BY_ID_MANIFEST_XML, encoding="utf-8")
    manifest = acrepd.parse_manifest(str(path))

    sheets = manifest["sheets"]
    assert sheets[0]["id"] == 1
    assert sheets[0]["nest_nc_filename"] == "Fronty - MDF_18_s2.nc"
    assert sheets[0]["press_name"] == "PRESS-2"
    assert sheets[1]["id"] == 2
    assert sheets[1]["nest_nc_filename"] == "Fronty - MDF_18_s1.nc"
    assert sheets[1]["press_name"] == "PRESS-1"

    p1 = sheets[0]["parts"][0]
    assert p1["id"] == 1
    assert p1["handle_name"] == "H-002"
    assert p1["csv_customer_name"] == "Klient B"
    assert p1["csv_order_number"] == "Z-002"
    assert p1["csv_item_number"] == "I-2"
    assert p1["press_sheet_name"] == "PRESS-1"

    p2 = sheets[0]["parts"][1]
    assert p2["id"] == 2
    assert p2["handle_name"] == "H-001"
    assert p2["csv_customer_name"] == "Klient A"
    assert p2["csv_order_number"] == "Z-001"
    assert p2["csv_item_number"] == "I-1"

    p3 = sheets[1]["parts"][0]
    assert p3["id"] == 3
    assert p3["handle_name"] == "H-003"
    assert p3["csv_order_number"] == "Z-003"


def test_parse_manifest_cdm_by_id_zero_match_fallback(
    tmp_path: pathlib.Path,
) -> None:
    path = tmp_path / "Fronty - MDF_18.acrepd"
    path.write_text(_CDM_ZERO_MATCH_MANIFEST_XML, encoding="utf-8")
    manifest = acrepd.parse_manifest(str(path))

    parts = [p for sheet in manifest["sheets"] for p in sheet["parts"]]
    assert [p["id"] for p in parts] == [1, 2, 3]
    assert parts[0]["handle_name"] == "H-001"
    assert parts[0]["csv_order_number"] == "Z-001"
    assert parts[1]["handle_name"] == "H-002"
    assert parts[1]["csv_order_number"] == "Z-002"
    assert parts[2]["handle_name"] == "H-003"
    assert parts[2]["csv_order_number"] == "Z-003"


def test_parse_manifest_cdm_duplicate_id_merge_not_none(
    tmp_path: pathlib.Path,
) -> None:
    path = tmp_path / "Fronty - MDF_18.acrepd"
    path.write_text(_CDM_DUPLICATE_ID_MANIFEST_XML, encoding="utf-8")
    manifest = acrepd.parse_manifest(str(path))

    parts = [p for sheet in manifest["sheets"] for p in sheet["parts"]]
    p1 = parts[0]
    assert p1["id"] == 1
    assert p1["handle_name"] == "HANDLE-A"
    assert p1["csv_customer_name"] == "Klient A"
    assert p1["csv_order_number"] == "Z-ORDER-B"
    assert p1["csv_item_number"] == "I-1"
    assert p1["press_sheet_name"] == "PRESS-1"
    assert parts[1]["handle_name"] is None
    assert parts[2]["handle_name"] is None


def test_parse_manifest_diffgram(manifest_diffgram_file: pathlib.Path) -> None:
    manifest = acrepd.parse_manifest(str(manifest_diffgram_file))

    assert manifest["job"]["job_name"] == "Fronty"
    assert len(manifest["sheets"]) == 2
    assert manifest["total_parts"] == 3


def test_parse_manifest_diffgram_wrapper(
    manifest_diffgram_wrapper_file: pathlib.Path,
) -> None:
    manifest = acrepd.parse_manifest(str(manifest_diffgram_wrapper_file))

    assert manifest["job"]["job_name"] == "Fronty"
    assert len(manifest["sheets"]) == 2
    assert manifest["total_parts"] == 3


def test_parse_manifest_diffgram_ignores_before_after_sections(
    tmp_path: pathlib.Path,
) -> None:
    path = tmp_path / "Fronty - MDF_18.acrepd"
    path.write_text(_DIFFGRAM_MODIFIED_MANIFEST_XML, encoding="utf-8")
    manifest = acrepd.parse_manifest(str(path))

    assert len(manifest["sheets"]) == 2
    assert manifest["total_parts"] == 3
    assert len(manifest["unmatched_parts"]) == 0
    part_names = [p["name"] for sheet in manifest["sheets"] for p in sheet["parts"]]
    assert part_names == ["PF-002Small_4", "PF-003", "PF-004"]


@pytest.mark.parametrize("xml", [_SCHEMA_ONLY_XML, "<NewDataSet />"])
def test_parse_manifest_empty_tables(tmp_path: pathlib.Path, xml: str) -> None:
    path = tmp_path / "empty.acrepd"
    path.write_text(xml, encoding="utf-8")
    manifest = acrepd.parse_manifest(str(path))
    assert manifest["job_name"] == "empty"
    assert manifest["material"] is None
    assert manifest["job"] == {
        "job_name": None,
        "customer_name": None,
        "material": None,
        "po_number": None,
        "due_date": None,
        "order_date": None,
        "processed_date": None,
        "efficiency_rate": None,
    }
    assert manifest["drawings"] == []
    assert manifest["sheets"] == []
    assert manifest["total_parts"] == 0
    assert manifest["unmatched_parts"] == []


def test_parse_manifest_invalid_xml(tmp_path: pathlib.Path) -> None:
    path = tmp_path / "broken.acrepd"
    path.write_text("<xs:schema><AC_02_JOB>", encoding="utf-8")
    with pytest.raises(RuntimeError, match="invalid XML"):
        acrepd.parse_manifest(str(path))


def test_parse_manifest_missing_file(tmp_path: pathlib.Path) -> None:
    with pytest.raises(FileNotFoundError):
        acrepd.parse_manifest(str(tmp_path / "nope.acrepd"))


def test_manifest_files(tmp_path: pathlib.Path) -> None:
    (tmp_path / "Fronty - MDF_18.acrepd").write_text("x" * 10, encoding="utf-8")
    (tmp_path / "Fronty - MDF_20.acrepd").write_text("y" * 20, encoding="utf-8")
    (tmp_path / "inny.txt").write_text("z", encoding="utf-8")

    manifests = acrepd.manifest_files(str(tmp_path))

    assert len(manifests) == 2
    assert manifests[0]["path"].endswith("Fronty - MDF_18.acrepd")
    assert manifests[0]["job_name"] == "Fronty"
    assert manifests[0]["material"] == "MDF_18"
    assert manifests[0]["size"] == 10
    assert isinstance(manifests[0]["mtime"], float)
    assert manifests[1]["path"].endswith("Fronty - MDF_20.acrepd")
    assert manifests[1]["job_name"] == "Fronty"
    assert manifests[1]["material"] == "MDF_20"
    assert manifests[1]["size"] == 20
    assert isinstance(manifests[1]["mtime"], float)


def test_sheet_count_light_full(manifest_file: pathlib.Path) -> None:
    assert acrepd.sheet_count_light(str(manifest_file)) == (2, 29)


def test_sheet_count_light_scrap_zero(tmp_path: pathlib.Path) -> None:
    path = tmp_path / "Fronty - MDF_18.acrepd"
    path.write_text(
        _FULL_MANIFEST_XML.replace("<SheetScrap>71</SheetScrap>", "<SheetScrap>0</SheetScrap>"),
        encoding="utf-8",
    )
    assert acrepd.sheet_count_light(str(path)) == (2, 100)


def test_sheet_count_light_scrap_non_numeric(tmp_path: pathlib.Path) -> None:
    path = tmp_path / "Fronty - MDF_18.acrepd"
    path.write_text(
        _FULL_MANIFEST_XML.replace("<SheetScrap>71</SheetScrap>", "<SheetScrap>abc</SheetScrap>"),
        encoding="utf-8",
    )
    assert acrepd.sheet_count_light(str(path)) == (2, None)


def test_sheet_count_light_missing_scrap(tmp_path: pathlib.Path) -> None:
    path = tmp_path / "Fronty - MDF_18.acrepd"
    path.write_text(_FULL_MANIFEST_XML.replace("<SheetScrap>71</SheetScrap>", ""), encoding="utf-8")
    assert acrepd.sheet_count_light(str(path)) == (2, None)


def test_sheet_count_light_namespaced(tmp_path: pathlib.Path) -> None:
    xml = """\
<?xml version="1.0" encoding="utf-8"?>
<NewDataSet xmlns="urn:schemas-microsoft-com:xml-vistadb">
  <AC_04_SHEETS>
    <SheetScrap>71</SheetScrap>
  </AC_04_SHEETS>
  <AC_04_SHEETS>
    <SheetScrap>12</SheetScrap>
  </AC_04_SHEETS>
</NewDataSet>
"""
    path = tmp_path / "namespaced.acrepd"
    path.write_text(xml, encoding="utf-8")
    assert acrepd.sheet_count_light(str(path)) == (2, 29)


def test_sheet_count_light_diffgram_skips_before_after(tmp_path: pathlib.Path) -> None:
    path = tmp_path / "Fronty - MDF_18.acrepd"
    path.write_text(_DIFFGRAM_MODIFIED_MANIFEST_XML, encoding="utf-8")
    assert acrepd.sheet_count_light(str(path)) == (2, 29)


def test_sheet_count_light_empty(tmp_path: pathlib.Path) -> None:
    path = tmp_path / "empty.acrepd"
    path.write_text("<NewDataSet />", encoding="utf-8")
    assert acrepd.sheet_count_light(str(path)) == (0, None)


def test_sheet_count_light_large_file_sheets_late(tmp_path: pathlib.Path) -> None:
    parts = "<AC_05_PARTS><PartID>1</PartID><PartName>P</PartName></AC_05_PARTS>\n" * 8000
    xml = (
        '<?xml version="1.0" encoding="utf-8"?>\n'
        "<NewDataSet>\n"
        "  <AC_02_JOB><JobName>X</JobName></AC_02_JOB>\n" + parts + "\n"
        "  <AC_04_SHEETS>\n"
        "    <SheetName>S1</SheetName>\n"
        "    <SheetScrap>70</SheetScrap>\n"
        "  </AC_04_SHEETS>\n"
        "  <AC_04_SHEETS>\n"
        "    <SheetName>S2</SheetName>\n"
        "  </AC_04_SHEETS>\n"
        "</NewDataSet>\n"
    )
    assert len(xml.encode("utf-8")) > 300_000
    path = tmp_path / "large.acrepd"
    path.write_text(xml, encoding="utf-8")
    assert acrepd.sheet_count_light(str(path)) == (2, 30)


def test_sheet_count_light_missing_file(
    tmp_path: pathlib.Path, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level("WARNING", logger="alphacam_cli.core.acrepd"):
        assert acrepd.sheet_count_light(str(tmp_path / "nope.acrepd")) == (0, None)
    assert "sheet_count_light failed" in caplog.text


def test_sheet_count_light_invalid_xml(tmp_path: pathlib.Path) -> None:
    path = tmp_path / "broken.acrepd"
    path.write_text("<xs:schema><AC_02_JOB>", encoding="utf-8")
    assert acrepd.sheet_count_light(str(path)) == (0, None)


def test_attach_sheet_cdm_partial_match_warns(caplog: pytest.LogCaptureFixture) -> None:
    sheets = [{"id": 1}, {"id": 2}]
    rows = [
        {"cdmsheetid": "1", "cdmsheetpressname": "PRESS-1"},
        {"cdmsheetid": "99", "cdmsheetpressname": "PRESS-X"},
    ]

    with caplog.at_level("WARNING", logger="alphacam_cli.core.acrepd"):
        acrepd._attach_sheet_cdm(sheets, rows)

    assert "acrepd: 1 of 2 CDM rows matched by cdmsheetid" in caplog.text
    assert sheets[0]["press_name"] == "PRESS-1"
    assert sheets[1].get("press_name") is None


def test_name_parts_splits_from_end(tmp_path: pathlib.Path) -> None:
    path = tmp_path / "Fronty - Dąb - MDF_18.acrepd"

    job_name, material = acrepd._name_parts(str(path))

    assert job_name == "Fronty - Dąb"
    assert material == "MDF_18"


def test_name_parts_without_separator(tmp_path: pathlib.Path) -> None:
    path = tmp_path / "Fronty.acrepd"

    job_name, material = acrepd._name_parts(str(path))

    assert job_name == "Fronty"
    assert material is None


def test_parse_manifest_too_large(tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = tmp_path / "big.acrepd"
    path.write_text(_FULL_MANIFEST_XML, encoding="utf-8")
    monkeypatch.setattr(acrepd, "_MAX_ACREPD_SIZE", 16)

    with pytest.raises(RuntimeError, match="file too large"):
        acrepd.parse_manifest(str(path))


def test_find_manifest(tmp_path: pathlib.Path) -> None:
    (tmp_path / "Fronty - MDF_18.acrepd").write_text("x", encoding="utf-8")
    (tmp_path / "Fronty - MDF_20.acrepd").write_text("y", encoding="utf-8")

    found = acrepd.find_manifest(str(tmp_path), "fronty", "mdf_18")
    assert found is not None
    assert found.endswith("Fronty - MDF_18.acrepd")

    assert acrepd.find_manifest(str(tmp_path), "fronty", "mdf_99") is None
    assert acrepd.find_manifest(str(tmp_path), "inne") is None

    first = acrepd.find_manifest(str(tmp_path), "fronty")
    assert first is not None
    assert first.endswith("Fronty - MDF_18.acrepd")


def test_reports_data_dir_override(tmp_path: pathlib.Path) -> None:
    assert acrepd._reports_data_dir(str(tmp_path), override="C:\\Custom") == "C:\\Custom"
    assert acrepd._reports_data_dir(str(tmp_path), override="   ") == str(
        tmp_path / "LICOMDIR" / "Reports" / "Data"
    )


def test_reports_data_dir_fallback_prefers_licomdir(tmp_path: pathlib.Path) -> None:
    (tmp_path / "LICOMDIR" / "Reports" / "Data").mkdir(parents=True)
    (tmp_path / "Reports" / "Data").mkdir(parents=True)
    assert acrepd._reports_data_dir(str(tmp_path)) == str(
        tmp_path / "LICOMDIR" / "Reports" / "Data"
    )


def test_reports_data_dir_fallback_plain(tmp_path: pathlib.Path) -> None:
    (tmp_path / "Reports" / "Data").mkdir(parents=True)
    assert acrepd._reports_data_dir(str(tmp_path)) == str(tmp_path / "Reports" / "Data")


def test_reports_data_dir_no_dirs_returns_first_candidate(tmp_path: pathlib.Path) -> None:
    assert acrepd._reports_data_dir(str(tmp_path)) == str(
        tmp_path / "LICOMDIR" / "Reports" / "Data"
    )


def _sheet(name: str) -> dict[str, object]:
    return {"id": 1, "name": name, "database_name": name, "parts": []}


def _nc(root: pathlib.Path, *parts: str) -> pathlib.Path:
    path = root.joinpath(*parts)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("x", encoding="utf-8")
    return path


def test_find_nc_files_sheet_stem_match(tmp_path: pathlib.Path) -> None:
    _nc(tmp_path, "Arkusz_A1.nc")
    result = acrepd.find_nc_files(
        str(tmp_path),
        [_sheet("Arkusz A1")],
        material="MDF_18",
        config={"replace_space_with_underscore": True},
    )

    assert result["nc_by_sheet"] == {
        0: {
            "nc_filename": "Arkusz_A1.nc",
            "nc_path": str(tmp_path / "Arkusz_A1.nc"),
            "nc_source": "disk",
        }
    }
    assert result["nc_matched_by_order"] == []
    assert result["nc_unmatched"] == []
    assert result["nc_missing"] == []


def test_find_nc_files_material_sheet_match_split_false(
    tmp_path: pathlib.Path,
) -> None:
    _nc(tmp_path, "MDF_18_MDF_18.nc")
    result = acrepd.find_nc_files(
        str(tmp_path),
        [_sheet("MDF_18")],
        material="MDF_18",
        config={
            "replace_space_with_underscore": True,
            "split_nested_sheet_drawings": False,
        },
    )

    assert result["nc_by_sheet"][0]["nc_filename"] == "MDF_18_MDF_18.nc"
    assert result["nc_missing"] == []
    assert result["nc_unmatched"] == []


def test_find_nc_files_sheet_material_reverse_match_try_all(
    tmp_path: pathlib.Path,
) -> None:
    _nc(tmp_path, "Arkusz_A1_MDF_18.nc")
    result = acrepd.find_nc_files(str(tmp_path), [_sheet("Arkusz A1")], material="MDF_18")

    assert result["nc_by_sheet"][0]["nc_filename"] == "Arkusz_A1_MDF_18.nc"
    assert result["nc_missing"] == []
    assert result["nc_unmatched"] == []


def test_find_nc_files_pattern_priority_prefers_plain_stem(
    tmp_path: pathlib.Path,
) -> None:
    _nc(tmp_path, "m_a.nc")
    _nc(tmp_path, "a.nc")
    result = acrepd.find_nc_files(str(tmp_path), [_sheet("a")], material="m")

    assert result["nc_by_sheet"][0]["nc_filename"] == "a.nc"
    assert result["nc_missing"] == []
    assert result["nc_unmatched"] == [str(tmp_path / "m_a.nc")]


def test_find_nc_files_pattern_priority_material_sheet_before_sheet_material(
    tmp_path: pathlib.Path,
) -> None:
    _nc(tmp_path, "a_m.nc")
    _nc(tmp_path, "m_a.nc")
    result = acrepd.find_nc_files(str(tmp_path), [_sheet("a")], material="m")

    assert result["nc_by_sheet"][0]["nc_filename"] == "m_a.nc"
    assert result["nc_missing"] == []
    assert result["nc_unmatched"] == [str(tmp_path / "a_m.nc")]


def test_find_nc_files_sheet_material_reverse_match_split_false(
    tmp_path: pathlib.Path,
) -> None:
    _nc(tmp_path, "Arkusz_A1_MDF_18.nc")
    result = acrepd.find_nc_files(
        str(tmp_path),
        [_sheet("Arkusz A1")],
        material="MDF_18",
        config={
            "replace_space_with_underscore": True,
            "split_nested_sheet_drawings": False,
        },
    )

    assert result["nc_by_sheet"][0]["nc_filename"] == "Arkusz_A1_MDF_18.nc"
    assert result["nc_missing"] == []
    assert result["nc_unmatched"] == []


def test_find_nc_files_split_false_unamed_sheets_keep_file_unmatched(
    tmp_path: pathlib.Path,
) -> None:
    _nc(tmp_path, "MDF_18_S1.nc")
    result = acrepd.find_nc_files(
        str(tmp_path),
        [_sheet(""), _sheet("")],
        material="MDF_18",
        config={
            "replace_space_with_underscore": True,
            "split_nested_sheet_drawings": False,
        },
    )

    assert result["nc_by_sheet"] == {}
    assert result["nc_unmatched"] == [str(tmp_path / "MDF_18_S1.nc")]


def test_find_nc_files_material_sheet_match_try_all(tmp_path: pathlib.Path) -> None:
    _nc(tmp_path, "MDF_18_MDF_18.nc")
    result = acrepd.find_nc_files(str(tmp_path), [_sheet("MDF_18")], material="MDF_18")

    assert result["nc_by_sheet"][0]["nc_filename"] == "MDF_18_MDF_18.nc"
    assert result["nc_missing"] == []
    assert result["nc_unmatched"] == []


def test_find_nc_files_order_fallback(tmp_path: pathlib.Path) -> None:
    _nc(tmp_path, "B.nc")
    _nc(tmp_path, "A.nc")
    result = acrepd.find_nc_files(str(tmp_path), [_sheet("X1"), _sheet("X2")])

    assert result["nc_by_sheet"][0]["nc_filename"] == "A.nc"
    assert result["nc_by_sheet"][1]["nc_filename"] == "B.nc"
    assert result["nc_matched_by_order"] == [0, 1]
    assert result["nc_missing"] == []
    assert result["nc_unmatched"] == []


def test_find_nc_files_missing_root(tmp_path: pathlib.Path) -> None:
    result = acrepd.find_nc_files(str(tmp_path / "nope"), [_sheet("X1"), _sheet("X2")])

    assert result["nc_by_sheet"] == {}
    assert result["nc_matched_by_order"] == []
    assert result["nc_unmatched"] == []
    assert result["nc_missing"] == ["X1", "X2"]


def test_find_nc_files_no_files(tmp_path: pathlib.Path) -> None:
    result = acrepd.find_nc_files(str(tmp_path), [_sheet("X1"), _sheet("X2")])

    assert result["nc_by_sheet"] == {}
    assert result["nc_matched_by_order"] == []
    assert result["nc_unmatched"] == []
    assert result["nc_missing"] == ["X1", "X2"]


def test_find_nc_files_unmatched_and_missing(tmp_path: pathlib.Path) -> None:
    _nc(tmp_path, "Arkusz_A1.nc")
    _nc(tmp_path, "Inny.nc")
    _nc(tmp_path, "Cos.nc")
    result = acrepd.find_nc_files(str(tmp_path), [_sheet("Arkusz A1"), _sheet("Arkusz A2")])

    assert result["nc_by_sheet"][0]["nc_filename"] == "Arkusz_A1.nc"
    assert result["nc_matched_by_order"] == []
    assert result["nc_unmatched"] == [
        str(tmp_path / "Cos.nc"),
        str(tmp_path / "Inny.nc"),
    ]
    assert result["nc_missing"] == ["Arkusz A2"]


def test_find_nc_files_prefers_token_dirs(tmp_path: pathlib.Path) -> None:
    _nc(tmp_path, "Arkusz_A1.nc")
    _nc(tmp_path, "nc", "Arkusz_A1.nc")
    _nc(tmp_path, "NESTING_out", "Arkusz_A2.nc")
    result = acrepd.find_nc_files(str(tmp_path), [_sheet("Arkusz A1"), _sheet("Arkusz A2")])

    assert result["nc_by_sheet"][0]["nc_path"] == str(tmp_path / "nc" / "Arkusz_A1.nc")
    assert result["nc_by_sheet"][1]["nc_path"] == str(tmp_path / "NESTING_out" / "Arkusz_A2.nc")
    assert result["nc_missing"] == []
    assert result["nc_unmatched"] == [str(tmp_path / "Arkusz_A1.nc")]


def test_find_nc_files_max_depth(tmp_path: pathlib.Path) -> None:
    _nc(tmp_path, "a", "b", "c", "d", "X.nc")
    _nc(tmp_path, "a", "b", "c", "d", "e", "Y.nc")
    result = acrepd.find_nc_files(str(tmp_path), [_sheet("X")])

    assert result["nc_by_sheet"][0]["nc_path"] == str(tmp_path / "a" / "b" / "c" / "d" / "X.nc")
    assert result["nc_missing"] == []
    assert result["nc_unmatched"] == []


def test_find_nc_files_name_identifiers_suffix(tmp_path: pathlib.Path) -> None:
    _nc(tmp_path, "Arkusz_A1_2.nc")
    result = acrepd.find_nc_files(
        str(tmp_path),
        [_sheet("Arkusz A1")],
        config={
            "replace_space_with_underscore": True,
            "split_nested_sheet_drawings": True,
            "use_name_identifiers": True,
        },
    )

    assert result["nc_by_sheet"][0]["nc_filename"] == "Arkusz_A1_2.nc"
    assert result["nc_missing"] == []
    assert result["nc_unmatched"] == []


def test_find_nc_files_replace_space_false(tmp_path: pathlib.Path) -> None:
    _nc(tmp_path, "Arkusz A1.nc")
    result = acrepd.find_nc_files(
        str(tmp_path),
        [_sheet("Arkusz A1")],
        config={"replace_space_with_underscore": False},
    )

    assert result["nc_by_sheet"][0]["nc_filename"] == "Arkusz A1.nc"
    assert result["nc_missing"] == []


def test_find_nc_files_config_none_values_match_default(tmp_path: pathlib.Path) -> None:
    _nc(tmp_path, "a.nc")
    _nc(tmp_path, "m_a.nc")
    result = acrepd.find_nc_files(
        str(tmp_path),
        [_sheet("a")],
        material="m",
        config={
            "replace_space_with_underscore": None,
            "split_nested_sheet_drawings": None,
            "use_name_identifiers": None,
        },
    )

    assert result["nc_by_sheet"][0]["nc_filename"] == "a.nc"
    assert result["nc_missing"] == []
    assert result["nc_unmatched"] == [str(tmp_path / "m_a.nc")]


@pytest.mark.skipif(os.name == "nt", reason="symlinks")
def test_find_nc_files_does_not_follow_symlinks(tmp_path: pathlib.Path) -> None:
    out = tmp_path / "out"
    out.mkdir()
    real = tmp_path / "real"
    real.mkdir()
    (real / "X.nc").write_text("x", encoding="utf-8")
    os.symlink(real, out / "link")
    result = acrepd.find_nc_files(str(out), [_sheet("X")])

    assert result["nc_by_sheet"] == {}
    assert result["nc_missing"] == ["X"]
    assert result["nc_unmatched"] == []


def test_find_nc_files_includes_nc_candidates(tmp_path: pathlib.Path) -> None:
    _nc(tmp_path, "Arkusz_A1.nc")
    result = acrepd.find_nc_files(str(tmp_path), [_sheet("Arkusz A1")])

    assert result["nc_candidates"] == [
        {
            "path": str(tmp_path / "Arkusz_A1.nc"),
            "filename": "Arkusz_A1.nc",
            "stem": "Arkusz_A1",
            "preferred": False,
        }
    ]
    assert result["nc_by_sheet"][0]["nc_filename"] == "Arkusz_A1.nc"


def test_find_nc_path_with_candidates_skips_scan(tmp_path: pathlib.Path) -> None:
    _nc(tmp_path, "Arkusz_A1.nc")

    assert acrepd.find_nc_path(str(tmp_path), "Arkusz_A1.nc", candidates=[]) is None
    found = acrepd._nc_scan(str(tmp_path))
    assert acrepd.find_nc_path(str(tmp_path), "Arkusz_A1.nc", candidates=found) == str(
        tmp_path / "Arkusz_A1.nc"
    )


def test_find_nc_path(tmp_path: pathlib.Path) -> None:
    _nc(tmp_path, "nc", "Fronty - MDF_18_s1.nc")

    found = acrepd.find_nc_path(str(tmp_path), "Fronty - MDF_18_s1.nc")

    assert found == str(tmp_path / "nc" / "Fronty - MDF_18_s1.nc")
    assert acrepd.find_nc_path(str(tmp_path), "brak.nc") is None


def test_find_nc_path_matches_stem_after_normalization(tmp_path: pathlib.Path) -> None:
    _nc(tmp_path, "Arkusz_A1.nc")

    found = acrepd.find_nc_path(str(tmp_path), "Arkusz A1.nc")

    assert found == str(tmp_path / "Arkusz_A1.nc")
    assert acrepd.find_nc_path(str(tmp_path), "Inny_Arkusz.nc") is None


def _token_part(name: str, qty: Any, token: Any = None, order: Any = None) -> dict[str, Any]:
    part: dict[str, Any] = {"name": name, "quantity_on_sheet": qty, "custom_field_1": token}
    if order is not None:
        part["csv_order_number"] = order
    return part


def _token_manifest(
    sheets: list[tuple[str, list[dict[str, Any]]]],
    unmatched: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    return {
        "sheets": [{"name": name, "parts": parts} for name, parts in sheets],
        "unmatched_parts": unmatched or [],
    }


def test_aggregate_by_token_groups_and_sums() -> None:
    manifest = _token_manifest(
        [
            (
                "Arkusz A1",
                [
                    _token_part("p1", 4, "ABC", "Z-001"),
                    _token_part("p2", 2, "DEF"),
                    _token_part("p3", 3, "ABC"),
                ],
            ),
            ("Arkusz A2", [_token_part("p4", 1, "DEF", "Z-002")]),
        ],
        [_token_part("p5", 5, "ABC")],
    )

    result = acrepd.aggregate_by_token(manifest)

    assert [g["token"] for g in result] == ["ABC", "DEF"]
    assert result[0]["total_qty"] == 12
    assert result[0]["sheets"] == [
        {"sheet": "Arkusz A1", "qty": 7},
        {"sheet": "?", "qty": 5},
    ]
    assert result[0]["csv_order_number"] == "Z-001"
    assert result[1]["total_qty"] == 3
    assert result[1]["sheets"] == [
        {"sheet": "Arkusz A1", "qty": 2},
        {"sheet": "Arkusz A2", "qty": 1},
    ]
    assert result[1]["csv_order_number"] == "Z-002"


def test_aggregate_by_token_no_token_group_last() -> None:
    manifest = _token_manifest(
        [
            ("Arkusz A1", [_token_part("p1", 2, "  "), _token_part("p2", 1, "XYZ")]),
            ("Arkusz A2", [_token_part("p3", 3)]),
        ],
        [_token_part("p4", 4, None)],
    )

    result = acrepd.aggregate_by_token(manifest)

    assert [g["token"] for g in result] == ["XYZ", None]
    assert result[1]["total_qty"] == 9
    assert result[1]["sheets"] == [
        {"sheet": "Arkusz A1", "qty": 2},
        {"sheet": "Arkusz A2", "qty": 3},
        {"sheet": "?", "qty": 4},
    ]
    assert result[1]["csv_order_number"] is None


def test_aggregate_by_token_none_qty_as_zero() -> None:
    manifest = _token_manifest(
        [
            ("Arkusz A1", [_token_part("p1", None, "ABC"), _token_part("p2", 2, "ABC")]),
            ("Arkusz A2", [_token_part("p3", "nie-liczba", "ABC")]),
        ]
    )

    result = acrepd.aggregate_by_token(manifest)

    assert result[0]["total_qty"] == 2
    assert result[0]["sheets"] == [
        {"sheet": "Arkusz A1", "qty": 2},
        {"sheet": "Arkusz A2", "qty": 0},
    ]


def test_aggregate_by_token_first_nonempty_order_number() -> None:
    manifest = _token_manifest(
        [
            ("Arkusz A1", [_token_part("p1", 1, "ABC", "  "), _token_part("p2", 1, "ABC")]),
            ("Arkusz A2", [_token_part("p3", 1, "ABC", "Z-999")]),
        ]
    )

    result = acrepd.aggregate_by_token(manifest)

    assert result[0]["csv_order_number"] == "Z-999"


def test_aggregate_by_token_sort_case_insensitive() -> None:
    manifest = _token_manifest(
        [
            ("Arkusz A1", [_token_part("p1", 1, "beta")]),
            ("Arkusz A2", [_token_part("p2", 1, "Alpha")]),
            ("Arkusz A3", [_token_part("p3", 1, "ALPHA")]),
        ]
    )

    result = acrepd.aggregate_by_token(manifest)

    assert [g["token"] for g in result] == ["ALPHA", "Alpha", "beta"]


def test_aggregate_by_token_case_sensitive_grouping() -> None:
    manifest = _token_manifest(
        [
            ("Arkusz A1", [_token_part("p1", 1, "ABC"), _token_part("p2", 2, "abc")]),
        ]
    )

    result = acrepd.aggregate_by_token(manifest)

    assert [g["token"] for g in result] == ["ABC", "abc"]
    assert result[0]["total_qty"] == 1
    assert result[1]["total_qty"] == 2


def test_aggregate_by_token_empty_manifest() -> None:
    assert acrepd.aggregate_by_token({"sheets": [], "unmatched_parts": []}) == []


def _validation_manifest(
    sheets: list[tuple[str, list[dict[str, Any]]]],
    unmatched: list[dict[str, Any]] | None = None,
    total_parts: int | None = None,
) -> dict[str, Any]:
    manifest = _token_manifest(sheets, unmatched)
    manifest["total_parts"] = (
        total_parts if total_parts is not None else sum(len(parts) for _, parts in sheets)
    )
    return manifest


def test_validate_manifest_ok() -> None:
    manifest = _validation_manifest(
        [
            ("Arkusz A1", [_token_part("p1", 4, "ABC", "Z-001"), _token_part("p2", 3, "ABC")]),
            ("Arkusz A2", [_token_part("p3", 2, "DEF", "Z-002")]),
        ]
    )

    result = acrepd.validate_manifest(manifest, {"ABC": 7, "DEF": 2})

    assert result == {"valid": True, "warnings": [], "errors": []}


def test_validate_manifest_token_qty_mismatch_error() -> None:
    manifest = _validation_manifest(
        [
            ("Arkusz A1", [_token_part("p1", 4, "ABC"), _token_part("p2", 3, "ABC")]),
            ("Arkusz A2", [_token_part("p3", 2, "DEF")]),
        ]
    )

    result = acrepd.validate_manifest(manifest, {"ABC": 8})

    assert result["valid"] is False
    assert result["errors"] == ['token "ABC": expected 8, got 7']


def test_validate_manifest_missing_token_error() -> None:
    manifest = _validation_manifest([("Arkusz A1", [_token_part("p1", 4, "ABC")])])

    result = acrepd.validate_manifest(manifest, {"XYZ": 5})

    assert result["valid"] is False
    assert result["errors"] == ['token "XYZ": expected 5, got 0']


def test_validate_manifest_total_parts_mismatch_error() -> None:
    manifest = _validation_manifest(
        [("Arkusz A1", [_token_part("p1", 4, "ABC"), _token_part("p2", 3, "ABC")])],
        total_parts=5,
    )

    result = acrepd.validate_manifest(manifest)

    assert result["valid"] is False
    assert result["errors"] == ["total_parts mismatch: expected 5, got 2"]


def test_validate_manifest_parts_without_order_and_token_warning() -> None:
    manifest = _validation_manifest(
        [
            ("Arkusz A1", [_token_part("p1", 4, "ABC"), _token_part("p2", 2)]),
            ("Arkusz A2", [_token_part("p3", 1)]),
        ]
    )

    result = acrepd.validate_manifest(manifest)

    assert result["valid"] is True
    assert result["warnings"] == ["2 parts without csv_order_number and custom_field_1"]
    assert result["errors"] == []


def test_validate_manifest_valid_true_with_warnings() -> None:
    manifest = _validation_manifest(
        [
            ("Arkusz A1", [_token_part("p1", 4, "ABC", "Z-001"), _token_part("p2", 2)]),
            ("Arkusz A2", [_token_part("p3", 1, "DEF", "Z-002")]),
        ]
    )

    result = acrepd.validate_manifest(manifest, {"ABC": 4, "DEF": 1})

    assert result["valid"] is True
    assert result["warnings"] == ["1 parts without csv_order_number and custom_field_1"]
    assert result["errors"] == []


def test_validate_manifest_valid_false_with_errors() -> None:
    manifest = _validation_manifest(
        [
            ("Arkusz A1", [_token_part("p1", 4, "ABC", "Z-001")]),
            ("Arkusz A2", [_token_part("p3", 1, "DEF", "Z-002")]),
        ]
    )

    result = acrepd.validate_manifest(manifest, {"ABC": 5, "DEF": 1})

    assert result["valid"] is False
    assert result["errors"] == ['token "ABC": expected 5, got 4']
    assert result["warnings"] == []


def test_aggregate_by_token_strips_token_whitespace() -> None:
    manifest = _token_manifest(
        [
            ("Arkusz A1", [_token_part("p1", 2, " ABC ")]),
            ("Arkusz A2", [_token_part("p2", 3, "ABC")]),
        ]
    )

    result = acrepd.aggregate_by_token(manifest)

    assert [g["token"] for g in result] == ["ABC"]
    assert result[0]["total_qty"] == 5


def test_fill_class_full_partial_empty() -> None:
    assert acrepd.fill_class(100) == "full"
    assert acrepd.fill_class(85) == "full"
    assert acrepd.fill_class(70) == "full"
    assert acrepd.fill_class(69) == "partial"
    assert acrepd.fill_class(50) == "partial"
    assert acrepd.fill_class(1) == "partial"
    assert acrepd.fill_class(0) == "empty"
    assert acrepd.fill_class(None) == "empty"


def test_fill_class_custom_threshold() -> None:
    assert acrepd.fill_class(50, threshold=50) == "full"
    assert acrepd.fill_class(49, threshold=50) == "partial"
    assert acrepd.fill_class(30, threshold=50) == "partial"
    assert acrepd.fill_class(0, threshold=50) == "empty"
    assert acrepd.fill_class(None, threshold=50) == "empty"


def test_fill_class_threshold_boundaries() -> None:
    assert acrepd.fill_class(1, threshold=0) == "full"
    assert acrepd.fill_class(0, threshold=0) == "empty"
    assert acrepd.fill_class(100, threshold=100) == "full"
    assert acrepd.fill_class(99, threshold=100) == "partial"


def test_fill_class_invalid_threshold_falls_back_to_default() -> None:
    assert acrepd.fill_class(85, threshold=101) == "full"
    assert acrepd.fill_class(85, threshold=-1) == "full"
    assert acrepd.fill_class(69, threshold=150) == "partial"
    assert acrepd.fill_class(69, threshold=None) == "partial"
