# Windows Event Metadata

TL;DR: The file likely to be me most useful as a reference table of Windows events is `./flattened/metadata_by_event_flattened.csv.zip`.

Running both the PowerShell and Python script is suggested to update and overwrite the metadata to be more representative of your own Windows deployment.

## Extracting windows event metadata

This folder contains a simple PowerShell script, `Get-EventMetadata.ps1`, which can to extract event provider and event ID metadata via `Get-WinEvent` `-ListProvider`, and then serialises / dumps the metadata output as a compressed JSON file, `.\Extracted\EventMetadata.json.zip`.

Accuracy will depend on the source windows system being run, given different Windows versions and different install packages/optional components add providers and events.

`Get-EventMetadata.ps1` was tested on PowerShell 5.1 and 7.0. Older versions might not work.

### Provider metadata errors are common

PowerShell errors for `Get-WinEvent` are exported to `.\Extracted\Get-WinEvent.err.log.txt` as simple messages and `.\Extracted\Get-WinEvent.err.log.csv` for neater categorisation by provider and inner exception message.

I'm yet to run `Get-EventMetadata.ps1` on any Windows system without at least a few errors. Due to the complexity of the Windows event API and eventing schema, errors seem quite common. On my sample Windows 10 system, I encountered 46 errors with the following 3 inner exception messages.

```console
Count Name
----- ----
   31 The system cannot find the file specified.
   11 The specified resource type cannot be found in the image file.
    4 The data is invalid.
```

## Flattened metadata views by Providers and Events

A second Python script, `metadata.py` uses pandas flatten/normalise the deeply nested node/object hierarchy of log names, providers and events. It also flattens lists of complex nodes/objects into a simpler list of string names. It exports views to `./flattened` as:

- By event: `event_metadata.json.zip` and `event_metadata.csv.zip`.
- By provider: `provider_metadata.json.zip` and `provider_metadata.csv.zip`.

These views are imported by `../compare_wef.py` and used to lookup and cross-reference event metadata related to XML event queries that embed XPath. It helps enrich the context of XPath event queries it attempts to enumerate.

### Names for Providers, Keywords, Tasks, Opcodes and LogLinks

The windows event API has two name attribute for Providers, Keywords, Tasks, Opcodes and LogLinks, whereby a `DisplayName` is intended as human readable, and the usual `Name` or `LogName` (in the case of `LogLinks`) is better suited to programatic access, e.g. via event queries. However, in practice, the use of these related name attributes is inconsistent. Often `DisplayName` is omitted or the same as the name. E.g. related to the PowerShell provider:

```json
{
  "Tasks": [
    {
      "Name": "Engine Health\r\n",
      "Value": 1,
      "DisplayName": "Engine Health",
      "EventGuid": "00000000-0000-0000-0000-000000000000"
    },
    {
      "Name": "Command Health\r\n",
      "Value": 2,
      "DisplayName": "Command Health",
      "EventGuid": "00000000-0000-0000-0000-000000000000"
    }
  ]
}
```

becomes:

```json
{
  "Tasks.Name": [
    "Engine Health",
    "Command Health"
  ]
}
```

### Windows event metadata discrepancies for undefined empty and null values

When parsing and flattening, the null named values are removed from lists and empty lists are produced instead.

See `metadata_issues.ipynb` for more detail. TL;DR: the representation of a Keyword metadata item being undefined varies widely and can be a None value, an empty list, or a list with a item that has both the 'Name' and 'DisplayName' keys set to a null value.

### LogName vs DisplayName and how it relates to the view in Windows Event Viewer vs. XML event queries

Since the windows event viewer will use the `DisplayName` of a log when available, while XML event queries use the `LogName` as the Path attribute, there can be some confusion when specifying the Path. `metadata_by_loglink_name_missmatch.csv.zip` is produced to enumerate cases where what you see in the Event Viewer won't match what needs to be specified in as the event selection Path.

## Additional reference files

`./Related/WindowsSecurityAuditEvents.csv` is downloaded from Microsoft as an alternate example, but is limited to only security audit log events.

This was converted to CSV from WindowsSecurityAuditEvents.xlsx. WindowsSecurityAuditEvents.xlsx was obtained from the page [Download Windows security audit events from Official Microsoft Download Center](https://www.microsoft.com/en-us/download/details.aspx?id=50034).
