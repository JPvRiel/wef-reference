#!/usr/bin/env python3

import os
import sys
import argparse
import colorlog
import glob
import re
import itertools
import lxml.etree
import zipfile
import json
import csv
import yaml
import numpy as np
import pandas as pd


exec('colorlog.colorlog.logging.INFO')
parser = argparse.ArgumentParser(
  description='Compare, enumerate and cross-reference windows event queries.'
)
parser.add_argument(
  '-c', '--custom', action='store_true',
  help='Include and compare an additional reference from the custom reference folder'
)
parser.add_argument(
  '-m', '--metadata', nargs='*',
  help='specify which metadata to include in enrichment (using this flag with nothing imples no metadata).',
  choices=['description', 'keywords', 'task', 'opcode', 'level', 'level.value'],
  default=['description', 'keywords', 'task', 'opcode', 'level', 'level.value']
)
parser.add_argument(
  '-d', '--metadata-full-description', action='store_true',
  help='By default the \'description\' metadata for events will be truncated upon the first newline. This enables retaining the full event description.',
  default=False
)
parser.add_argument(
  '-l','--log-level',
  help='set verbosity of console logging.',
  choices=['debug', 'info', 'warn', 'error'],
  default='info'
)

# unknown, parse_known_args() helps "ipykernel_launcher.py: error: unrecognized arguments" when run with Jupyter,
# https://stackoverflow.com/a/55329134/5472444
args, unknown = parser.parse_known_args()

## Logging to console setup
logger = colorlog.getLogger()
args
logger_level = eval(f'colorlog.colorlog.logging.{args.log_level.upper()}')
logger.setLevel(logger_level)
handler = colorlog.StreamHandler()
handler.setFormatter(colorlog.ColoredFormatter())
logger.addHandler(handler)

## Gather and check other arguments
# Map choices to expected keys produced during importing event metadata
m_choices_map = {
  'description': 'Description',
  'description-full': 'Description',
  'keywords': 'Keywords',
  'task': 'Task',
  'opcode': 'Opcode',
  'level': 'Level',
  'level.value': 'Level.Value'
}
m_include = [m_choices_map[i] for i in args.metadata]
if args.metadata_full_description and 'description' not in args.metadata:
  logger.warning(f'\'description\' was not given with \'--metadata\', but \'--metadata-full-description\' was given, so description metadata will be included in full.')
  m_include.append('Description')

## panda's options
pd.set_option('mode.chained_assignment','raise')

## YAML options
# Disable outputting references 
# https://stackoverflow.com/a/30682604/5472444
yaml.Dumper.ignore_aliases = lambda *args : True

output_dir = './export'
if args.custom:
  output_dir = './export_with_custom'

## Reference/lookup provider metadata ##
input_dir = './Windows Event Metadata/flattened'
provider_metadata = None
with zipfile.ZipFile(f'{input_dir}/metadata_by_provider_flattened.json.zip', 'r') as z:
  with z.open('metadata_by_provider_flattened.json') as f:
    provider_metadata = pd.read_json(f, orient='records')

## Expand/explode the log link names for use as a lookup
provider_metadata['LogLinks.Count'] = provider_metadata['LogLinks.Name'].apply(len)
provider_metadata_expanded_by_loglink = provider_metadata.explode('LogLinks.Name')
provider_metadata_expanded_by_loglink.rename(columns={'LogLinks.Name': 'LogLink.Name'}, inplace=True)

## Reference/lookup event metadata ##
event_metadata = None
with zipfile.ZipFile(f'{input_dir}/metadata_by_event_flattened.json.zip', 'r') as z:
  with z.open('metadata_by_event_flattened.json') as f:
    event_metadata = pd.read_json(f, orient='records')

# Metadata lookup functions

def get_provider_metadata(log_path, provider=None):
  """
  Lookup metadata of interest:
  - Log path required
  - Provider optional
  """

  metadata_columns = ['Id', 'Keywords.Name', 'Levels.Name', 'Tasks.Name', 'Opcodes.Name', 'ProviderName']
  metadata_lookup = None
  if provider:
    metadata_lookup = provider_metadata_expanded_by_loglink[
      (provider_metadata_expanded_by_loglink['LogLink.Name'] == log_path) &
      (provider_metadata_expanded_by_loglink['Name'] == provider)
    ]
  else:
    metadata_lookup = provider_metadata_expanded_by_loglink[
      provider_metadata_expanded_by_loglink['LogLink.Name'] == log_path
    ]
  return metadata_lookup[metadata_columns].to_dict('records')


