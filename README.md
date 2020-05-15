# Windows Event Forwarding References

This project collects and compares various references related to Windows Event Forwarding (WEF), which I also refer to as Windows Event Log Collection (WELC).

`wef-reference.xlsx` provides worksheets that cross-reference events with XML event query lists published by Microsoft, the NSA and Palantir.

It's intended to remove some of the tedium of comparing and deciding which events should or should not be collected for cyber security related event forwarding subscriptions.

- While there's much room for improvement (see "Limitations" and "Future work"), it's currently a usable consolation of which event ID's to focus on.
- E.g. a minimum priority of events to collect would be where 2 or more references recommend it, with special attention to the Microsoft Baseline set.
- It helps showcase that important security events are not simply located in the Security event log path.
- Futhermore, simply collecting all events from the Security log will likely overburden log collection / SIEM platforms.

## Updating references

### Updating Windows event metadata

`wef-reference.xlsx` can be updated with sample event metadata from your own system. This would require running scripts in the following order

1. `Get-EventMetadata.ps1`: execute from `Windows Event Metadata`.
2. `metadata.py`: execute from `Windows Event Metadata`.
3. `compare_wef`: execute from project root. It sources metadata from `Windows Event Metadata`.
4. Open `wef-reference.xlsx` and re-fresh data.

Note, Excel's Power Query data source `File.Contents()` function doesn't currently support relative paths, but a common workaround has been put in place to calculate the absolute path needed. So it should be possible to refresh the data without having to re-import it manually.

### Updating event query / subscription references

The [`palantir`](./palantir/) and [`nsacyber`](./nsacyber/) sources are added as git submodules, so when any upstream changes occur in those projects, the submodules need to be rerun and steps 3 and 4 above  

The [`microsoft`](./microsoft/) query lists are localted in the Appendices  of the documentation site (a markdown file) and manually extracted into this repo.

## Dependencies

- PowerShell for extracting event metadata from your own environment (`Windows Event Metadata` sub directory).
- Python3.7+ (haven't tested lower versions) and various modules (refer to python script file `import`'s to see which modules are needed).
  - All modules/packages I needed were available with Anaconda, but pip should work as well.

## Comparisons

Microsoft's references split their example in two, one "baseline" and the other extra category "suspect".

The NSA and Palantir references split event collection into a dozen or more subscription configuration files.

