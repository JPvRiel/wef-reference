Write-Output "Getting metadata of event providers. Please wait..."
New-Item -ItemType Directory -Force -Path '.\Extracted'
# NOTE: 
# - Due to permission error related bugs with some manifests, even as admin, Get-WinEvent is not suitable for gathering all provider metadata
# - Even with -ErrorAction 'Continue', enumeration stops and fails to assign to the variable when 'System.UnauthorizedAccessException' occurs.
#$allProvidersMetadata = Get-WinEvent -ListProvider '*' -ErrorAction 'Continue' -ErrorVariable getWinEventErrors
$allProvidersMetadata = [System.Collections.ArrayList]@()
$providerMetadataExceptions = [System.Collections.ArrayList]@()
$eventSession = [System.Diagnostics.Eventing.Reader.EventLogSession]::GlobalSession
$eventProviderNames = $eventSession.GetProviderNames();
foreach ($eventProviderName in $eventProviderNames) {
    $providerMetadataException = $null
    try {
      # Calling Get-WinEvent is much slower than createing a new object
      #$providerMetadata = Get-WinEvent -ListProvider $eventProviderName -ErrorAction 'Stop'
      $providerMetadata = New-Object -TypeName System.Diagnostics.Eventing.Reader.ProviderMetadata -ArgumentList $eventProviderName -ErrorAction 'Stop'
      $allProvidersMetadata += $providerMetadata
    }
    catch {
      $providerMetadataException = [PSCustomObject]@{
        ProviderName = $eventProviderName
        Exception = $_.Exception
      }
      $providerMetadataExceptions.Add($providerMetadataException)
      Write-Error "Provider metadata exception for $eventProvider." -ErrorAction 'Continue'
      $_
    }
}
$providerCount = $allProvidersMetadata.count
$errorCount = $providerMetadataExceptions.count
if ($errorCount -gt 0) {
  # Report errors.
  Write-Warning "Attempted export of $errorCount provider metadata encountered errors."
  Write-Output "Summary of inner exception messages:"
  $providerMetadataExceptions.Exception.InnerException.Message | Group-Object -NoElement | Sort-Object  -Descending -Property Count | Format-Table -AutoSize
  # Log simple error messages as text.
  $errorFile = '.\Extracted\Get-WinEvent.err.log.txt'
  # Out-File fails to strip control characters for color output, so remove them with regex as a workaround.
  #$providerMetadataExceptions | ForEach-Object { $_ -replace '\[\d+(;\d+)?m' } | Out-file -FilePath $errorFile
  $providerMetadataExceptions | %{ "Provider: $($_.ProviderName). Exception: $($_.Exception)" } | Out-file -FilePath $errorFile
  # Extract properties for CSV output
  $calcProps = @(
    @{n='ProviderName';e={$_.ProviderName}},
    @{n='Exception.InnerException.Message';e={$_.Exception.InnerException.Message}}
  )
  # Log errors as csv
  $errorFileCsv = '.\Extracted\Get-WinEvent.err.log.csv'
  $providerMetadataExceptions | Select-Object -Property $calcProps | Export-Csv -Path $errorFileCsv
  Write-Output "See `"$errorFile`" for messages and `"$errorFileCsv`" for a more detailed breakdown of errors."
}
# Export as JSON.
Write-Output "Exporting metadata of $providerCount providers. Please wait..."
$allProvidersMetadata | ConvertTo-Json -Depth 10 | Out-File '.\EventMetadata.json'
Compress-Archive -Force -Path '.\EventMetadata.json' -DestinationPath '.\Extracted\EventMetadata.json.zip'
Remove-Item -Path '.\EventMetadata.json'
Write-Output "Exported metadata from $providerCount providers to `".\Extracted\EventMetadata.json.zip`"."