def get_event_metadata(log_path, provider=None, event_id=None, level=None):
  """
  Lookup metadata of interest:
  - Log path required
  - Provider, Event ID, and Level optional
  - If event ID is specified, this supercedes the level (level is discarded)
  - If there are multiple versions, the latest version supercedes
  """

  metadata_columns = ['Id', 'Keywords.Name', 'Description', 'Level.Name', 'Level.DisplayName', 'Level.Value', 'Opcode.Name', 'Opcode.DisplayName', 'Task.Name', 'Task.DisplayName', 'Provider.Name']
  metadata_lookup = None
  # Provider given
  if provider:
    if event_id:
      metadata_lookup = event_metadata[
        (event_metadata['LogLink.LogName']==log_path) &
        (event_metadata['Provider.Name']==provider) &
        (event_metadata['Id']==event_id)
      ]
    elif level:
      metadata_lookup = event_metadata[
        (event_metadata['LogLink.LogName']==log_path) &
        (event_metadata['Provider.Name']==provider) &
        (event_metadata['Level.Value']==level)
      ]
    else:
      metadata_lookup = event_metadata[
        (event_metadata['LogLink.LogName']==log_path) &
        (event_metadata['Provider.Name']==provider)
      ]
  else:
  # Provider not given
    if event_id:
      metadata_lookup = event_metadata[
        (event_metadata['LogLink.LogName']==log_path) &
        (event_metadata['Id']==event_id)
      ]
    elif level:
      metadata_lookup = event_metadata[
        (event_metadata['LogLink.LogName']==log_path) &
        (event_metadata['Level.Value']==level)
      ]
    else:
      metadata_lookup = event_metadata[
        (event_metadata['LogLink.LogName']==log_path)
      ]
  # Get highest version
  event_meta_data_max_versions = metadata_lookup[(metadata_lookup['Version']==metadata_lookup['Version'].max())]
  # Limit descripton to first line only?
  return event_meta_data_max_versions[metadata_columns].to_dict('records')


def prune_none_and_empty(d):
  """
  Remove keys that have either null values, empty strings or empty arrays
  See: https://stackoverflow.com/a/27974027/5472444
  """

  if not isinstance(d, (dict, list)):
    return d
  if isinstance(d, list):
    return [v for v in [prune_none_and_empty(v) for v in d] if v]
  return {k: v for k, v in ((k, prune_none_and_empty(v)) for k, v in d.items()) if v}


def set_to_list(d):
  """
  Convert set to list to avoid 'TypeError: Object of type set is not JSON serializable' error with json.dumps()
  """

  if isinstance(d, (set, list)):
    return [v for v in d]
  if isinstance(d, dict):
    return {k: set_to_list(v) for k, v in d.items()}
  return d


## Functions to interpret and compare windows event selections ##

# Regex patterns for windows event xpath queries
# (not a proper way to interpret xpath, just a rough approximation)
re_xpath_provider = re.compile(r'Provider\[@Name\s*=\s*[\'"]([^\'"]+)[\'"]]', re.IGNORECASE)
re_xpath_level = re.compile(r'Level\s*=\s*(\d+)', re.IGNORECASE)
re_xpath_event_id = re.compile(r'EventID\s*=\s*(\d+)', re.IGNORECASE)
# Deal with event ID ranges, e.g. *[System[(EventID >=4737 and EventID <=4739)]]', and they might be formatted over multiple lines.
re_xpath_event_id_range = re.compile(r'EventID\s*>=\s*(\d+)\s+and\s+EventID\s*<=\s*(\d+)', re.IGNORECASE & re.MULTILINE)
re_xml_comment = re.compile('<!--(.*?)-->', re.DOTALL & re.MULTILINE)


def get_event_id_list(xpath):
  """
  (Ab)use regex to get a list of event IDs from xPath which may be a in a list of 'or' logic or in a greater than or less than range
  """

  event_ids = []
  # find basic 'EventID=1 or EventID=2' xpath
  one_or_more_listed_event_ids = re_xpath_event_id.findall(xpath)
  if one_or_more_listed_event_ids:
    event_ids.extend([int(e) for e in one_or_more_listed_event_ids])
  # find ranges of 'EventID>=1 or EventID<=3' xpath where the regex returns a tuple of the upper and lower bound matched as regex groups
  one_or_more_event_id_ranges = re_xpath_event_id_range.findall(xpath)
  for event_id_range in one_or_more_event_id_ranges:
    lower = int(event_id_range[0])
    upper = int(event_id_range[1]) + 1
    event_ids.extend(list(range(lower, upper)))
  return event_ids


def xml_element_get_all_text(element: lxml.etree.Element):
  """
  Function to get all text, not just first child:

  - The .text property of elements from lxml only includes the first text part and is split by commented causing <Element>.text to produce truncated/partial text.
  - Instead of <Element>.text, using  <Element>.xpath('text()') is safer and will get a list of all text.
  - Extending lxml etree BaseElement class was not used due to:
    - Complexity where one cannot simply extend a class without interacting with the element tree. See: https://lxml.de/element_classes.html.
    - Extending the class injects a parent node element and shifts the current element with its properrties as a child element of the extended element.
  """

  #return ''.join([t for t in element.itertext()])
  return ''.join(element.xpath('text()'))


