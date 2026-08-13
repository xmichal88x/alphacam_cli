param(
    [string]$JobName,
    [string]$Column,
    [string]$Value
)
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$allowedColumns = @('fkCustomerID','PurchaseOrderNumber','DueDate','JobDescription')
if ($allowedColumns -cnotcontains $Column) {
    Write-Error "Column '$Column' is not allowed. Allowed: $($allowedColumns -join ', ')"
    exit 1
}
Add-Type -Path 'C:\Program Files\Hexagon\ALPHACAM 2025\VistaDB.5.NET40.dll'
$conn = New-Object VistaDB.Provider.VistaDBConnection('Data Source=C:\ALPHACAM\LICOMDAT\Automation Manager Data\AutomationManager.vdb5')
$conn.Open()
try {
    $job = $JobName.Replace("'", "''")
    $column = $Column.Replace("'", "''")
    $value = $Value.Replace("'", "''")
    $cmd = $conn.CreateCommand()
    $cmd.CommandText = "SELECT JobDetailID FROM AM_JobDetails WHERE JobName = '$job'"
    $r = $cmd.ExecuteReader()
    $jdId = $null
    if ($r.Read()) { $jdId = [int]$r.GetValue(0) }
    $r.Close()
    if ($null -ne $jdId) {
        $cmd2 = $conn.CreateCommand()
        $cmd2.CommandText = "UPDATE AM_JobDetails SET [$column] = '$value' WHERE JobDetailID = $jdId"
        Write-Output ("rows: " + $cmd2.ExecuteNonQuery())
    } else {
        Write-Output "rows: 0"
    }
} finally {
    $conn.Close()
}
