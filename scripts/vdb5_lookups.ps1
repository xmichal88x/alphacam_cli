param()
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
Add-Type -Path 'C:\Program Files\Hexagon\ALPHACAM 2025\VistaDB.5.NET40.dll'
$conn = New-Object VistaDB.Provider.VistaDBConnection('Data Source=C:\ALPHACAM\LICOMDAT\Automation Manager Data\AutomationManager.vdb5')

function Get-StrVal {
    param([object]$v)
    if ($null -ne $v -and -not [DBNull]::Value.Equals($v)) { return [string]$v }
    return ''
}

function Get-BoolVal {
    param([object]$v)
    if ($null -ne $v -and -not [DBNull]::Value.Equals($v)) { return [bool]$v }
    return $false
}

function Get-IntVal {
    param([object]$v)
    if ($null -ne $v -and -not [DBNull]::Value.Equals($v)) { return [int]$v }
    return 0
}

function Get-DblVal {
    param([object]$v)
    if ($null -ne $v -and -not [DBNull]::Value.Equals($v)) { return [double]$v }
    return 0.0
}

function Read-Section {
    param(
        [object]$Reader,
        [hashtable]$StrFields,
        [hashtable]$IntFields,
        [hashtable]$DblFields,
        [hashtable]$BoolFields
    )
    $indexByName = @{}
    for ($i = 0; $i -lt $Reader.FieldCount; $i++) {
        $indexByName[$Reader.GetName($i).Trim('[', ']')] = $i
    }

    $rows = New-Object System.Collections.ArrayList
    while ($Reader.Read()) {
        $row = [ordered]@{}
        foreach ($src in $StrFields.Keys) {
            if ($indexByName.ContainsKey($src)) {
                $row[$StrFields[$src]] = Get-StrVal $Reader.GetValue($indexByName[$src])
            }
        }
        foreach ($src in $IntFields.Keys) {
            if ($indexByName.ContainsKey($src)) {
                $row[$IntFields[$src]] = Get-IntVal $Reader.GetValue($indexByName[$src])
            }
        }
        foreach ($src in $DblFields.Keys) {
            if ($indexByName.ContainsKey($src)) {
                $row[$DblFields[$src]] = Get-DblVal $Reader.GetValue($indexByName[$src])
            }
        }
        foreach ($src in $BoolFields.Keys) {
            if ($indexByName.ContainsKey($src)) {
                $row[$BoolFields[$src]] = Get-BoolVal $Reader.GetValue($indexByName[$src])
            }
        }
        [void]$rows.Add($row)
    }
    $Reader.Close()
    return $rows
}

$setupStrFields = @{
    'SetupName' = 'name'
    'GeometryQuery' = 'geometry_query'
    'GeometryAutoQuery' = 'geometry_auto_query'
}
$setupIntFields = @{
    'SetupID' = 'id'
    'FE_WhatToExtract' = 'fe_what_to_extract'
    'FE_ContourExtractionMode' = 'fe_contour_extraction_mode'
    'FE_DrillableHolesExtractionMode' = 'fe_drillable_holes_extraction_mode'
    'SetupSeqNum' = 'setup_seq_num'
}
$setupDblFields = @{
    'FE_ChordTolerance' = 'fe_chord_tolerance'
    'FE_ZLevelStep' = 'fe_z_level_step'
    'FE_MaxDiaDrilledHoles' = 'fe_max_dia_drilled_holes'
    'IMP_StepLength' = 'imp_step_length'
}
$setupBoolFields = @{
    'FE_UsePanelAlignment' = 'fe_use_panel_alignment'
    'FE_UseOpenAirPocketMethod' = 'fe_use_open_air_pocket_method'
    'FE_LimitThroughHoles' = 'fe_limit_through_holes'
    'FE_ExtractAllFaces' = 'fe_extract_all_faces'
    'IMP_Project3Dto2D' = 'imp_project_3d_to_2d'
    'IMP_CommonLineRemoval' = 'imp_common_line_removal'
    'IMP_JoinResultingGeos' = 'imp_join_resulting_geos'
    'IMP_ConvertSpline' = 'imp_convert_spline'
    'IMP_DeleteOriginal' = 'imp_delete_original'
    'IMP_JoinResultingLinesOrArcs' = 'imp_join_resulting_lines_or_arcs'
    'IMP_SetElementZLevels' = 'imp_set_element_z_levels'
}

