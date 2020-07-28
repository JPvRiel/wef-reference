[xml]$x = Get-Content '.\Event 4624 simple single query duplicated.xml'
$e = Get-WinEvent -FilterXml $x
Write-Output "Duplicated record IDs (empty line indicates none):"
$e | Group-Object RecordId -NoElement | ?{ $_.Count -gt 1 }
