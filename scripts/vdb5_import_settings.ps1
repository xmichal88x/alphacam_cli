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

try {
    $conn.Open()
    $settingsById = @{}
    $order = New-Object System.Collections.ArrayList
    $cmd = $conn.CreateCommand()
    $cmd.CommandText = 'SELECT ImportSettingID, ImportSettingName, Selected, DelimiterChar, IgnoreHeader, IsCDMImport, SubDelimiterChar, CreateJob FROM AM_ImportSettings'
    $reader = $cmd.ExecuteReader()
    while ($reader.Read()) {
        $id = [int]$reader.GetValue(0)
        $settingsById[$id] = @{
            id = $id
            name = Get-StrVal $reader.GetValue(1)
            selected = Get-BoolVal $reader.GetValue(2)
            delimiter_char = Get-StrVal $reader.GetValue(3)
            ignore_header = Get-BoolVal $reader.GetValue(4)
            is_cdm_import = Get-BoolVal $reader.GetValue(5)
            sub_delimiter_char = Get-StrVal $reader.GetValue(6)
            create_job = Get-BoolVal $reader.GetValue(7)
            fields = New-Object System.Collections.ArrayList
        }
        [void]$order.Add($id)
    }
    $reader.Close()

    $cmd2 = $conn.CreateCommand()
    $cmd2.CommandText = 'SELECT ImportSettingID, ParameterType, ColumnNumber FROM AM_ImportSettingsParameter ORDER BY ImportSettingID, ColumnNumber'
    $r2 = $cmd2.ExecuteReader()
    while ($r2.Read()) {
        $sid = [int]$r2.GetValue(0)
        if ($settingsById.ContainsKey($sid)) {
            [void]$settingsById[$sid]['fields'].Add(@{
                column_number = [int]$r2.GetValue(2)
                parameter_type = [int]$r2.GetValue(1)
            })
        }
    }
    $r2.Close()

    $result = New-Object System.Collections.ArrayList
    foreach ($id in $order) {
        [void]$result.Add($settingsById[$id])
    }
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