def get_queries(xml_query_list):
  """
  Extract elements and metadata from a windows event XML query list
  """

  x_query_list = lxml.etree.fromstring(xml_query_list).xpath('/QueryList/Query')
  assert len(x_query_list) > 0, f"Unexpected number of Query elements matched by XPath query '/QueryList/Query'"
  queries = []
  for x_query in x_query_list:
    # NOTE:
    # - The Path (log name) might be specified in either the query attributes (along with to the query ID) or in the XPath definition.
    # - The etree.Element class was extended as QueryElement with and all_text property because the standard text property truncates text after any embedded comments.
    # - TODO: It's undetermined if both the XPath and the query can simultaneously be set and are allowed to be different or must be consistant.
    # - TODO: Collected comments can get disassociated from the nearby select or suppress statement they annotate, so it's less useful for large/complex query IDs.
    # - FIXME: The data structure below using lazy regex to seperately list IDs and providers causes disassociation between the provider and event ID and misaligned flattened CSV output by event ID later on.
    queries.append(
      {
        'Comments': list(x_query.xpath('./comment()')),
        'Attributes': dict(x_query.attrib),
        'Selections': [
          { 'Path': str(s.xpath('@Path')[0]),
            'XPath': xml_element_get_all_text(s),
            'Providers': re_xpath_provider.findall(xml_element_get_all_text(s)),
            'Levels': re_xpath_level.findall(xml_element_get_all_text(s)),
            'EventIDs': get_event_id_list(xml_element_get_all_text(s))
          }
          for s in x_query.xpath('./Select')
        ],
        'Suppressions': [
          { 'Path': str(s.xpath('@Path')[0]),
            'XPath': xml_element_get_all_text(s),
            'Providers': re_xpath_provider.findall(xml_element_get_all_text(s)),
            'Levels': re_xpath_level.findall(xml_element_get_all_text(s)),
            'EventIDs': get_event_id_list(xml_element_get_all_text(s))
          } for s in x_query.xpath('./Suppress')
        ]
      }
    )
  return queries


def get_subscription_query_list_xml(xml_file_path):
  """
  Extract the embedded windows event XML QueryList elements out of a an XML subscription setting file
  """

  with open(xml_file_path, 'rb') as f_xml:
    x_subscription = lxml.etree.parse(f_xml)
    # XPath selection requires namespace to used!
    x_subscription_query = x_subscription.xpath('/ns:Subscription/ns:Query',  namespaces={'ns': 'http://schemas.microsoft.com/2006/03/windows/events/subscription'})
    assert len(x_subscription_query) == 1, f"Unexpected number of elements matched by XPath query '/ns:Subscription/ns:Query' for file {xml_file_path}."
    s_x_query = xml_element_get_all_text(x_subscription_query[0])
    return s_x_query


