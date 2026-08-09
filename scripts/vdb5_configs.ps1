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

function Convert-DataReader {
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

$configStrFields = @{
    'ConfigurationSettingName' = 'name'
    'PostProcessor' = 'post_processor'
    'DrawingFileOutputLocation' = 'drawing_output_location'
    'NCFileOutputLocation' = 'nc_output_location'
    'ReportFileOutputLocation' = 'report_output_location'
    'NCFileExtension' = 'nc_extension'
    'CustomVBAMacro' = 'custom_vba_macro'
    'CompiledFileName' = 'compiled_file_name'
    'CompiledBaseName' = 'compiled_base_name'
}
$configIntFields = @{
    'ConfigurationSettingID' = 'id'
    'Nesting_Method' = 'nesting_method'
    'Nesting_PackTo' = 'nesting_pack_to'
    'Nesting_TimePerSheet' = 'nesting_time_per_sheet'
    'Nesting_OptimisationLevel' = 'nesting_optimisation_level'
    'Nesting_SheetOrderType' = 'nesting_sheet_order_type'
    'Nesting_SheetAlignment' = 'nesting_sheet_alignment'
}
$configDblFields = @{
    'Nesting_GapBetweenPaths' = 'nesting_gap_between_paths'
    'Nesting_GapAtSheetEdge' = 'nesting_gap_at_sheet_edge'
    'Nesting_ExtraGapAtLeadStart' = 'nesting_extra_gap_at_lead_start'
    'Nesting_SearchResolution' = 'nesting_search_resolution'
    'Nesting_TotalTime' = 'nesting_total_time'
    'Nesting_AlignmentZLevel' = 'nesting_alignment_z_level'
    'Nesting_JoinSawCutsTolerance' = 'nesting_join_saw_cuts_tolerance'
    'Nesting_InactivityTimeout' = 'nesting_inactivity_timeout'
}
$configBoolFields = @{
    'ReplaceSpaceWithUnderscore' = 'replace_space_with_underscore'
    'DisableScreenUpdates' = 'disable_screen_updates'
    'ClearOutputFolders' = 'clear_output_folders'
    'GenerateNC' = 'generate_nc'
    'GenerateReports' = 'generate_reports'
    'CreateDefaultMaterial' = 'create_default_material'
    'SaveGeneratedAutostyles' = 'save_generated_autostyles'
    'ReadFileInformationOnImport' = 'read_file_information_on_import'
    'ShowMaterialSelectorAfterImport' = 'show_material_selector_after_import'
    'Nesting_CutSmallPartsFirst' = 'nesting_cut_small_parts_first'
    'Nesting_DrillThenCutInnerPathsFirst' = 'nesting_drill_then_cut_inner_paths_first'
    'Nesting_LeaveEdgeGapUncut' = 'nesting_leave_edge_gap_uncut'
    'Nesting_MinimiseToolChanges' = 'nesting_minimise_tool_changes'
    'Nesting_UseBridged' = 'nesting_use_bridged'
    'Nesting_UseOnionSkin' = 'nesting_use_onion_skin'
    'Nesting_PreventNestingInApertures' = 'nesting_prevent_nesting_in_apertures'
    'Nesting_UseSupportTags' = 'nesting_use_support_tags'
    'Nesting_SplitNestedSheetDrawings' = 'nesting_split_nested_sheet_drawings'
    'Nesting_UseNameIdentifiers' = 'nesting_use_name_identifiers'
    'Nesting_CutWholePartTogether' = 'nesting_cut_whole_part_together'
    'Nesting_OrderByPart' = 'nesting_order_by_part'
    'Nesting_MinimiseSheetPatterns' = 'nesting_minimise_sheet_patterns'
    'Nesting_NestSmallPartsFirst' = 'nesting_nest_small_parts_first'
    'Nesting_TryRotatedPartFirstOnAllParts' = 'nesting_try_rotated_part_first_on_all_parts'
    'Nesting_OutputDrawingWithAllNestedSheets' = 'nesting_output_drawing_with_all_nested_sheets'
    'Nesting_SaveRejectedPartsToNewJob' = 'nesting_save_rejected_parts_to_new_job'
    'Nesting_OptimiseToolpathOverlapping' = 'nesting_optimise_toolpath_overlapping'
    'Nesting_SaveOffcuts' = 'nesting_save_offcuts'
    'Nesting_AllowSolidParts' = 'nesting_allow_solid_parts'
    'Nesting_AssistedNest' = 'nesting_assisted_nest'
    'Nesting_SaveOffcutsToDatabase' = 'nesting_save_offcuts_to_database'
    'Nesting_SuppressDuplicateSheets' = 'nesting_suppress_duplicate_sheets'
    'Nesting_ForceStrictPriorities' = 'nesting_force_strict_priorities'
    'Nesting_CommonLineCutting' = 'nesting_common_line_cutting'
    'Nesting_ReverseSideNesting' = 'nesting_reverse_side_nesting'
    'Nesting_ReverseSideUseAutoStyle' = 'nesting_reverse_side_use_auto_style'
    'Nesting_ReverseSideSheetSquaring' = 'nesting_reverse_side_sheet_squaring'
    'Nesting_UseJoinSawCuts' = 'nesting_use_join_saw_cuts'
    'Nesting_JoinSawCutsBidirectional' = 'nesting_join_saw_cuts_bidirectional'
    'Nesting_JoinSawCutsSuppressErrors' = 'nesting_join_saw_cuts_suppress_errors'
}
$cdmStrFields = @{
    'CustomMacro' = 'custom_macro'
}
$cdmIntFields = @{
    'CDMConfigurationSettingID' = 'cdm_configuration_setting_id'
    'fkConfigurationSettingID' = 'fk_configuration_setting_id'
}
$cdmDblFields = @{
    'PartRecoveryX' = 'part_recovery_x'
    'PartRecoveryY' = 'part_recovery_y'
    'DisableNestingOversizeX' = 'disable_nesting_oversize_x'
    'DisableNestingOversizeY' = 'disable_nesting_oversize_y'
    'ZDepthTolerance' = 'z_depth_tolerance'
    'PreviewMaterialThickness' = 'preview_material_thickness'
}
$cdmBoolFields = @{
    'PartRecoveryIgnoreGrain' = 'part_recovery_ignore_grain'
    'CaptureNestedPartPositions' = 'capture_nested_part_positions'
    'DisableNesting' = 'disable_nesting'
    'UseDefaultPress' = 'use_default_press'
    'PressGroupByMaterialThickness' = 'press_group_by_material_thickness'
    'UseDataFromToolFile' = 'use_data_from_tool_file'
    'UseSameStartPoint' = 'use_same_start_point'
    'UseDrawingExtentsForInsertedDrawingOperations' = 'use_drawing_extents_for_inserted_drawing_operations'
    'GenerateNCForParts' = 'generate_nc_for_parts'
}

try {
    $conn.Open()
    $cmd = $conn.CreateCommand()
    $cmd.CommandText = 'SELECT * FROM AM_ConfigurationSettings ORDER BY ConfigurationSettingID'
    $reader = $cmd.ExecuteReader()
    $configs = Convert-DataReader -Reader $reader -StrFields $configStrFields -IntFields $configIntFields -DblFields $configDblFields -BoolFields $configBoolFields

    $cmd.CommandText = 'SELECT * FROM CDM_ConfigurationSettings ORDER BY fkConfigurationSettingID, CDMConfigurationSettingID'
    $reader = $cmd.ExecuteReader()
    $cdm = Convert-DataReader -Reader $reader -StrFields $cdmStrFields -IntFields $cdmIntFields -DblFields $cdmDblFields -BoolFields $cdmBoolFields

    $configsJson = ConvertTo-Json -InputObject $configs -Compress -Depth 10
    if ($configsJson -notmatch '^\s*\[') {
        $configsJson = "[$configsJson]"
    }
    $cdmJson = ConvertTo-Json -InputObject $cdm -Compress -Depth 10
    if ($cdmJson -notmatch '^\s*\[') {
        $cdmJson = "[$cdmJson]"
    }
    Write-Output ('{"configs":' + $configsJson + ',"cdm":' + $cdmJson + '}')
} catch {
    Write-Error $_.Exception.Message
    exit 1
} finally {
    if ($null -ne $conn) { $conn.Close() }
}