$customerStrFields = @{
    'CustomerName' = 'name'
    'AddressLine1' = 'address_line_1'
    'AddressLine2' = 'address_line_2'
    'City' = 'city'
    'Country' = 'country'
    'PostZipCode' = 'post_zip_code'
    'ContactName' = 'contact_name'
    'TelephoneNumber' = 'telephone_number'
    'EmailAddress' = 'email_address'
    'WebsiteAddress' = 'website_address'
}
$customerIntFields = @{
    'CustomerID' = 'id'
}

$machiningOrderStrFields = @{
    'MachiningStyleName' = 'machining_style_name'
    'LayerName' = 'layer_name'
    'ListName' = 'list_name'
}
$machiningOrderIntFields = @{
    'ToolOrderID' = 'tool_order_id'
    'fkToolOrderListID' = 'fk_tool_order_list_id'
    'SeqNum' = 'seq_num'
}
$machiningOrderBoolFields = @{
    'IsMultidrill' = 'is_multidrill'
}

$doorstyleStrFields = @{
    'FullFileName' = 'full_file_name'
    'VBAProjectName' = 'vba_project_name'
}
$doorstyleIntFields = @{
    'UserStyleID' = 'id'
}

$multidrillStrFields = @{
    'MultidrillHeadName' = 'name'
}
$multidrillIntFields = @{
    'MultidrillHeadID' = 'id'
}
$multidrillDblFields = @{
    'FeedRate' = 'feed_rate'
    'SpindleSpeed' = 'spindle_speed'
    'SafeRapidDistance' = 'safe_rapid_distance'
    'RapidDownTo' = 'rapid_down_to'
    'MaterialTop' = 'material_top'
    'BottomOfHole' = 'bottom_of_hole'
}
$multidrillBoolFields = @{
    'Selected' = 'selected'
}

$fittingStrFields = @{
    'FittingType' = 'fitting_type'
    'FittingFile' = 'fitting_file'
}
$fittingIntFields = @{
    'FittingID' = 'id'
    'fkJobFileID' = 'fk_job_file_id'
}

$layerMappingStrFields = @{
    'LayerName' = 'layer_name'
    'MachiningStyleName' = 'machining_style_name'
    'SetupName' = 'setup_name'
}
$layerMappingIntFields = @{
    'LayerMappingID' = 'layer_mapping_id'
    'fkSetupID' = 'fk_setup_id'
    'MachiningOrder' = 'machining_order'
    'ToolSideClosedGeo' = 'tool_side_closed_geo'
    'ToolSideOpenGeo' = 'tool_side_open_geo'
    'ToolDirectionClosedGeo' = 'tool_direction_closed_geo'
    'ToolDirectionOpenGeo' = 'tool_direction_open_geo'
    'StartPoint' = 'start_point'
    'LayerOrder' = 'layer_order'
}
$layerMappingBoolFields = @{
    'IsFeatureLayer' = 'is_feature_layer'
    'ApplyIndividuallyToEachGeometry' = 'apply_individually_to_each_geometry'
}

