param(
  [Parameter(Mandatory)][String]$Path,
  [String]$OutputPath=$null,
  [Switch]$DontReplaceXmlDataXPathNewlinesWithSpace
)

if (-not $OutputPath) {
  $OutputPath = "$((Get-Item $Path).Basename).compact.xml"
}

$ErrorActionPreference = 'Stop'

# Get and measure input
$InputXmlLines = Get-Content -Path $Path
$MeasuredInputXml = $InputXmlLines | Measure-Object -Line -Character
$InputLineCount = $MeasuredInputXml.Lines
$InputCharCount = $MeasuredInputXml.Characters
Write-Output "$InputLineCount lines and $InputCharCount characters input from '$Path'."

# Get content returns a collection of strings where newlines are lost. 
# Needed for multi-line regex to work latter, reassemble it with newlines.
# Use Microsoft CRLF convention
$InputXml = $InputXmlLines -join "`r`n" 
$InputValidatedXml = $null
try {
  $InputValidatedXml = [xml]$InputXml
  Write-Debug "'$Path' input is valid XML."
}
catch {
  Write-Error "Unable to interpret '$Path' as XML."
  throw $_
}

$OutputXML = $null
Write-Verbose 'Removeing XML comments.'
$OutputXML = $InputXml -replace '(?ms)<!--.*?-->', ''
Write-Verbose 'Removeing all preceeding or trailing whitespace'
$OutputXML = $OutputXML -replace '(?m)^\s*', ''
$OutputXML = $OutputXML -replace '(?m)\s*$', ''
Write-Verbose 'Removeing duplicated newlines'
$OutputXML = $OutputXML.Replace("(?ms)`n*", "`n")
Write-Verbose 'Removeing newlines adjacent to XML elements'
$OutputXML = $OutputXML.Replace("`n<", '<')
$OutputXML = $OutputXML.Replace(">`n", '>')
if (-not $DontReplaceXmlDataXPathNewlinesWithSpace)
{ Write-Verbose 'Compacting XPath newlines'
  # lines starting or ending with 'and' and 'or' must be replaced with a single space.
  $OutputXML = $OutputXML.Replace("`nor", ' or')
  $OutputXML = $OutputXML.Replace("or`n", 'or ')
  $OutputXML = $OutputXML.Replace("`nand", ' and')
  $OutputXML = $OutputXML.Replace("and`n", 'and ')
  # other newlines can be fully replaced.
  $OutputXML = $OutputXML.Replace("`n", '')
}

try {
  $OutputValidatedXml = [xml]$OutputXML
  Write-Debug "'$OutputPath' output is valid XML."
}
catch {
  Write-Error "Unable to interpret '$OutputPath' as XML."
  throw $_
}

$MeasuredOutputXML= $OutputXML | Measure-Object -Line -Character
$OutputLineCount = $MeasuredOutputXML.Lines
$OutputCharCount = $MeasuredOutputXML.Characters
$OutputXML | Out-File -FilePath $OutputPath
Write-Output "$OutputLineCount lines and $OutputCharCount characters output to '$OutputPath'."