def enum_query_combinations(enum, s_file, q_id, q_parent_path, q_type, q):
  """
  Enumerate combinations of select or suppress sub-query elements and propergate references to the deepest level of event specificity.
  During enumeration, event and provider metadata lookups are done and used to increase the specificity.

  enum: dict object passed as a reference to add enumerated events and references to.
  s_file: subscription file name to reference
  q_id: Query ID of the XML element
  q_parent_path: Path attribute in the Query element
  q_type: Query type element, either Select or Suppress
  q_xpath: XPath data/text within Select or Suppress element

  Note, a pseudo-hierarchy of event query specificity, and related reference level, is as follows:

  Paths:
    Path: required
      Providers
        Provider: optional
          Events:
            Event ID: optional
            (Reference at this level)

  When query parsing and metadata lookups fail to resolve a specific provider(s) or event ID(s), a single null node is created.

  NOTE: Query specificity:
  - A query could just select an Event directly from a Path without specifying the Provider.
  - When an Event ID or Level is selected without a Provider, ambiguity results and multiple Providers and Events are in scope.
  - With the Security log Path/Channel, the Microsoft-Windows-Security-Auditing is the most common provider producing into this channel.
  - The Path attribute can be stipulated at query level and the sub-query Select or Suppress level. The deeper Select/Suppress level is assumed to take precedence.

  NOTE: Query metadata lookup failure reasons:
  - FIXME: Regex to extract event provider, event ID, or level failed to match properly.
  - Query did not select a valid/defined event or provider.
  - Source system metadata extract lacked provider or event manifests.

  - FIXME: This function has become too complex and bloated. Perhaps it should be simplified by refactored using objects to compartmentalise and abstract the complexity.
  """

  # Assume sub-level the <Select Path=...> or <Suppress Path=...> attribute will take precadence over parent <Query Path=...> attribute when choosing a channel
  q_path = q['Path']
  if not q_path:
    if q_parent_path == None:
      logger.error(f"Invalid query in '{s_file}'. Query ID {q_id} has no log 'Path' attribute defined for the <Query> and <{q_type}> sub-query type. Enumeration for this item aborted.", file=sys.stderr)
      return
    else:
      q_path = q_parent_path
  elif q_parent_path and q_parent_path != q_path:
    logger.warning(f"Contradicting query Path in '{s_file}'. Query ID {q_id}'s the child path attribute, <{q_type} Path='{q_path}'>, does not match the parent path attribute, <Query Path='{q_parent_path}'>. The child Path will take precadence.")

  # XPath extractions and permutations
  q_xpath = q['XPath']
  # NOTE:
  # - itertools.product or the list comprehension building a tuple from nested iterations will return an empty list if one of the iterations/lists input is empty
  # - Avoid this by replacing empty lists with a non-empty list and the single null/None value to force the product to expand out the empty sets
  # - FIXME: expansion is only based on Providers, Event IDs and Levels and this will fail to expand on queries that use other event attribtues such as Keywords, Tasks, Opcodes or Event Data.
  event_combinations = itertools.product(
    set(q['Providers']) if q['Providers'] else {None},
    {int(l) for l in q['Levels']} if q['Levels'] else {None},
    {int(i) for i in q['EventIDs']} if q['EventIDs'] else {None},
  )

  # Metadata lookups
  # List to accumulate results of events and metadata lookups
  m_list = []
  for e in event_combinations:
    x_provider, x_level, x_event_id = e
    # First try lookup message metadata related to query
    m_event_lookup = get_event_metadata(q_path, x_provider, x_event_id, x_level)
    m_event_lookup_len = len(m_event_lookup)
    if m_event_lookup_len > 0:
      logger.debug(f"{m_event_lookup_len} Event metadata items found for Path={q_path}, Provider={x_provider}, EventID={x_event_id}, Level={x_level}, as per {s_file} at Query ID={q_id} and {q_type} Path={q_path} with XPath: '{q_xpath}'.")
      # Use event metdata
      for m_event in m_event_lookup:
        # Use DisplayName when suitable, else fallback to Name, except for Provider Name and Log Name where a match to the Query Path and Provider is intended via Name.
        # Truncate the description to the first line unless a full description was intended or it's null
        m_list.append(
          {
            'Id': m_event['Id'],
            'Keywords':  m_event['Keywords.Name'],
            'Description': m_event['Description'] if args.metadata_full_description or m_event['Description'] is None else m_event['Description'].splitlines()[0],
            'Level': m_event['Level.DisplayName'] if m_event['Level.DisplayName'] else m_event['Level.Name'],
            'Level.Value': m_event['Level.Value'] if m_event['Level.Value'] is not None else x_level,
            'Task': m_event['Task.DisplayName'] if m_event['Task.DisplayName'] else m_event['Task.Name'],
            'Opcode': m_event['Opcode.DisplayName'] if m_event['Opcode.DisplayName'] else m_event['Opcode.Name'],
            'Provider': m_event['Provider.Name']
          }
        )
    else:
      # Sometimes manifests define providers but do not define any event metadata
      logger.debug(f"Event metadata lookup failed for Path='{q_path}', Provider='{x_provider}', EventID={x_event_id}, Level='{x_level}', as per '{s_file}' at Query ID={q_id} and {q_type} Path='{q_path}' with XPath: '{q_xpath}'.")
      # Second, try lookup provider metadata
      m_provider_lookup = get_provider_metadata(q_path, x_provider)
      m_provider_lookup_len = len(m_provider_lookup)
      if m_provider_lookup_len > 0:
        logger.debug(f"{m_provider_lookup} Provider metadata items found for Path={q_path}, Provider={x_provider}, as per {s_file} at Query ID={q_id} and {q_type} Path={q_path} with XPath: '{q_xpath}'.")
        # Use provider metadata
        for m_provider in m_provider_lookup:
          # NOTE:
          # - Both Event and Provider metadata nodes can list multiple keywords
          # - Events only support a single Level, Task or Opcode
          # - Providers can define multiple Levels, Tasks or Opcodes, but this is omitted as it would complicate flattening / normalising data at the event level.
          # - Hence only limited metadata is returned
          m_list.append(
            {
              'Id': None,
              'Keywords': m_provider['Keywords.Name'],
              'Description': None,
              'Level': None,
              'Level.Value': None,
              'Task': None,
              'Opcode': None,
              'Provider': m_provider['ProviderName']
            }
          )
      else:
        logger.warning(f"Event and Provider metadata lookup failed for Path='{q_path}', Provider='{x_provider}', and EventID={x_event_id}, as per '{s_file}' at Query ID={q_id} and {q_type} Path='{q_path}' with XPath: '{q_xpath}'.")
        # Single list item with nullified values provides a quick hack to ensure at least one loop iteration adds a reference for the query later on.
        m_list.append(
          {
            'Id': x_event_id,
            'Keywords': [],
            'Description': None,
            'Level': None,
            'Level.Value': None,
            'Task': None,
            'Opcode': None,
            'Provider': x_provider
          }
        )

  # Enumerate events with defined event IDs
  # NOTE: Verbose/explicit/unrolled complex dict update done because:
  # - This is an independent iteration using the event metadata if defined, but in case event metadata lookups failed, it falls back to the event info enumerated from the query/xpath.
  # - Python's dict merge() function overwrites key values in a shallow way, i.e. doesn't recurse and do a deep merge, nor does it handle values with lists.
  # - I don't know of an idomatic python example to merge complex/nested dicts.
  # - Even PEP https://www.python.org/dev/peps/pep-0584/ does not seem to consider nesting.
  # - FIXME: could be abstracted/neatened up with a recursive function to merge complex/nested dicts and lists.
  for m in m_list:
    path = q_path
    # Favour en missing/not specificed in the query, use the provider and event_id from the metadata lookup
    provider = m['Provider'] if m['Provider'] is not None else x_provider
    event_id = m['Id'] if m['Id'] is not None else x_event_id
    m_enrich = {k: m[k] for k in m if k in m_include}
    # Update enumeration with item if not already defined.
    # New log path?
    if path not in enum:
      enum[path] = {
        provider: {
          event_id: {
            'Metadata': m_enrich,
            'References': {
              s_file: {
                q_id: {
                  q_type: [
                    q_xpath
                  ]
                }
              }
            }
          }
        }
      }
    # New/first provider for log path?
    elif provider not in enum[path]:
      enum[path][provider] = {
        event_id: {
          'Metadata': m_enrich,
          'References': {
            s_file: {
              q_id: {
                q_type: [
                  q_xpath
                ]
              }
            }
          }
        }
      }
    # New/first event ID for provider?
    elif event_id not in enum[path][provider]:
      enum[path][provider][event_id] = {
        'Metadata': m_enrich,
        'References': {
          s_file: {
            q_id: {
              q_type: [
                q_xpath
              ]
            }
          }
        }
      }
    # New/first subscription reference file?
    elif s_file not in enum[path][provider][event_id]['References']:
      enum[path][provider][event_id]['References'][s_file] = {
        q_id: {
          q_type: [
            q_xpath
          ]
        }
      }
    # New/first query id for subscription file
    elif q_id not in enum[path][provider][event_id]['References'][s_file]:
      enum[path][provider][event_id]['References'][s_file][q_id] = {
        q_type: [
          q_xpath
        ]
      }
    # New/first selection or suppression filter reference for query id
    elif q_type not in enum[path][provider][event_id]['References'][s_file][q_id]:
      enum[path][provider][event_id]['References'][s_file][q_id][q_type] = [
        q_xpath
      ]
    # New/first xpath reference for select/suppress filter
    elif q_xpath not in enum[path][provider][event_id]['References'][s_file][q_id][q_type]:
      enum[path][provider][event_id]['References'][s_file][q_id][q_type].append(
        q_xpath
      )
    else:
      # This is expected if the XPath selects multiple event IDs because ID needs to enumerated out of the same XPath.
      logger.debug(f"Already enumerated this event and reference. Path={path}, Provider={provider}, EventID={event_id}, and the reference File={s_file}, QueryID={q_id}, Path={q_path}, Type={q_type}, XPath='{q_xpath}'")

  #TODO: XML comments not yet included as they can end up disassociated from the select or suppress statement in larger complex queries with multiple select or suppress elements.


