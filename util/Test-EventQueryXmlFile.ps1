<#
.SYNOPSIS
  Test queries defined in a QueryList or Subscription XML file.
.DESCRIPTION
  Queries events from computers using parallel jobs and then outputs a summary about the events found for a given select query, query item or query list over a specific time window (-StartDateTime and -EndDateTime).
.PARAMETER Computers
  A specific remote system or list of systems to query. Defaults to the current system (which reqires remote powershell to function). 
.PARAMETER MaxEvents
  The overall upper limit of events to return. This limit is shared by the entire query list set.
.PARAMETER TestUnit
  TestUnit can be either of 'QueryList', 'EachQuery', or 'EachSelect' with the latter two options useful for independent tests of the QueryList components.
.PARAMETER StartDateTime
  The newest event timestamp to look for events. Assumes the source query file does not already have it's own time filters applied.
.PARAMETER EndDateTime
  The oldest event timestamp to look for events. Assumes the source query file does not already have it's own time filters applied.
.PARAMETER JobTimeoutSec
  The maximum number of seconds to wait for query tests to complete. With 'EachQuery' or 'EachSelect' TestUnit, this is per query tested, not an overall timeout, so expect testing to take longer than a single timeout.
.PARAMETER CsvTestResultFile
  If specified, summary aggregate of events found per test will be output to the CSV file.
#>

param(
  [Parameter(Position=0)][Alias('ComputerName')][String[]]$Computers = @('.'),
  [Parameter(Position=1, Mandatory)][String]$XmlFilePath,
  [int]$MaxEvents = 10000,
  [String][ValidateSet('QueryList','EachQuery','EachSelect')]$TestUnit = 'QueryList',
  [switch]$SortByEventCount,
  $StartDateTime=$null,
  $EndDateTime=$null,
  $JobTimeoutSec = 900,
  $CsvTestResultFile = $null
)

$ErrorActionPreference = 'Stop'

# Build XPath and XSLT to add suppress after selects for events outside of the start to end time range (if set).
$ISO8601_UTC_FORMAT_STRING_MS = 'yyyy-MM-ddTHH:mm:ss.fffZ'
$startISO8601_UTC_ms = $null
if ($StartDateTime) {
  $startISO8601_UTC_ms = ([DateTime]$StartDateTime).ToUniversalTime().ToString($ISO8601_UTC_FORMAT_STRING_MS)
  Write-Debug "Time range: From $startISO8601_UTC_ms."
}
$endISO8601_UTC_ms = $null
if ($EndDateTime) {
  $endISO8601_UTC_ms = ([DateTime]$EndDateTime).ToUniversalTime().ToString($ISO8601_UTC_FORMAT_STRING_MS)
  Write-Debug "Time range: Until $endISO8601_UTC_ms."
}
$dateTimeSuppressXPath = $null
if ($startISO8601_UTC_ms -and $endISO8601_UTC_ms) {
  $dateTimeSuppressXPath = "*[System[TimeCreated[@SystemTime&lt;'$startISO8601_UTC_ms' or @SystemTime&gt;'$endISO8601_UTC_ms']]]"
}
elseif ($startISO8601_UTC_ms -and -not $endISO8601_UTC_ms) {
  $dateTimeSuppressXPath = "*[System[TimeCreated[@SystemTime&lt;'$startISO8601_UTC_ms']]]"
}
elseif ($endISO8601_UTC_ms -and -not $startISO8601_UTC_ms) {
  $dateTimeSuppressXPath = "*[System[TimeCreated[@SystemTime&gt;'$endISO8601_UTC_ms']]]"
}
$xsltAddDateTimeSuppress = $null
if ($dateTimeSuppressXPath) {
  Write-Debug "Time range suppress XPath: $dateTimeSuppressXPath"
  [xml]$xslAddDateTimeSuppress =
@"
<?xml version='1.0'?>
<xsl:stylesheet version='1.0' xmlns:xsl='http://www.w3.org/1999/XSL/Transform'>
  
  <!-- Identity transform -->
  <xsl:template match='@* | node()' name='identity-copy'>
    <xsl:copy>
        <xsl:apply-templates select='@* | node()'/>
    </xsl:copy> 
  </xsl:template>

  <!-- Add suppress after select -->
  <xsl:template match='Select'>
    <xsl:copy>
      <xsl:apply-templates select='@*|node()'/>
    </xsl:copy>
    <xsl:variable name='path' select='@Path'/>
    <Suppress Path='{`$path}'>$dateTimeSuppressXPath</Suppress>
  </xsl:template>

</xsl:stylesheet>
"@
  Write-Debug "XSLT:`n$($xslAddDateTimeSuppress.OuterXml)"
  $xsltAddDateTimeSuppress = [Xml.Xsl.XslCompiledTransform]::New()
  $xsltAddDateTimeSuppress.Load($xslAddDateTimeSuppress)
}

