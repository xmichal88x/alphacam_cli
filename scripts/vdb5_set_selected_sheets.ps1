param(
    [string]$JobName,
    [string]$Sheets
)
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
Add-Type -Path 'C:\Program Files\Hexagon\ALPHACAM 2025\VistaDB.5.NET40.dll'
$conn = New-Object VistaDB.Provider.VistaDBConnection('Data Source=C:\ALPHACAM\LICOMDAT\Automation Manager Data\AutomationManager.vdb5')
$conn.Open()
$tx = $null
try {
    $job = $JobName.Replace("'", "''")
    $cmd = $conn.CreateCommand()
    $cmd.CommandText = "SELECT JobDetailID FROM AM_JobDetails WHERE JobName = '$job'"
    $r = $cmd.ExecuteReader()
    $jdId = $null
    if ($r.Read()) { $jdId = [int]$r.GetValue(0) }
    $r.Close()
    if ($null -eq $jdId) {
        Write-Output "sheet_rows: 0"
        exit 0
    }
    $tx = $conn.BeginTransaction()
    try {
        $del = $conn.CreateCommand()
        $del.Transaction = $tx
        $del.CommandText = "DELETE FROM AM_SelectedSheets WHERE fkJobDetailID = $jdId"
        $del.ExecuteNonQuery() | Out-Null
        $count = 0
        if ($Sheets) {
            foreach ($pair in ($Sheets -split ',')) {
                $parts = $pair -split ':'
                $sheetId = [int]$parts[0]
                $qty = [int]$parts[1]
                $ins = $conn.CreateCommand()
                $ins.Transaction = $tx
                $ins.CommandText = "INSERT INTO AM_SelectedSheets (fkJobDetailID, SelectedSheetID, Quantity) VALUES ($jdId, $sheetId, $qty)"
                $ins.ExecuteNonQuery() | Out-Null
                $count++
            }
        }
        $tx.Commit()
    } catch {
        if ($null -ne $tx) { $tx.Rollback() }
        throw
    }
    Write-Output ("sheet_rows: " + $count)
} finally {
    $conn.Close()
}