# Parse the referenced windows event forwarding subscription configuration directories
logger.info('Importing and parsing source subscription/query list references.')
# Palantir
palantir_subscription_list = []
palantir_xml_subscription_files = glob.glob('./palantir/windows-event-forwarding/wef-subscriptions/*.xml')
for f_subscriptions in palantir_xml_subscription_files:
  queries = get_queries(get_subscription_query_list_xml(f_subscriptions))
  palantir_subscription_list.append({'file': f_subscriptions, 'queries': queries})
# NSA
nsa_subscription_list = []
nsa_xml_subscription_files = glob.glob('./nsacyber/Event-Forwarding-Guidance/Subscriptions/NT6/*.xml')
for f_subscriptions in nsa_xml_subscription_files:
  queries = get_queries(get_subscription_query_list_xml(f_subscriptions))
  nsa_subscription_list.append({'file': f_subscriptions, 'queries': queries})
# Microsoft
microsoft_subscription_list = []
microsoft_xml_query_files = glob.glob('./microsoft/*.xml')
for f_queries in microsoft_xml_query_files:
  with open(f_queries, 'rb') as f_xml:
    queries = get_queries(f_xml.read())
    microsoft_subscription_list.append({'file': f_queries, 'queries': queries})
subscription_reference_lists = [microsoft_subscription_list, nsa_subscription_list, palantir_subscription_list]
# Custom
custom_subscription_list = []
if args.custom:
  custom_xml_query_files = glob.glob('./custom/*.xml')
  for f_queries in custom_xml_query_files:
    with open(f_queries, 'rb') as f_xml:
      queries = get_queries(f_xml.read())
      custom_subscription_list.append({'file': f_queries, 'queries': queries})
  subscription_reference_lists.append(custom_subscription_list)
n_reference_files = len(palantir_subscription_list) + len(nsa_subscription_list) + len(microsoft_subscription_list) + len(custom_subscription_list)

# Represent subscriptions as yaml (for debugging/inspection)
logger.info('Converting and exporting each subscription (query list) XML reference into a simplified YAML representation.')
with open(f'{output_dir}/palantir_wef_subscriptons.yml', 'w') as f_yaml:
  f_yaml.write(yaml.dump(prune_none_and_empty(palantir_subscription_list), default_flow_style=False))
  f_yaml.close()