$xmlFileContent = Get-Content $XmlFilePath
# Warn about unexpected results if both source and script paramters are filtering by time.
if ($dateTimeSuppressXPath -and $xmlFileContent -match 'TimeCreated') {
  Write-Warning "'TimeCreated' was found in the file '$XmlFilePath'. This will likely conflict with StartDateTime or EndDateTime parameters given." -WarningAction 'Inquire'
}
# Look for query list within a subscription file
$xml = [xml]$xmlFileContent
if ($xml.QueryList) {
  Write-Output "Reading QueryList from file '$XmlFilePath'."
  $xmlQueryList = $xml
}
elseif ($xml.Subscription) {
  Write-Output "Reading QueryList from Subscription in file '$XmlFilePath'."
  $xmlQueryList = $xml.Subscription.Query."#cdata-section"
} else {
  Write-Error "Expected 'Subscription' or 'QueryList' root level XML node not found in '$XmlFilePath'."
}

$MeasuredInputXml = $xmlQueryList | Measure-Object -Line -Character
$InputLineCount = $MeasuredInputXml.Lines
$InputCharCount = $MeasuredInputXml.Characters
Write-Information "$InputLineCount lines and $InputCharCount characters input from '$XmlFilePath'."

# Validate and display a summary of the XML Queries and Select or Suppress XPath items.
$validatedXml = $null
$countQueries = 0
$countSelects = 0
$countSuppress = 0
try {
  $validatedXml = [xml]$xmlQueryList
  Write-Debug "'$XmlFilePath' input is valid XML."
  $QueryCount = $validatedXml.QueryList.Query.Count
  Write-Information "$QueryCount queries found."
  $QueryList = [Collections.ArrayList]@()
  foreach ($query in $validatedXml.QueryList.Query) {
    $countQueries++
    foreach ($select in $query.Select) {
      $countSelects++
      [void]$QueryList.Add(
        [PSCustomObject]@{
          QueryId = $query.Id
          Type = 'Select'
          LogPath = $select.Path
          XPath = $select.'#text'
        }
      )
    }
    foreach ($suppress in $query.Suppress) {
      $countSuppress++
      [void]$QueryList.Add(
        [PSCustomObject]@{
          QueryId = $query.Id
          Type = 'Suppress'
          LogPath = $suppress.Path
          XPath = $suppress.'#text'
        }
      )
    }
  }
  Write-Output "Query list summary table follows:"
  $QueryList | Format-Table -AutoSize -Wrap
}
catch {
  Write-Error "Unable to interpret '$XmlFilePath' as XML."
  throw $_
}
Write-Output "Summary: '$XmlFilePath' had $countQueries queries, with $countSelects select and $countSuppress suppress nodes."

