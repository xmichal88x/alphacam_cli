$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
Add-Type -Path 'C:\Program Files\Hexagon\ALPHACAM 2025\VistaDB.5.NET40.dll'
$conn = New-Object VistaDB.Provider.VistaDBConnection('Data Source=C:\ALPHACAM\LICOMDAT\Automation Manager Data\AutomationManager.vdb5')
$conn.Open()
try {
    $cmd = $conn.CreateCommand()
    $cmd.CommandText = 'SELECT CustomField1, CustomField2, CustomField3, CustomField4, CustomField5, CustomField6, CustomField7, CustomField8, CustomField9, CustomField10, CustomField11, CustomField12, CustomField13, CustomField14, CustomField15, CustomField16, CustomField17, CustomField18, CustomField19, CustomField20, CustomField21, CustomField22, CustomField23, CustomField24, CustomField25 FROM AM_Settings'
    $reader = $cmd.ExecuteReader()
    $names = @{}
    if ($reader.Read()) {
        for ($n = 1; $n -le 25; $n++) {
            $v = $reader.GetValue($n - 1)
            if ($null -ne $v -and -not [DBNull]::Value.Equals($v)) {
                $s = [string]$v
                if ($s.Trim()) { $names["$n"] = $s.Trim() }
            }
        }
    }
    $reader.Close()
    $names | ConvertTo-Json -Compress | Write-Output
} finally {
    $conn.Close()
}
