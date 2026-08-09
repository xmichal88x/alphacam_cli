param(
    [string]$TypeName
)
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

$strFields = @{
    'PathName' = 'path_name'
    'LastModified' = 'last_modified'
    'ToolName' = 'tool_name'
    'ToolFullPath' = 'tool_full_path'
    'MachiningMethod' = 'machining_method'
    'MachiningStyle' = 'machining_style'
    'CutType' = 'cut_type'
    'CreationMethod' = 'creation_method'
    'InsertFilePath' = 'insert_file_path'
    'TypeName' = 'door_type'
}
$intFields = @{
    'PathID' = 'path_id'
    'CDM_PathID' = 'cdm_path_id'
    'DoorTypeID' = 'door_type_id'
    'PathNumber' = 'path_number'
    'GroupID' = 'group_id'
    'ToolNumber' = 'tool_number'
    'ToolOffset' = 'tool_offset'
    'NumberOfCuts' = 'number_of_cuts'
    'XYCorners' = 'xy_corners'
    'FinalPassIsland' = 'final_pass_island'
    'PocketType' = 'pocket_type'
    'StartCutting' = 'start_cutting'
    'PathOffsetSide' = 'path_offset_side'
    'PathOffsetFrom' = 'path_offset_from'
    'LeadEntryPointIsCorner' = 'lead_entry_point_is_corner'
    'PartialStartElemIndex' = 'partial_start_elem_index'
    'PartialEndElemIndex' = 'partial_end_elem_index'
    'NumberOfSteps' = 'number_of_steps'
    'InsertParametricGroupNumber' = 'insert_parametric_group_number'
    'McComp' = 'mc_comp'
    'ToolInOut' = 'tool_in_out'
    'ToolSide' = 'tool_side'
    'LeadIn' = 'lead_in'
    'LeadOut' = 'lead_out'
    'InsertFileReferencePoint' = 'insert_file_reference_point'
}
$dblFields = @{
    'SafeRapid' = 'safe_rapid'
    'RapidDownTo' = 'rapid_down_to'
    'FinalDepth' = 'final_depth'
    'FinalDepthPercentage' = 'final_depth_percentage'
    'SpindleSpeed' = 'spindle_speed'
    'DownFeed' = 'down_feed'
    'CutFeed' = 'cut_feed'
    'CutDirection' = 'cut_direction'
    'MaterialTop' = 'material_top'
    'Stock' = 'stock'
    'ChordError' = 'chord_error'
    'ThicknessFirstCut' = 'thickness_first_cut'
    'ThicknessLastCut' = 'thickness_last_cut'
    'ThicknessFirstCutPercent' = 'thickness_first_cut_percent'
    'ThicknessLastCutPercent' = 'thickness_last_cut_percent'
    'Diameter' = 'diameter'
    'StepLength' = 'step_length'
    'PathOffsetValue' = 'path_offset_value'
    'PocketBoundary' = 'pocket_boundary'
    'LeadLineLength' = 'lead_line_length'
    'LeadLineLengthOut' = 'lead_line_length_out'
    'LeadArcRadius' = 'lead_arc_radius'
    'LeadApproachAngle' = 'lead_approach_angle'
    'LeadOverlap' = 'lead_overlap'
    'Lead3DApproachAngle' = 'lead3d_approach_angle'
    'Lead3DApproach' = 'lead3d_approach'
    'WidthOfCut' = 'width_of_cut'
    'InsertFilePointX' = 'insert_file_point_x'
    'InsertFilePointY' = 'insert_file_point_y'
    'EngraveCornerAngle' = 'engrave_corner_angle'
    'PartialStartElemDist' = 'partial_start_elem_dist'
    'PartialEndElemDist' = 'partial_end_elem_dist'
    'DecelerationDistance' = 'deceleration_distance'
    'SlowDownTo' = 'slow_down_to'
    'DoNotSlowDownRadius' = 'do_not_slow_down_radius'
    'IgnoreAngleGreaterThan' = 'ignore_angle_greater_than'
    'SimpleEngraveFeed' = 'simple_engrave_feed'
    'SimpleEngraveClearance' = 'simple_engrave_clearance'
}
$boolFields = @{
    'IsFinalDepthPercent' = 'is_final_depth_percent'
    'CompOnRapid' = 'comp_on_rapid'
    'SlopeIn' = 'slope_in'
    'SlopeOut' = 'slope_out'
    'DepthsOfCutSpecified' = 'depths_of_cut_specified'
    'MultiplePasses' = 'multiple_passes'
    'ToolDirectionCW' = 'tool_direction_cw'
    'ToolDirectionReversed' = 'tool_direction_reversed'
    'Pocket3DApproach' = 'pocket3d_approach'
    'SlowDownForCorners' = 'slow_down_for_corners'
    'AccelerateOutOfCorner' = 'accelerate_out_of_corner'
    'ToolSidePartialReverse' = 'tool_side_partial_reverse'
}

try {
    $conn.Open()
    $cmd = $conn.CreateCommand()
    $cmd.CommandText = 'SELECT * FROM CDM_DoorPaths p LEFT JOIN CDM_DoorTypes t ON p.DoorTypeID = t.DoorTypeID'
    if ($TypeName) {
        $escaped = $TypeName.Replace("'", "''")
        $cmd.CommandText += " WHERE t.TypeName = '$escaped'"
    }
    $cmd.CommandText += ' ORDER BY p.DoorTypeID, p.PathNumber'
    $reader = $cmd.ExecuteReader()
    $indexByName = @{}
    for ($i = 0; $i -lt $reader.FieldCount; $i++) {
        $indexByName[$reader.GetName($i).Trim('[', ']')] = $i
    }

    $result = New-Object System.Collections.ArrayList
    while ($reader.Read()) {
        $row = [ordered]@{}
        foreach ($src in $strFields.Keys) {
            if ($indexByName.ContainsKey($src)) {
                $row[$strFields[$src]] = Get-StrVal $reader.GetValue($indexByName[$src])
            }
        }
        foreach ($src in $intFields.Keys) {
            if ($indexByName.ContainsKey($src)) {
                $row[$intFields[$src]] = Get-IntVal $reader.GetValue($indexByName[$src])
            }
        }
        foreach ($src in $dblFields.Keys) {
            if ($indexByName.ContainsKey($src)) {
                $row[$dblFields[$src]] = Get-DblVal $reader.GetValue($indexByName[$src])
            }
        }
        foreach ($src in $boolFields.Keys) {
            if ($indexByName.ContainsKey($src)) {
                $row[$boolFields[$src]] = Get-BoolVal $reader.GetValue($indexByName[$src])
            }
        }
        [void]$result.Add($row)
    }
    $reader.Close()

    $json = ConvertTo-Json -InputObject $result -Compress -Depth 10
    if ($json -notmatch '^\s*\[') {
        $json = "[$json]"
    }
    Write-Output $json
} catch {
    Write-Error $_.Exception.Message
    exit 1
} finally {
    if ($null -ne $conn) { $conn.Close() }
}
