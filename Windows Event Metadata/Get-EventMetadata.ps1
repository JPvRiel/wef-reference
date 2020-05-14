Write-Output "Getting metadata of event providers. Please wait..."
New-Item -ItemType Directory -Force -Path '.\Extracted'
$allProvidersMetadata = Get-WinEvent -ListProvider '*' -ErrorAction 'Continue' -ErrorVariable getWinEventErrors
$providerCount = $allProvidersMetadata.count
$errorCount = $getWinEventErrors.count
if ($errorCount -gt 0) {
  # Report errors.
  Write-Warning "Attempted export of $errorCount provider metadata encounted errors."
  Write-Output "Summary of inner exception messages:"
  $getWinEventErrors.Exception.InnerException.Message | Group-Object -NoElement | Sort-Object  -Descending -Property Count | Format-Table -AutoSize
  # Log simple error messages as text.
  $errorFile = '.\Extracted\Get-WinEvent.err.log.txt'
  # Out-File fails to strip control characters for color output, so remove them with regex as a workarround.
  $getWinEventErrors | ForEach-Object { $_ -replace '\[\d+(;\d+)?m' } | Out-file -FilePath $errorFile
  # Log errors as csv
  $errorFileCsv = '.\Extracted\Get-WinEvent.err.log.csv'
  # Extract provider name and other properties for CSV output
  $reProvider = '^Could not retrieve information about the (\S+) provider'
  $calcProps = @(
    @{n='Exception.Message';e={$_.Exception.Message}},
    @{n='Exception.InnerException.Message';e={$_.Exception.InnerException.Message}},
    @{n='Exception.Message.Provider';e={if ($_.Exception.Message -match $reProvider) {$Matches[1]} else {$null}}},
    @{n='FullyQualifiedErrorId';e={$_.FullyQualifiedErrorId}}
  )
  $getWinEventErrors | Select-Object -Property $calcProps | Export-Csv -Path $errorFileCsv
  Write-Output "See `"$errorFile`" for messages and `"$errorFileCsv`" for a more detailed breakdown of errors."
}
# Export as JSON.
Write-Output "Exporting metadata of $providerCount providers. Please wait..."
$allProvidersMetadata | ConvertTo-Json -Depth 10 | Out-File '.\EventMetadata.json'
Compress-Archive -Force -Path '.\EventMetadata.json' -DestinationPath '.\Extracted\EventMetadata.json.zip'
Remove-Item -Path '.\EventMetadata.json'
Write-Output "Exported metadata from $providerCount providers to `".\Extracted\EventMetadata.json.zip`"."