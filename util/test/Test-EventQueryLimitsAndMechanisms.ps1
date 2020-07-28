$yesterday = $(Get-Date).AddDays(-1) | Get-Date -Uformat '%Y-%m-%d'
$yesterday_start = $yesterday + 'T00:00:00.000'
$yesterday_end = $yesterday + 'T23:59:59.999'

Write-Output "Testing for events in range: $yesterday_start until $yesterday_end."

$tests = @(
  'overlap'
)

foreach ($t in $tests) {
  Write-Output "# Testing: $t"
  foreach ($f in $(Get-ChildItem "$t\*.xml")) {
    ../Test-EventQueryXmlFile.ps1 -XmlFilePath $f -MaxEvents 10000 -TestUnit QueryList -StartDateTime $yesterday_start -EndDateTime $yesterday_end
  }
}