with open(f'{output_dir}/nsa_wef_subscriptons.yml', 'w') as f_yaml:
  f_yaml.write(yaml.dump(prune_none_and_empty(nsa_subscription_list), default_flow_style=False))
  f_yaml.close()
with open(f'{output_dir}/microsoft_wef_subscriptons.yml', 'w') as f_yaml:
  f_yaml.write(yaml.dump(prune_none_and_empty(microsoft_subscription_list), default_flow_style=False))
  f_yaml.close()
if args.custom and len(custom_subscription_list) > 0:
  with open(f'{output_dir}/custom_wef_subscriptons.yml', 'w') as f_yaml:
    f_yaml.write(yaml.dump(prune_none_and_empty(custom_subscription_list), default_flow_style=False))
    f_yaml.close()

# Enumerate and aggregate subscription query combinations normalised by Path (log name), Provider and EventID set.
# - Assumption that "Path : Provider : EventID" uniquely identifies an event.
# - However:
#   - Only Path might be supplied in a query and the rest (Provider, EventID or Level) may be omitted (None/Empty).
#   - Commonly, queries from the Security path often omit the assumed Provider, 'Microsoft-Windows-Security-Auditing'
# - Utilise tuples as composite keys for the dict object when enumerating combinations

# The query_combinations dict is built and used as nested index
# It's indexed by [<Path>][<Provider>][<EventId>][<References>][<Subscription File>][<Query ID>][<Query Type(Select|Suppress)>] 
# At the deepest level, the end leaf node is a list of XPaths under each query type.
# Midway at the EventID level, Event metadata for the EventID is injected if available, or else populated with None type values.
# Directly/implicitly structuring it with Path, Provider and EventID names as keys in the dict provides for faster indexing and appending unique combinantions in the enum_query_combinations function call.
# Likewise for cross-references to Subscription / Event Query List files.
# Once indexing is complete, a list of labeled dict objects more suited to normalisation into a flat csv is generated.
logger.info('Enumerating query combinations.')
query_combinations = {}

for subscription_reference_list in subscription_reference_lists:
  n_paths = len(query_combinations)
  for subscription in subscription_reference_list:
    subscription_file = subscription['file']
    logger.debug(f"Processing {subscription_file}")
    # Add or update referenced IDs
    for query in subscription['queries']:
      q_id = query['Attributes']['Id']
      if 'Path' in query['Attributes']:
        q_parent_path = query['Attributes']['Path']
      else:
        q_parent_path = None
      # Attempt to interpret xPath queries
      for x in query['Selections']:
        enum_query_combinations(query_combinations, subscription_file, q_id, q_parent_path, 'Select', x)
      for x in query['Suppressions']:
        enum_query_combinations(query_combinations, subscription_file, q_id, q_parent_path, 'Suppress', x)
    #TODO: comments not yet included due to disassocaition issue noted before.
    logger.debug(f"Processed {subscription_file}: New paths = {len(query_combinations) - n_paths}; Running total = {len(query_combinations)}.")
    # Count events queried, nested at path:provider:event_id
    n_paths = len(query_combinations)


# Output query_combinations index version which helps with debugging / validation of enumerating defined event query combinations
# json module fails to serialize python sets and sort_keys=True can't work as it won't compare None and Int types.
logger.info('Exporting query combination indexes in JSON and YAML formats.')
with open(f'{output_dir}/query_combinations_index.json', 'w') as f_json:
  json.dump(set_to_list(query_combinations), f_json, indent=2)
  f_json.close()
# Yaml module output is possibly better and more readable, can serialize sets, and doesn't mind comparing None and Int.
with open(f'{output_dir}/query_combinations_index.yml', 'w') as f_yaml:
  yaml.dump(query_combinations, f_yaml, default_flow_style=False)
  f_yaml.close()


# Output labled JSON, YAML and flattened CSV formats
# query_combinations was built as a dict indexed by [<Path>][<Provider>][<EventId>][<References>][<Subscription File>][<Query ID>][<Query Type(Select|Suppress)>].
# label and prepare query_combinations for csv export by adding explicit labels suitable for normalisation by column names Path, Provider and EventID.
# nested dict/list compreshension accross multiple lines for readability.
logger.info('Exporting query combinations with labled/named nodes in JSON and YAML formats.')
query_combinations_labeled = { 
  'Paths': [
    { 'Name': k_path,
      'Providers': [
        { 'Name': k_provider,
          'Events': [
            { 'Id': k_event_id,
              'Metadata': v_event['Metadata'],
              'References': [
                { 'File': k_ref,
                  'QueryList': [
                    { 'Id': k_query_id,
                      'SubQueries': [
                        { 'Type': k_query_type,
                          'XPath': v_xpath
                        } for k_query_type,v_xpath_list in v_query_types.items() for v_xpath in v_xpath_list
                        # The above complex list comprehension transforms the index for xpath query types back to the original structure the XML query had with select and suppress subqueries.
                        # E.g dict comprehension moving parent key into sublist values and enumerating on the sublist:
                        # [{k: i} for k, vl in dict_nested_list.items() for i in vl]
                      ]
                    } for k_query_id,v_query_types in v_ref_queries.items()
                  ]
                }
                for k_ref,v_ref_queries in v_event['References'].items()
              ]
            } for k_event_id,v_event in v_events.items()
          ]
        } for k_provider,v_events in v_providers.items()
      ]
    } for k_path,v_providers in query_combinations.items()
  ]
}
with open(f'{output_dir}/query_combinations.json', 'w') as f_json:
  json.dump(set_to_list(query_combinations_labeled), f_json, indent=2)
  f_json.close()
