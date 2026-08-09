$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
Add-Type -Path 'C:\Program Files\Hexagon\ALPHACAM 2025\VistaDB.5.NET40.dll'
$conn = New-Object VistaDB.Provider.VistaDBConnection('Data Source=C:\ALPHACAM\LICOMDAT\Automation Manager Data\AutomationManager.vdb5')
$conn.Open()
try {
    $cfgId = $null
    $cmd = $conn.CreateCommand()
    $cmd.CommandText = 'SELECT fkConfigurationSettingID FROM AM_Settings'
    $reader = $cmd.ExecuteReader()
    if ($reader.Read()) {
        $v = $reader.GetValue(0)
        if ($null -ne $v -and -not [DBNull]::Value.Equals($v)) {
            $cfgId = [int]$v
        }
    }
    $reader.Close()

    $cfgName = $null
    $matId = $null
    if ($null -ne $cfgId) {
        $cmd2 = $conn.CreateCommand()
        $cmd2.CommandText = "SELECT ConfigurationSettingName FROM AM_ConfigurationSettings WHERE ConfigurationSettingID = $cfgId"
        $r2 = $cmd2.ExecuteReader()
        if ($r2.Read()) {
            $cfgName = [string]$r2.GetValue(0)
        }
        $r2.Close()

        $cmd3 = $conn.CreateCommand()
        $cmd3.CommandText = "SELECT fkMaterialID FROM AM_JobFileDefaults WHERE fkConfigurationSettingID = $cfgId"
        $r3 = $cmd3.ExecuteReader()
        if ($r3.Read()) {
            $v3 = $r3.GetValue(0)
            if ($null -ne $v3 -and -not [DBNull]::Value.Equals($v3)) {
                $matId = [int]$v3
            }
        }
        $r3.Close()
    }

    $result = @{
        config_id = $cfgId
        config_name = $cfgName
        material_id = $matId
    }
    $result | ConvertTo-Json -Compress | Write-Output
} finally {
    $conn.Close()
}
