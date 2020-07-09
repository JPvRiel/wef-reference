# Microsoft Subscription Guidance Refactored

Some of the queries in the Microsoft guide are for deprecated software like EMET.

## Some products limit the size of the query

QRadar WinCollect has a 4096 character limitation on the XML query list given to it. Combining and compacting the queries suggested by Microsoft helps fit it within this limit.

## Considerations

### Authentication events

For event ID 4624, both the "Baseline" and "Suspect" microsoft reference query lists omit LogonType 5 used for service accounts.
