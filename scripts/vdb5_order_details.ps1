param(
    [string]$JobName
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
    'JobName' = 'job_name'
    'StyleName' = 'style_name'
    'CSV_CustomerName' = 'csv_customer_name'
    'CSV_OrderNumber' = 'csv_order_number'
    'CSV_ItemNumber' = 'csv_item_number'
    'ProductionComment' = 'production_comment'
    'UserVariableString' = 'user_variable_string'
    'UserDescriptionString' = 'user_description_string'
}
for ($n = 0; $n -le 6; $n++) {
    $strFields["UserValue_$n"] = "user_value_$n"
}
$intFields = @{
    'StyleNumber' = 'style_number'
    'Quantity' = 'quantity'
    'fkMaterialID' = 'material_id'
    'RotationMethod' = 'rotation_method'
    'NestingPriority' = 'nesting_priority'
    'fkTypeID' = 'fk_type_id'
    'CDM_PK' = 'cdm_pk'
    'CDM_OrderID' = 'cdm_order_id'
    'fkParentOrderDetailID' = 'fk_parent_order_detail_id'
}
$dblFields = @{
    'OrderDetailDoorWidth' = 'width'
    'OrderDetailDoorLength' = 'length'
    'CornerRadius' = 'corner_radius'
    'OversizeX' = 'oversize_x'
    'OversizeY' = 'oversize_y'
    'RotationAngle' = 'rotation_angle'
}
$boolFields = @{
    'IgnoreOuterGeometry' = 'ignore_outer_geometry'
    'SmallNestPart' = 'small_nest_part'
    'HasDrilling' = 'has_drilling'
    'ByPassNest' = 'bypass_nest'
    'ActiveInProcess' = 'active_in_process'
}

try {
    $conn.Open()
    $cmd = $conn.CreateCommand()
    $cmd.CommandText = 'SELECT * FROM CDM_OrderDetails d INNER JOIN AM_JobDetails j ON d.fkJobDetailID = j.JobDetailID'
    if ($JobName) {
        $escaped = $JobName.Replace("'", "''")
        $cmd.CommandText += " WHERE j.JobName = '$escaped'"
    }
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
        $cf = [ordered]@{}
        for ($n = 1; $n -le 25; $n++) {
            $src = "CDMCustomField$n"
            if ($indexByName.ContainsKey($src)) {
                $cf["$n"] = Get-StrVal $reader.GetValue($indexByName[$src])
            } else {
                $cf["$n"] = ''
            }
        }
        $row['custom_fields'] = $cf
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