with open(f'{output_dir}/query_combinations.yml', 'w') as f_yaml:
  yaml.dump(query_combinations_labeled, f_yaml, default_flow_style=False)
  f_yaml.close()

# Flatten event ID view as csv
logger.info('Flattening/normalising query combinations by event.')
query_combinations_flattened_by_event = pd.json_normalize(
  query_combinations_labeled,
  record_path=['Paths', 'Providers', 'Events'],
  meta=[
    ['Paths','Name'],
    ['Paths','Providers','Name']
  ]
)
# Expand and flatten 'References' columns with complex nested objects into a tabulated summary showing how many references link to the event ID
# Note:
# - Attempts to create a summay per core reference with extra columns appended.
# - Additional columns summarise lists of files and lists of query IDs independently.
# - This breaks the association between file and Query ID.
# - However, in most event IDs are expected to only be referenced by one file and multiple files should be rare.
# - It only aggregates a count of Select and Suspend xPath attrbitues
# - It does not enumerate xPath details
# Move the References colum to the end
query_combinations_flattened_by_event['References'] = query_combinations_flattened_by_event.pop('References')
# The core reference can identified by the parent folder the files belong to. 
reference_dirs = ['microsoft', 'nsacyber', 'palantir']
if len(custom_subscription_list) > 0:
  reference_dirs.append('custom')

# Append expanded reference columns
for i, r_dir in enumerate(reference_dirs):
  # Boolean to list if related to core reference or not
  query_combinations_flattened_by_event[f'Reference.{r_dir}'] = False
  # To list files per core reference that relate to the event ID
  query_combinations_flattened_by_event[f'Reference.{r_dir}.FileList'] = np.empty(shape=(len(query_combinations_flattened_by_event.index), 0), dtype=str).tolist()
  # To list query IDs (only ever observed integers used in IDs)
  query_combinations_flattened_by_event[f'Reference.{r_dir}.QueryIDList'] = np.empty(shape=(len(query_combinations_flattened_by_event.index), 0), dtype=int).tolist()
  # To count Select and Suspend node attributes
  query_combinations_flattened_by_event[f'Reference.{r_dir}.SelectCount'] = 0
  query_combinations_flattened_by_event[f'Reference.{r_dir}.SuppressCount'] = 0
# TODO: Try use other pandas dataframe functions like grouby(), and learn how the split-apply-combine chain of operations works, e.g. https://realpython.com/pandas-groupby/
for i in query_combinations_flattened_by_event.index:
  for r in query_combinations_flattened_by_event.at[i, 'References']:
    for r_dir in reference_dirs:
      if r['File'].startswith(f'./{r_dir}'):
        query_combinations_flattened_by_event.at[i, f'Reference.{r_dir}'] = True
        query_combinations_flattened_by_event.at[i, f'Reference.{r_dir}.FileList'].append(r['File'])
        for q in r['QueryList']:
          query_combinations_flattened_by_event.at[i, f'Reference.{r_dir}.QueryIDList'].append(q['Id'])
          for s in q['SubQueries']:
            if s['Type'] == 'Select':
              query_combinations_flattened_by_event.at[i, f'Reference.{r_dir}.SelectCount'] += 1
            elif s['Type'] == 'Suppress':
              query_combinations_flattened_by_event.at[i, f'Reference.{r_dir}.SelectCount'] += 1
            else:
              raise AssertionError(f"'{s['Type']} for the QueryList Type was found with the References column at record index {i}, but only 'Select' or 'Suppress' was expected as a Type.")
# Remove the complex Reference column
query_combinations_flattened_by_event.drop('References', axis='columns', inplace=True)
if 'Metadata.Keywords' in query_combinations_flattened_by_event.columns:
  # Convert Keyword list into a semi-colon delimited string (since a comma in a CSV can become consfusing unless quoted).
  query_combinations_flattened_by_event['Metadata.Keywords'] = query_combinations_flattened_by_event['Metadata.Keywords'].apply(lambda l: '; '.join(l) if isinstance(l, list) else l)