Based on an ['wecsvc stops working after a while' issue comment](https://github.com/palantir/windows-event-forwarding/issues/35#issuecomment-498737540), splitting collection into too many subscriptions may have a negative impact as each subscription appears to use it's own separate WinRM/WSMan connection.

A script `compare_wef.py` was written to compare the xml configuration samples provided by including them as git sub-modules and then parsing their subscription / query list files:

- Microsoft: [`microsoft`](./microsoft/)
- NSA: [`nsacyber`](./nsacyber/)
- Palantir: [`palantir`](./palantir/)

See `./compare_wef.py -h` for a few options to control metadata cross-referencing to events defined/implied by queries.

The output files of the script are placed in `export`.

- Referenced subscription file sets are consolidated and summarized into single yaml files named per reference, e.g. `<reference>_wef_subscriptions.yml`.
- Unified views of events accross all references are produced as `query_combinations` files in both `.yaml` and `.json` formats.
  - These are explicitly labeled nested objects suitable for importing as pandas data frames.
- Implicitly indexable versions are also produced as `query_combinations_index` files in both  `.yaml` and `.json` formats.
  - These could be simpler for use with python dict type lookups where property values are named as keys.
- Flattend CSV versions normalized by events and by reference are generated.
- YAML intended as human-readable, JSON as a more common format suited to integrations, and CSV for importing into spreadsheet applications.

## Enriching event queries with event metadata

The subfolder [`Windows Event Metadata`](./Windows%20Event%20Metadata/) contains a PowerShell script to exporting event providers and event metadata.

The output of the script is imported by `compare_wef.py` to enrich and improve enumerating the event IDs that the various XPath queries would explicitly or implicitly select or suppress.

## Limitations

This "best-effort" project has the following known limitations:

- The XPath syntax is not parsed by a formal XPath parsing engine to decode providers, event IDs, and levels.
  - Regular expressions are used to guess at specific event ID and event levels specified within XPath queries.
  - Obviously this which might fail to properly capture unforeseen variations, but it worked well enough for my use case.
  - Refactoring to use [eulxml.xpath](https://eulxml.readthedocs.io/en/latest/xpath.html) is a potential enhancement.
- The metadata reference is extracted from a sample Windows 10 system and limited to the specific providers and event versions defined on that system.
  - Some of the technologies referenced in queries were not deployed on the sample system and could result in incomplete event enumeration or nullified metadata lookups for some queries.
  - The current sample of metadata was extracted from a Windows 10 1909 system.
  - It's preferable to run the PowerShell event provider and metadata script on the target environment and regenerate the metadata.
  - Regratably, I only located the [Windows-Event-Log-Messages](https://github.com/nsacyber/Windows-Event-Log-Messages) resource after writing my own simple metadata extract process.
    - `WELM` it's likely a superior way to extract the event metadata.
- Each subscription source core reference directory is hardcoded in the script and adding more sources requires modifying the script. This could be parameterised in future.

### Future work

Obviously it'd be nice to see this extended with other published guidance / query / subscription examples. In addition to that, the following cross-referencing would be good:

- Refactor `compare_wef` to make use of `WELM`, as per [Windows-Event-Log-Messages](https://github.com/nsacyber/Windows-Event-Log-Messages), instead of own custom solution in `Windows Event Metadata`.
- [Appendix L: Events to Monitor](https://docs.microsoft.com/en-us/windows-server/identity/ad-ds/plan/appendix-l--events-to-monitor) is not yet compared
  - But it was not published as a Query List/subscription...
  - It adds a "Potential Criticality" rating for events.
- Search for a usable data reference source (ie. CSV or JSON) that allows mapping event IDs to specific windows audit policy settings and cross-reference that.
- Search for a reference related to advanced object access auditing.
  - Specifically find extended guidance on which objects (e.g. file, registry) should have System ACLs (SACLs) set.
  - Object access auditing is either very noisy (global/basic), or requires onerous work creating System ACLs to set auditing per object/container (advanced).

## Observations

### Providers without event metadata/manifests

With my Windows 10 sample system, the following providers did not event metadata to enumerate:

| Path                                                            | Provider                                            |
|:----------------------------------------------------------------|:----------------------------------------------------|
| Security                                                        | AD FS Auditing                                      |
| Application                                                     | EMET                                                |
| Application                                                     | Windows Error Reporting                             |
| Application                                                     | Duo Security                                        |
| Windows PowerShell                                              | PowerShell                                          |
| AD FS/Admin                                                     | AD FS                                               |
| AD FS Tracing/Debug                                             |                                                     |
| Duo Authentication for AD FS                                    |                                                     |
| Microsoft-Windows-TPM-WMI                                       |                                                     |
| OAlerts                                                         | Microsoft Office 16 Alerts                          |
| OAlerts                                                         | Microsoft Office 14 Alerts                          |
| Microsoft-Windows-TerminalServices-Gateway/Admin                |                                                     |
| Microsoft-Windows-TerminalServices-Gateway/Operational          |                                                     |
| Microsoft-Windows-TerminalServices-ClientUSBDevices/Operational | Microsoft-Windows-TerminalServices-ClientUSBDevices |
| Microsoft-Windows-TerminalServices-Printers/Operational         | Microsoft-Windows-TerminalServices-Printers         |
| Autoruns                                                        |                                                     |
| Microsoft-Windows-SMBClient/Security                            |                                                     |

### Log Links and Query Log Path

My assumption was that the LogLinks attribute for each provider and the LogLink attribute for events should match the `Path` attribute used in XML queries. Note that providers can have multiple LogLinks, i.e. the events are split/logged to different Paths/Log Names. E.g. from my sample metadata set, I ran the following to see providers with the largest number of Log Links:

```python
print(provider_metadata[provider_metadata['LogLinks.Count'] == provider_metadata['LogLinks.Count'].max()][['Name', 'LogLinks.Name', 'LogLinks.Count']].to_markdown())
```

And the result for the most linked provier names was:

| Name | LogLinks.Name | LogLinks.Count |
|:-----|:--------------|:---------------|
| Microsoft-Windows-Application-Experience | 'Microsoft-Windows-Application-Experience/Compatibility-Infrastructure-Debug', 'Microsoft-Windows-Application-Experience/Program-Compatibility-Assistant/Analytic', 'Microsoft-Windows-Application-Experience/Program-Compatibility-Assistant/Trace', 'Microsoft-Windows-Application-Experience/Program-Compatibility-Assistant', 'Microsoft-Windows-Application-Experience/Program-Telemetry', 'Microsoft-Windows-Application-Experience/Program-Inventory', 'Microsoft-Windows-Application-Experience/Steps-Recorder', 'Microsoft-Windows-Application-Experience/Program-Compatibility-Troubleshooter' | 8 |
| Microsoft-Windows-MF | 'MF_MediaFoundationDeviceProxy', 'MF_MediaFoundationDeviceMFT', 'MediaFoundationPipeline', 'MediaFoundationContentProtection', 'MediaFoundationAsyncWrapper', 'MediaFoundationDS', 'MediaFoundationSrcPrefetch', 'MediaFoundationMP4' | 8 |
| Microsoft-Windows-SMBClient | 'Microsoft-Windows-SMBClient/HelperClassDiagnostic', 'Microsoft-Windows-SMBClient/ObjectStateDiagnostic', 'Microsoft-Windows-SMBClient/Operational', 'Microsoft-Windows-SMBClient/Analytic', 'Microsoft-Windows-SmbClient/Diagnostic', 'Microsoft-Windows-SmbClient/Connectivity', 'Microsoft-Windows-SmbClient/Security', 'Microsoft-Windows-SmbClient/Audit' | 8 |
| Microsoft-Windows-Win32k | 'Microsoft-Windows-Win32k/Tracing', 'Microsoft-Windows-Win32k/UIPI', 'Microsoft-Windows-Win32k/Power', 'Microsoft-Windows-Win32k/Concurrency', 'Microsoft-Windows-Win32k/Render', 'Microsoft-Windows-Win32k/Messages', 'Microsoft-Windows-Win32k/Contention', 'Microsoft-Windows-Win32k/Operational' | 8 |
| Microsoft-Windows-Shell-AuthUI | 'Microsoft-Windows-Authentication User Interface/Operational', 'Microsoft-Windows-Shell-AuthUI-CredUI/Diagnostic', 'Microsoft-Windows-Shell-AuthUI-Logon/Diagnostic', 'Microsoft-Windows-Shell-AuthUI-Common/Diagnostic', 'Microsoft-Windows-Shell-AuthUI-Shutdown/Diagnostic', 'Microsoft-Windows-Shell-AuthUI-CredentialProviderUser/Diagnostic', 'Microsoft-Windows-Shell-AuthUI-BootAnim/Diagnostic', 'Microsoft-Windows-Shell-AuthUI-LogonUI/Diagnostic' | 8 |

## References

### Primary references

- Microsoft:
  - [Use Windows Event Forwarding to help with intrusion detection](https://docs.microsoft.com/en-us/windows/security/threat-protection/use-windows-event-forwarding-to-assist-in-intrusion-detection) is Microsoft's guidance on setting up WEF with a "basline" and extra "suspect" set of events to collect.
  - [Appendix L: Events to Monitor](https://docs.microsoft.com/en-us/windows-server/identity/ad-ds/plan/appendix-l--events-to-monitor) is Microsoft's recommendation on events to monitor Active Directory for Signs of Compromise. It's based on the following reference:
    - [Monitoring Active Directory for Signs of Compromise](https://docs.microsoft.com/en-us/windows-server/identity/ad-ds/plan/security-best-practices/monitoring-active-directory-for-signs-of-compromise)
  - [Best practice for configuring EventLog forwarding in Windows Server 2016 and Windows Server 2012 R2](https://support.microsoft.com/en-us/help/4494356/best-practice-eventlog-forwarding-performance)
- Palantir:
  - [Palantir: Windows Event Forwarding Guidance](https://github.com/palantir/windows-event-forwarding) provides a more comprehensive public reference example for configuring WEF (Windows Event Forwarding).
    - Palantir’s WEF library contains a curated series of subscriptions to examine and adapt, combining recommendations from Microsoft and the NSA.
    - It suggests using custom event channels to group and catagorise events.
  - [Palantir: Windows Event Forwarding for Network Defense](https://medium.com/palantir/windows-event-forwarding-for-network-defense-cb208d5ff86f) is the blog post introducing Palantir's approach.
- NSA:
  - [NSA Event Forwarding Guidance](https://github.com/nsacyber/Event-Forwarding-Guidance) provides example subscriptions and custom windows event views. It appears to split subscriptions into specific detection use-cases and scenarios.
  - [Spotting the Adversary with Windows Event Log Monitoring](https://apps.nsa.gov/iaarchive/library/reports/spotting-the-adversary-with-windows-event-log-monitoring.cfm) is the paper presenting the NSA approach.
  - [Windows-Event-Log-Messages](https://github.com/nsacyber/Windows-Event-Log-Messages)
    - Provides scripts to automate extracting windows event message metadata.

### Other references

General background, tools and methods related to windows eventing:

- [MSDN Wecutil.exe](https://msdn.microsoft.com/en-us/library/bb736545(v=vs.85).aspx).
- [Event Queries and Event XML](https://docs.microsoft.com/en-us/previous-versions/bb399427(v=vs.90))
- [Technet Get-WinEvent](https://technet.microsoft.com/en-us/library/hh849682.aspx).
- [Best practice for configuring EventLog forwarding in Windows Server 2012 R2](https://support.microsoft.com/en-us/help/4494356/best-practice-eventlog-forwarding-performance).
  - Note, "Improves Event Forwarding scalability to ensure thread safety and increase resources." references KB4537806 and KB4537818 to improve handling more event forwarding subscribers per collection server.
- [Windows Event Forwarding: export and import subscriptions](http://godlessheathenmemoirs.blogspot.co.za/2013/05/windows-event-forwarding-export-and.html).
- [Creating custom event forwarding logs](https://blogs.technet.microsoft.com/russellt/2016/05/18/creating-custom-windows-event-forwarding-logs/)
- [psEventLogWatcher](https://archive.codeplex.com/?p=pseventlogwatcher) has useful code samples for dealing with forwarded event bookmarks.
- [WEFFLES](https://github.com/jepayneMSFT/WEFFLES) has examples for using Windows Event Forwarding and PowerBI to do threat hunting and incorporated the `EventLogWatcher.psm1` module from 'psEventLogWatcher'.

References related to problems with eventing and event subscriptions:

- [The Windows Event Forwarding Survival Guide](https://hackernoon.com/the-windows-event-forwarding-survival-guide-2010db7a68c4) provides examples of subscription error messages that occur in the `Microsoft-Windows-Eventlog-ForwardingPlugin` Event Log Channel.
- [Windows event forwarding and missing event text](https://www.gorlani.com/articles/wef.php) explains how to correct issues with binary XML (non-rendered) events missing DLLs that allow a collector to render the event.
- [Lessons Learned: Winlogbeat & Forwarded Events – no event description](http://blog.davidvassallo.me/2017/11/18/lessons-learned-winlogbeat-forwarded-events-no-event-description/) describes how winlogbeat can be configured for winlogbeat to render the event text by setting `event_logs.forwarded: false` (which is counter intuitive...)
- [A Better Way To Search Events](https://powershell.org/2019/08/a-better-way-to-search-events/) provides some XPath filter examples on EventData and using Get-WinEvent in PowerShell.
- [XPath 1.0 limitations](https://docs.microsoft.com/en-us/windows/win32/wes/consuming-events#xpath-10-limitations) notes how microsoft only implimented a subset of XPath v1.0 features.

Security event description resources:

- [Windows security audit events](https://www.microsoft.com/en-us/download/details.aspx?id=50034)
- [Windows 10 and Windows Server 2016 security auditing and monitoring reference](https://www.microsoft.com/en-us/download/details.aspx?id=52630)
- [Description of security events in Windows 7 and in Windows Server 2008 R2](https://support.microsoft.com/en-us/help/977519/description-of-security-events-in-windows-7-and-in-windows-server-2008)
- [Getting a Provider's Metadata](https://docs.microsoft.com/en-gb/windows/win32/wes/getting-a-provider-s-metadata-#getting-a-providers-metadata)

## Licenses

### License for this repository

This project more or less matches the licenses of the sources it incorporates:

- Data and information licensed under Creative Commons [Attribution 4.0 International (CC BY 4.0)](./LICENSE.txt)
- Code (scripts) under the MIT License (./LICENSE-CODE.txt).

### Related license for primary references included here

Licence files are included within each source directory.
| Reference directory | License |
| - | - |
| [`microsoft`](./microsoft/) | Creative Commons [Attribution 4.0 International (CC BY 4.0)](https://creativecommons.org/licenses/by/4.0/) and "MIT License" for code. |
| [`nsacyber`](./nsacyber/) | Creative Commons [CC0 1.0 Universal](https://creativecommons.org/publicdomain/zero/1.0/) |
| [`palantir`](./palantir/) | "MIT License" |