$TestEventQueryScriptBlock = {
  param(
    [xml]$XmlQueryList,
    [int]$MaxEvents
  )

  try {
    $events = Get-WinEvent -FilterXML $XmlQueryList -MaxEvents $MaxEvents -ErrorAction Stop
    $eventGroups = $events | Group-Object -Property ProviderName, LevelDisplayName, Id, MachineName
    foreach ($eventGroup in $eventGroups) {
      $FirstEvent = $eventGroup.Group[-1]
      $LastEvent = $eventGroup.Group[0]
      [PSCustomObject]@{
        MachineName = $FirstEvent.MachineName
        Log = $FirstEvent.LogName
        Provider = $FirstEvent.ProviderName  
        Level = $FirstEvent.Level
        LevelName = $FirstEvent.LevelDisplayName
        Id = $FirstEvent.Id
        Count = $eventGroup.Count
        FirstTime = $FirstEvent.TimeCreated
        LastTime = $LastEvent.TimeCreated
        LastMessage = $LastEvent.Message
        XmlQueryList = $XmlQueryList.OuterXml
        Exception = $null
      }
    }
  }
  catch {
    # Return an object indicating a failure to match events
    [PSCustomObject]@{
      MachineName = $null
      Log = $null
      Provider = $null
      Level = $null
      LevelName = $null
      Id = $null
      Count = $null
      FirstTime = $null
      LastTime = $null
      LastMessage = $null
      XmlQueryList = $XmlQueryList.OuterXml
      Exception = $_.Exception.Message
    }
    if ($_.FullyQualifiedErrorId -match 'NoMatchingEventsFound') {
      # Enrich error with warnings given its likely sometimes a query may fail to match events
      Write-Warning "$($_.Exception.Message)`nFailed Query:`n$($XmlQueryList.OuterXml)"
    }
    elseif ($_.FullyQualifiedErrorId -match 'EventLogNotFoundException') {
      # Enrich the error message with a warning that all the results are affected due to a missing log source/manifest.
      Write-Error "Due to a limitation with Get-WinEvent XML query list handling, all queries fail as the command aborts if just one of the log paths defined does not exist.' `
        + 'Original exception:`n$($_.Exception.Message)`n' `
        + 'Failed query:`n$($XmlQueryList.OuterXml)" -ErrorAction 'Stop'
    }
    else {
      Write-Error "Unexpected failure.`n$($_.Exception.Message)" -ErrorAction 'Stop'
    }
  }

}


$eventGroupSummaries = [Collections.ArrayList]@()

function Invoke-TestUnitJob {
  param(
    [xml]$XmlQueryList,
    [int]$MaxEvents
  )

  # Apply time filter XSLT Suppress
  $transformedXmlQueryList = $null
  if ($xsltAddDateTimeSuppress) {
    # Create memory stream and stream writer
    $memoryStream = [IO.MemoryStream]::New(128)
    $streamWriter = [IO.StreamWriter]::New($memoryStream, [Text.Encoding]::UTF8Encoding)
    $xmlWriterSettings = [System.Xml.XmlWriterSettings]::new()
    $xmlWriterSettings.OmitXmlDeclaration = $true
    $xmlWriterSettings.Indent = $true
    $xmlWriter = [System.XML.XmlWriter]::Create($streamWriter, $xmlWriterSettings)
    # Transform into a memory stream
    $xsltAddDateTimeSuppress.Transform($XmlQueryList, $null, $xmlWriter)
    $xmlWriter.Flush()
    $xmlWriter.Close()
    # Read back from the memory stream
    $memoryStream.Position = 0
    $streamReader = [IO.StreamReader]::New($memoryStream, [Text.Encoding]::UTF8Encoding)
    [xml]$transformedXmlQueryList = $streamReader.ReadToEnd()
    Write-Debug "Date range inserted into Query List:`n$($transformedXmlQueryList.OuterXml)"
    $streamReader.Close()
    $memoryStream.Dispose()
  }
  else {
    $transformedXmlQueryList = $XmlQueryList
  }

  # Start job
  $job = Invoke-Command -AsJob -JobName 'TestUnitJob' -ComputerName $Computers -ScriptBlock $TestEventQueryScriptBlock -ArgumentList $transformedXmlQueryList, $MaxEvents
  $jobState = ($job | Wait-Job -TimeoutSec $JobTimeoutSec).State
  if ($jobState -notin @('Completed', 'Failed')) {
    Write-Error "Parent job was '$jobState' was incomplete before the timeout."
  }
  # FIXME: Remote jobs have child jobs? Check each child job?
  # FIXME: Warnings and errors from receive job seem to write to the console before the above output despite receive job being called later
  $jobError = $null
  $jobWarning = $null
  $jobOutput = $job | Receive-Job -ErrorVariable jobError -WarningVariable jobWarning -ErrorAction Continue
  # Display non-custom object related output.
  $jobOutput | ?{$_.GetType().Name -ne 'PSCustomObject'}
  $jobObjects = @($jobOutput | ?{$_.GetType().Name -eq 'PSCustomObject'} | Select-Object -Property * -ExcludeProperty PSComputerName,	RunspaceId, PSShowComputerName)
  if (-not ($jobError -or $jobWarning)) {
    if ($jobObjects.Count -gt 0 -and $jobObjects[0].Id) {
      Write-Output "$($jobObjects.Count) event groups found for query:`n'$($XmlQueryList.OuterXml)'"
      $jobObjects | Format-Table -Property Log, Provider, Id, LevelName, MachineName, Count, FirstTime, LastTime, LastMessage
      # Display result table, but avoid displaying if there is a single empty exception object returned.
    }
    else {
      Write-Error 'Unexpected result where there are no warnings or errors, but also no event group IDs are found in the returned job object.' -ErrorAction 'Stop'
    }
  }
  [Console]::Out.Flush()
  # store job result object output for export at the end
  [void]$eventGroupSummaries.AddRange($jobObjects)
  $job | Remove-Job -Force
  [Console]::Out.Flush()
}

