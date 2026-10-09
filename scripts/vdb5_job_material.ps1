param(
    [string]$JobName
)
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
Add-Type -Path 'C:\Program Files\Hexagon\ALPHACAM 2025\VistaDB.5.NET40.dll'
$conn = New-Object VistaDB.Provider.VistaDBConnection('Data Source=C:\ALPHACAM\LICOMDAT\Automation Manager Data\AutomationManager.vdb5')
$conn.Open()
try {
    $job = $JobName.Replace("'", "''")
    $cmd = $conn.CreateCommand()
    $cmd.CommandText = "SELECT fkMaterialID FROM AM_JobDetails WHERE JobName = '$job'"
    $r = $cmd.ExecuteReader()
    $mat = ""
    if ($r.Read()) {
        if (-not $r.IsDBNull(0)) { $mat = [string]$r.GetValue(0) }
    }
    $r.Close()
    Write-Output ("material: " + $mat)
} finally {
    $conn.Close()
}
