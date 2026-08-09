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
    'MaterialName' = 'name'
}
$intFields = @{
    'MaterialID' = 'id'
    'GrainRestriction' = 'grain_restriction'
}
$dblFields = @{
    'SheetWidth' = 'width'
    'SheetLength' = 'length'
    'SheetThickness' = 'thickness'
}

try {
    $conn.Open()
    $cmd = $conn.CreateCommand()
    $cmd.CommandText = 'SELECT MaterialID, MaterialName, SheetWidth, SheetLength, SheetThickness, GrainRestriction FROM AM_Materials ORDER BY MaterialID'
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