try {
    $conn.Open()
    $cmd = $conn.CreateCommand()

    $cmd.CommandText = 'SELECT SetupID, SetupName, FE_WhatToExtract, FE_UsePanelAlignment, FE_ChordTolerance, FE_ZLevelStep, FE_UseOpenAirPocketMethod, FE_LimitThroughHoles, FE_MaxDiaDrilledHoles, FE_ExtractAllFaces, GeometryQuery, GeometryAutoQuery, FE_ContourExtractionMode, FE_DrillableHolesExtractionMode, IMP_Project3Dto2D, IMP_StepLength, IMP_CommonLineRemoval, IMP_JoinResultingGeos, IMP_ConvertSpline, IMP_DeleteOriginal, IMP_JoinResultingLinesOrArcs, IMP_SetElementZLevels, SetupSeqNum FROM AM_Setups ORDER BY SetupSeqNum, SetupID'
    $reader = $cmd.ExecuteReader()
    $setups = Read-Section -Reader $reader -StrFields $setupStrFields -IntFields $setupIntFields -DblFields $setupDblFields -BoolFields $setupBoolFields

    $cmd.CommandText = 'SELECT CustomerID, CustomerName, AddressLine1, AddressLine2, City, Country, PostZipCode, ContactName, TelephoneNumber, EmailAddress, WebsiteAddress FROM AM_CustomerDetails ORDER BY CustomerID'
    $reader = $cmd.ExecuteReader()
    $customers = Read-Section -Reader $reader -StrFields $customerStrFields -IntFields $customerIntFields -DblFields @{} -BoolFields @{}

    $cmd.CommandText = 'SELECT m.ToolOrderID, m.fkToolOrderListID, m.MachiningStyleName, m.LayerName, m.SeqNum, m.IsMultidrill, l.ToolOrderListName AS ListName FROM AM_MachiningOrder m LEFT JOIN AM_ToolOrderLists l ON m.fkToolOrderListID = l.ToolOrderListID ORDER BY m.SeqNum, m.ToolOrderID'
    $reader = $cmd.ExecuteReader()
    $machiningOrders = Read-Section -Reader $reader -StrFields $machiningOrderStrFields -IntFields $machiningOrderIntFields -DblFields @{} -BoolFields $machiningOrderBoolFields

    $cmd.CommandText = 'SELECT UserStyleID, FullFileName, VBAProjectName FROM CDM_UserStyles ORDER BY UserStyleID'
    $reader = $cmd.ExecuteReader()
    $doorstyles = Read-Section -Reader $reader -StrFields $doorstyleStrFields -IntFields $doorstyleIntFields -DblFields @{} -BoolFields @{}

    $cmd.CommandText = 'SELECT MultidrillHeadID, MultidrillHeadName, Selected, FeedRate, SpindleSpeed, SafeRapidDistance, RapidDownTo, MaterialTop, BottomOfHole FROM AM_Multidrill ORDER BY MultidrillHeadID'
    $reader = $cmd.ExecuteReader()
    $multidrill = Read-Section -Reader $reader -StrFields $multidrillStrFields -IntFields $multidrillIntFields -DblFields $multidrillDblFields -BoolFields $multidrillBoolFields

    $cmd.CommandText = 'SELECT FittingID, fkJobFileID, FittingType, FittingFile FROM AM_Fittings ORDER BY FittingID'
    $reader = $cmd.ExecuteReader()
    $fittings = Read-Section -Reader $reader -StrFields $fittingStrFields -IntFields $fittingIntFields -DblFields @{} -BoolFields @{}

    $cmd.CommandText = 'SELECT lm.LayerMappingID, lm.fkSetupID, lm.LayerName, lm.MachiningStyleName, lm.MachiningOrder, lm.IsFeatureLayer, lm.ToolSideClosedGeo, lm.ToolSideOpenGeo, lm.ToolDirectionClosedGeo, lm.ToolDirectionOpenGeo, lm.StartPoint, lm.LayerOrder, lm.ApplyIndividuallyToEachGeometry, s.SetupName AS SetupName FROM AM_LayerMapping lm LEFT JOIN AM_Setups s ON lm.fkSetupID = s.SetupID ORDER BY lm.fkSetupID, lm.LayerOrder, lm.LayerMappingID'
    $reader = $cmd.ExecuteReader()
    $layersMapping = Read-Section -Reader $reader -StrFields $layerMappingStrFields -IntFields $layerMappingIntFields -DblFields @{} -BoolFields $layerMappingBoolFields

    $payload = [ordered]@{
        setups = $setups
        customers = $customers
        machining_orders = $machiningOrders
        doorstyles = $doorstyles
        multidrill = $multidrill
        fittings = $fittings
        layers_mapping = $layersMapping
    }
    Write-Output (ConvertTo-Json -InputObject $payload -Compress -Depth 10)
} catch {
    Write-Error $_.Exception.Message
    exit 1
} finally {
    if ($null -ne $conn) { $conn.Close() }
}
