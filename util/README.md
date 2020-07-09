# Util

Misc. scripts related to managing windows event subscription files or metadata.

## Testing Subscription Query Lists

E.g. test a subscription file:

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
