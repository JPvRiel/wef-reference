# Event query tests

A few examples to demonstrate limitations and behaviour of the event query mechanisms.

`Test-EventQueryLimitsAndMechanisms.ps1` loops over test directories with QueryList XML files and uses `..\Test-EventQueryXmlFile.ps1` to test the lists using the time range of yesterday (24hr).

## overlap

Demonstrates that multiple `Query` items (nodes) in the `QueryList` with overlapping or duplicate event selection do not cause duplicated events to be returned.
