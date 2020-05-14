#!/usr/bin/env python3

import os
import colorlog
import zipfile
import json
import pandas as pd


## Colourised output to console
logger = colorlog.getLogger()
logger.setLevel(colorlog.colorlog.logging.INFO)
handler = colorlog.StreamHandler()
handler.setFormatter(colorlog.ColoredFormatter())
logger.addHandler(handler)

## Set working directory to intended subdir (helps when running in vscode)
if 'Windows Event Metadata' not in os.getcwd():
  # Assume in project root dir
  os.chdir('./Windows Event Metadata')

output_dir = './flattened'
if not os.path.exists(output_dir):
    os.makedirs(output_dir)

# Functions to handle complex keys/nodes and insert a simplified name subkey as a string lists.

def simplify_composite_keys(df, keys):
  # Intended for simplifying Keywords, Tasks, Opcodes and Levels, but does not apply to Log Links.

  def get_object_names(o):
    # Used to convert complex Keyword, Task, Opcode or Level nodes into simpler DisplayName or Name strings.
    if isinstance(o, list):
      # PowerShell/Windows serialises 'empty' event metadata as a null item in a list for event Keywords, etc.
      # It can also start a list with a null item followed by valid items.
      # Check for and remove null items
      for i, n in enumerate(o):
        if n['DisplayName'] is None and n['Name'] is None:
          del o[i]
      return [i['DisplayName'] if i['DisplayName'] is not None else i['Name'] for i in o]
    elif isinstance(o, dict):
      o['DisplayName'] if o['DisplayName'] is not None else o['Name']
    elif o is None:
      return None
    else:
      raise TypeError('get_object_names expects a list of dicts, a dict or None')

  for k in keys:
    if k in df.columns.values:
      names = df[k].apply(get_object_names)
      # Insert the simpler text keword names after to the original complex object column.
      i_col_complex_k = df.columns.get_loc(k)
      i_next_col_simplified_names = i_col_complex_k + 1
      df.insert(i_next_col_simplified_names, f'{k}.Name', names)
    else:
      raise KeyError(f"'{k}' key was not found in the dataframe columns.")


def simplify_composite_loglink_key(df, key):
  # Intended for simplifying Log Link's using the LogName subkey.
  
  def get_log_link_names(o):
    #Used to convert complex LogLink nodes into simpler LogName strings. DisplayName is omitted since it's often not specified or less descriptive.
    if isinstance(o, list):
      return [key['LogName'] for key in o]
    else:
      raise TypeError('get_log_link_names expects a list of dicts.')

  if key in df.columns.values:
    log_names = df[key].apply(get_log_link_names)
    # Insert the simpler text keword names after to the original complex object column.
    i_col_complex_k = df.columns.get_loc(key)
    i_next_col_simplified_names = i_col_complex_k + 1
    df.insert(i_next_col_simplified_names, f'{key}.Name', log_names)
  else:
    raise KeyError(f"'{key}' key was not found in the dataframe columns.")


# Import/deserialize from compressed json (output of Get-EventMetaData.ps1).
metadata_import = None
zip_file = './Extracted/EventMetadata.json.zip'
with zipfile.ZipFile(zip_file, 'r') as z:
  with z.open('EventMetadata.json') as f:
    metadata_import = json.load(f)
logger.info(f'{len(metadata_import)} Providers and related metadata imported from "{zip_file}".')

# Get per provider metadata (which sub-keys to collect/filter)
metadata_by_provider_flattened = pd.json_normalize(metadata_import)
# Simplify the Provider's Keywords, Tasks, Opcodes and Levels metadata
simplify_composite_keys(df=metadata_by_provider_flattened, keys=['Keywords', 'Tasks', 'Opcodes', 'Levels'])
simplify_composite_loglink_key(df=metadata_by_provider_flattened, key='LogLinks')
# Remove complex arrays of nested objects after simplification
metadata_by_provider_flattened.drop(columns=['LogLinks', 'Keywords', 'Tasks', 'Opcodes', 'Levels', 'Events'], inplace=True)
# Export as compressed JSON
metadata_by_provider_flattened.to_json(
  f'{output_dir}/metadata_by_provider_flattened.json.zip',
  orient='records',
  indent=2,
  compression=dict(
    method='zip',
    archive_name='metadata_by_provider_flattened.json'
  )
)
# Export as csv
metadata_by_provider_flattened.to_csv(
  f'{output_dir}/metadata_by_provider_flattened.csv.zip',
  index=False,
  compression=dict(
    method='zip',
    archive_name='metadata_by_provider_flattened.csv'
  )
)
n_metadata_by_provider_flattened = len(metadata_by_provider_flattened)
logger.info(f'Flattened/normalised metadata for {n_metadata_by_provider_flattened} providers exported to "{output_dir}" as "metadata_by_provider_flattened.csv.zip" and "metadata_by_provider_flattened.json.zip"')

