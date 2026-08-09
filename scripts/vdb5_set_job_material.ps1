$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
param(
    [string]$JobName,
    [int]$MaterialID
)
Add-Type -Path 'C:\Program Files\Hexagon\ALPHACAM 2025\VistaDB.5.NET40.dll'
$conn = New-Object VistaDB.Provider.VistaDBConnection('Data Source=C:\ALPHACAM\LICOMDAT\Automation Manager Data\AutomationManager.vdb5')
$conn.Open()
try {
    $cmd = $conn.CreateCommand()
    $job = $JobName.Replace("'", "''")
    $cmd.CommandText = "UPDATE AM_JobDetails SET fkMaterialID = $MaterialID WHERE JobName = '$job'"
    Write-Output ("rows: " + $cmd.ExecuteNonQuery())
} finally {
    $conn.Close()
}
