$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
Add-Type -Path 'C:\Program Files\Hexagon\ALPHACAM 2025\VistaDB.5.NET40.dll'
$conn = New-Object VistaDB.Provider.VistaDBConnection('Data Source=C:\ALPHACAM\LICOMDAT\Automation Manager Data\AutomationManager.vdb5')
$conn.Open()
try {
    $cmd = $conn.CreateCommand()
    $cmd.CommandText = 'SELECT * FROM CDM_DoorTypes'
    $reader = $cmd.ExecuteReader()
    $rows = @()
    while ($reader.Read()) {
        $row = @{}
        for ($i = 0; $i -lt $reader.FieldCount; $i++) {
            $row[$reader.GetName($i)] = $reader.GetValue($i)
        }
        $rows += $row
    }
    $json = $rows | ConvertTo-Json -Compress
    if ($json -notmatch '^\s*\[') {
        $json = "[$json]"
    }
    Write-Output $json
} finally {
    $conn.Close()
}
