# Util

Misc. scripts related to managing windows event subscription files or metadata.

## Testing Subscription Query Lists

E.g. test a subscription files from the project root/parent directory:

```PowerShell
.\util\Test-EventQueryXmlFile.ps1 -XmlFilePath '.\nsacyber\Event-Forwarding-Guidance\Subscriptions\NT6\AccountLogons.xml'
```

E.g. test a query list file such as given in the Microsoft reference:

```PowerShell
.\util\Test-EventQueryXmlFile.ps1 -XmlFilePath '.\microsoft refactored\Appendix E - Annotated baseline subscription event query (refactored).xml'
```

E.g. test each individual query ID as a unit (instead of the full query list):

```PowerShell
.\util\Test-EventQueryXmlFile.ps1 -XmlFilePath '.\microsoft\Appendix E - Annotated baseline subscription event query.xml' -UnitTest 'EachQuery'
```

Note:

- `Get-Help Test-EventQueryXmlFile.ps1` will provide info on extra arguments, such as limiting the date and time range to select events for (which is done via injecting a time range Suppress element).
- `Test-EventQueryXmlFile.ps1` is also called by a testing script in the the `test` sub-directory.
