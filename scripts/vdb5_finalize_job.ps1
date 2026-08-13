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
    $cmd.CommandText = "SELECT JobDetailID FROM AM_JobDetails WHERE JobName = '$job'"
    $r = $cmd.ExecuteReader()
    $jdId = $null
    if ($r.Read()) { $jdId = [int]$r.GetValue(0) }
    $r.Close()
    if ($null -eq $jdId) {
        Write-Output "rows: 0"
        exit 0
    }
    $cmd2 = $conn.CreateCommand()
    $cmd2.CommandText = "UPDATE AM_JobDetails SET [JobType] = 1 WHERE JobDetailID = $jdId"
    Write-Output ("job_rows: " + $cmd2.ExecuteNonQuery())
    $cmd3 = $conn.CreateCommand()
    $cmd3.CommandText = "INSERT INTO AM_SelectedSheets (fkJobDetailID, SelectedSheetID, Quantity) SELECT $jdId, SelectedSheetID, Quantity FROM AM_SelectedSheetDefaults WHERE NOT EXISTS (SELECT 1 FROM AM_SelectedSheets WHERE fkJobDetailID = $jdId AND SelectedSheetID = AM_SelectedSheetDefaults.SelectedSheetID)"
    Write-Output ("sheet_rows: " + $cmd3.ExecuteNonQuery())
} finally {
    $conn.Close()
}