# Likewise, convert reference FileList and QueryIDList objects to a semi-colon delimited string.
ref_columns_to_delimit = [c for c in query_combinations_flattened_by_event.columns if c.endswith('.FileList') or c.endswith('.QueryIDList')]
query_combinations_flattened_by_event[ref_columns_to_delimit] = query_combinations_flattened_by_event[ref_columns_to_delimit].applymap(lambda l: '; '.join(l) if isinstance(l, list) else l)
# Avoid None values causing ID integer conversion to float:
# - Sometimes only Provider info is available and event ID lookups for the provider fail because the sampled system's event ID metadata / maniest was not present for the provider.
# - In such cases, handle the event ID as NaN by using the Int64 type which has NaN support to avoid conversion to float type during CSV output.
# - See https://pandas.pydata.org/pandas-docs/stable/user_guide/gotchas.html#support-for-integer-na
columns_to_force_as_int = ['Id']
if 'Metadata.Level.Value' in query_combinations_flattened_by_event.columns:
  columns_to_force_as_int.append('Metadata.Level.Value')
query_combinations_flattened_by_event = query_combinations_flattened_by_event.astype(
  {c: pd.Int32Dtype() for c in columns_to_force_as_int}
)
#query_combinations_flattened_by_event[columns_to_force_as_int] = query_combinations_flattened_by_event.reindex(columns=columns_to_force_as_int)
query_combinations_flattened_by_event.to_csv(
  f'{output_dir}/query_combinations_flattened_by_event.csv',
  index=False
)

# Flatten reference view as csv
logger.info('Flattening/normalising query combinations by reference.')
query_combinations_flattened_by_reference = pd.json_normalize(
  query_combinations_labeled,
  record_path=['Paths','Providers','Events','References','QueryList','SubQueries'],
  meta=[
    ['Paths','Name'],
    ['Paths','Providers','Name'],
    ['Paths','Providers','Events','Id'],
    ['Paths','Providers','Events','References','File'],
    ['Paths','Providers','Events','References','QueryList','Id']
  ]
)
query_combinations_flattened_by_reference.to_csv(
  f'{output_dir}/query_combinations_flattened_by_reference.csv',
  index=False
)
logger.info(f'Exported flattened/normalised query combinations by event as "./{output_dir}/query_combinations_flattened_by_reference.csv".')

# Check for and warn about queries that were missing metadata lookups for Event IDs.
logger.info('Reviewing queries that had missing metadata lookups.')
query_combinations_flattened_by_reference_null_eventid = query_combinations_flattened_by_reference[query_combinations_flattened_by_reference['Paths.Providers.Events.Id'].isnull()]
if not query_combinations_flattened_by_reference_null_eventid.empty:
  logger.warning(
    'Event ID enumeration will be incomplete. There could be various reasons:\n' +
    '- The query could be invalid or event metadata could not be looked up.\n' +
    '- It is also not uncommon for some metadata to be incomplete, as provider and/or event manifests are often not valid or installed on a system.'
  )
  # Report unmapped events and related queries to csv
  query_combinations_flattened_by_reference_null_eventid_csv_view = query_combinations_flattened_by_reference_null_eventid[['Paths.Name', 'Paths.Providers.Name', 'Paths.Providers.Events.References.File', 'Paths.Providers.Events.References.QueryList.Id', 'Type', 'XPath']]
  query_combinations_flattened_by_reference_null_eventid_csv_view.to_csv(
    f'{output_dir}/query_combinations_flattened_by_reference_with_null_eventid_warning.csv',
    index=False
  )
  # Summerise on console
  col_simple_name = {
    'Paths.Name': 'Path', 
    'Paths.Providers.Name': 'Provider', 
    'Paths.Providers.Events.References.File': 'File',
    'Paths.Providers.Events.References.QueryList.Id': 'QueryId'
  }
  query_combinations_flattened_by_reference_null_eventid_simple_name_view = query_combinations_flattened_by_reference_null_eventid[['Paths.Name', 'Paths.Providers.Name', 'Paths.Providers.Events.References.File','Paths.Providers.Events.References.QueryList.Id']]
  query_combinations_flattened_by_reference_null_eventid_simple_name_view = query_combinations_flattened_by_reference_null_eventid_simple_name_view.rename(columns=col_simple_name)
  print('The impacted Paths and Providers which lacked event ID metadata cross-references are summarised below.', file=sys.stderr)
  # FIXME, to_markdown doesn't scale/wrap text to fit terminal size, so limit displayed columns to just Path and Provider
  try:
    term_rows, term_columns = os.get_terminal_size()
  except:
    term_columns = 80
  if term_columns < 130:
    print('Table may require a wider terminal width to view without wrapping.')
  pd.options.display.width = max(term_columns, 80)
  print(query_combinations_flattened_by_reference_null_eventid_simple_name_view[['Path','Provider']].to_markdown(showindex=False), file=sys.stderr)
  logger.warning(f'Refer to "./{output_dir}/query_combinations_flattened_by_reference_with_null_eventid_warning.csv" for details of which references are affected by metadata lookup failures.')
else:
  logger.info('All references could be mapped to event IDs via event metadata (good).')

# Final report
logger.info(f'Completed. {len(query_combinations_flattened_by_event)} events enumerated with {len(query_combinations_flattened_by_reference)} cross-references to {n_reference_files} reference files.')