# NB! Don't allow too many query jobs to run in parallel as it will overwhelm the event log service on the computer. Rather wait on each Unit Test query per computer.
Write-Output "Testing query list on $($Computers.Count) computers in parallel jobs. Event limits apply per computer. This may take a while..."
$maxEventsTotal = $MaxEvents
Switch ($TestUnit) {
  'QueryList' {
    Write-Output "The full query list will be tested and limited to $maxEventsTotal events."
    Invoke-TestUnitJob -XmlQueryList $validatedXml -MaxEvents $maxEventsTotal
  }
  'EachQuery' {
    $maxEventsPerQuery = [math]::floor($maxEventsTotal / $countQueries)
    Write-Output "Each query in the query list will be tested independently and limited to $maxEventsPerQuery events per query ($maxEventsTotal total events / $countQueries queries)."
    Write-Warning "Testing each query in isolation will take longer." -WarningAction 'Inquire'
    $queryCount = 0
    foreach ($query in $validatedXml.QueryList.Query) {
      $queryCount++
      $queryId = $query.Id
      $queryListSingleQuery = [xml]"<QueryList>$($query.OuterXml)</QueryList>"
      Write-Verbose "Testing QueryID '$queryId'."
      Invoke-TestUnitJob -XmlQueryList $queryListSingleQuery -MaxEvents $maxEventsPerQuery
    }
  }
  'EachSelect' {
    $maxEventsPerSelect = [math]::floor($maxEventsTotal / $countSelects)
    Write-Output "Each Select part of a query will be tested independently and limited to $maxEventsPerSelect events per select ($maxEventsTotal total events / $countSelects selects)."
    Write-Warning "The select unit test will not apply suppress nodes to the query."
    Write-Warning "Testing each select in isolation will take much longer." -WarningAction Inquire
    $queryCount = 0
    foreach ($query in $validatedXml.QueryList.Query) {
      $queryCount++
      $selectCount = 0
      foreach ($select in $query.Select) {
        $selectCount++
        $queryId = $query.Id
        $logPath = $select.Path
        $xPath = $select.'#text'
        $queryListSingleSelect = [xml]"<QueryList><Query Id='$queryId'>$($select.OuterXml)</Query></QueryList>"
        Write-Debug "Testing Select #$selectCount from QueryID '$queryId' with LogPath '$logPath' and XPath:`n$xPath"
        Invoke-TestUnitJob -XmlQueryList $queryListSingleSelect -MaxEvents $maxEventsPerSelect
      }
    }
  }
}

# Aggregate results
if ($eventGroupSummaries.Count -gt 0) {
  if ($SortByEventCount) {
    $eventGroupSummaries = $eventGroupSummaries | Sort-Object -Property Count -Descending
  }
  else {
    $eventGroupSummaries = $eventGroupSummaries | Sort-Object XmlQueryList, Failed, Log, Provider, Id, MachineName
  }
  if ($CsvTestResultFile) {
    $eventGroupSummaries | ConvertTo-CSV -NoTypeInformation | Out-File -FilePath $CsvTestResultFile
  }
  $sumCount = ($eventGroupSummaries | Measure-Object -Property Count -Sum).Sum
  Write-Output "$sumCount total events selected (out of max events $MaxEvents)"
}
else {
  Write-Error "No event groupings found. Event queries may have failed to select any events."
}