# Examine log links (which relates to the 'Path' attribute used in event queries)
provider_metadata = ['Id', 'Name', 'DisplayName', 'ResourceFilePath', 'MessageFilePath', 'ParameterFilePath', 'HelpLink']
metadata_by_loglink = pd.json_normalize(metadata_import, record_path='LogLinks', meta_prefix='Provider.', meta=provider_metadata)
n_metadata_by_loglink = len(metadata_by_loglink)
distinct_loglinks = metadata_by_loglink.groupby(['LogName', 'DisplayName']).size().reset_index().rename(columns={0:'count'})
n_distinct_loglinks = len(distinct_loglinks)
logger.info(f'{n_distinct_loglinks} distinct Log Links found accross {n_metadata_by_loglink} Providers.')
# Report metrics on how many LogLinks don't have a non-null display name match the log name
# See: https://stackoverflow.com/a/35268906/5472444
distinct_loglinks_name_missmatch = distinct_loglinks[(distinct_loglinks['DisplayName'].notnull() & (distinct_loglinks['LogName'] != distinct_loglinks['DisplayName']))]
n_distinct_loglinks_name_missmatch = len(distinct_loglinks_name_missmatch)
metadata_by_loglink_name_missmatch = metadata_by_loglink[metadata_by_loglink['DisplayName'].notnull() & (metadata_by_loglink['LogName'] != metadata_by_loglink['DisplayName'])]
n_distinct_providers_with_loglink_name_missmatches=len(metadata_by_loglink_name_missmatch['Provider.Name'].unique())
if n_distinct_loglinks_name_missmatch > 0:
  metadata_by_loglink_name_missmatch.to_csv(
    f'{output_dir}/metadata_by_loglink_name_missmatch.csv.zip',
    index=False,
    compression=dict(
      method='zip',
      archive_name='metadata_by_loglink_name_missmatch.csv'
    )
  )
  # Only print a notice since this is fairly common and not an actual issue, but it's interesting that the norm is for them to match.
  logger.warning(f'{n_distinct_loglinks_name_missmatch}/{n_distinct_loglinks} distinct Log Link(s) had a Display Name that did not match the Log Name and were linked to {n_distinct_providers_with_loglink_name_missmatches}/{n_metadata_by_provider_flattened} Provider(s).')
  logger.info(f'\'LogName\' is extracted and \'DisplayName\' is ignored when flattening Provider metadata into "{output_dir}/metadata_by_provider_flattened.csv.zip".')
  logger.info(f'"{output_dir}/metadata_by_loglink_name_missmatch.csv.zip" enumerates all impacted Log Names and Providers to help discern when the Log Display Name (as shown in Windows Event Viewer) will not match the actual Path (\'LogName\') to be used for event queries.')

# Normalize and expand according to events adding provider info as metadata
provider_metadata = ['Id', 'Name', 'DisplayName', 'ResourceFilePath', 'MessageFilePath', 'ParameterFilePath', 'HelpLink']
metadata_by_event_flattened = pd.json_normalize(metadata_import, record_path='Events', meta_prefix='Provider.', meta=provider_metadata)
# Simplify the Keyword metadata at both the Event level
simplify_composite_keys(metadata_by_event_flattened, ['Keywords'])
# Remove complex arrays of nested objects after simplification
metadata_by_event_flattened.drop(columns=['Keywords'], inplace=True)
# Export as compressed JSON
metadata_by_event_flattened.to_json(
  f'{output_dir}/metadata_by_event_flattened.json.zip',
  orient='records',
  indent=2,
  compression=dict(
    method='zip',
    archive_name='metadata_by_event_flattened.json'
  )
)
# Export as csv
metadata_by_event_flattened.to_csv(
  f'{output_dir}/metadata_by_event_flattened.csv.zip',
  index=False,
  compression=dict(
    method='zip',
    archive_name='metadata_by_event_flattened.csv'
  )
)
logger.info(f'Flattened/normalised metadata for {len(metadata_by_event_flattened)} events exported to {output_dir} as "metadata_by_event_flattened.csv.zip" and "metadata_by_event_flattened.json.zip"')
logger.info('Completed.')
