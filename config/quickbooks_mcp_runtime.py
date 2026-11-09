"""Optional reference-only MCP configuration; no credential resolution or traffic."""
import os
import re
from adapters.quickbooks_mcp import decode, bounded, require, MCPError, READ_SCOPE, VERSION, READ_TOOL, schema_check
from .runtime_files import read_bounded_file

FIELDS = {'enabled','realm','principal_ref','credential_ref','credential_revision','app_name','contract_id','scopes','reviewed_tool','output_schema','target_argument','result_identity_key','fixed_arguments'}


def validate_registry(value, secrets):
    try:
        require(isinstance(value, dict) and len(value) <= 16)
        contracts = set()
        for alias, entry in value.items():
            require(isinstance(alias, str) and re.fullmatch(r'[a-z][a-z0-9_-]{0,63}', alias))
            require(isinstance(entry, dict) and set(entry) == FIELDS and type(entry['enabled']) is bool)
            for key in ('realm','principal_ref','credential_revision','app_name'):
                require(isinstance(entry[key], str) and re.fullmatch(r'[A-Za-z0-9_.:@-]{1,100}', entry[key]))
            require(re.fullmatch(r'[A-Za-z0-9_-]{1,60}', entry['app_name']))
            require(type(entry['contract_id']) is int and entry['contract_id'] > 0 and entry['contract_id'] not in contracts)
            contracts.add(entry['contract_id'])
            require(entry['scopes'] == ['com.intuit.quickbooks.accounting', READ_SCOPE])
            if entry['reviewed_tool'] is not None:
                require(isinstance(entry['reviewed_tool'], dict) and entry['reviewed_tool'].get('name') == READ_TOOL)
                schema_check(entry['reviewed_tool'].get('inputSchema'))
            if entry['output_schema'] is not None:
                schema_check(entry['output_schema'])
            for key in ('target_argument','result_identity_key'):
                require(entry[key] is None or isinstance(entry[key], str) and re.fullmatch(r'[A-Za-z][A-Za-z0-9_]{0,63}', entry[key]))
            require(isinstance(entry['fixed_arguments'], dict) and len(entry['fixed_arguments']) <= 16 and entry['target_argument'] not in entry['fixed_arguments'])
            bounded(entry['fixed_arguments'], 4096)
            credential = secrets.get(entry['credential_ref'])
            require(isinstance(credential, dict) and set(credential) == {'env','revision'}
                and credential['revision'] == entry['credential_revision']
                and isinstance(credential['env'], str) and re.fullmatch(r'[A-Z][A-Z0-9_]{0,127}', credential['env']))
        bounded(value)
        return value
    except (MCPError, TypeError, KeyError, AttributeError):
        raise RuntimeError('Invalid QuickBooks MCP reference configuration') from None


def load(secrets):
    value = os.getenv('PSL_QUICKBOOKS_MCP_PROFILE')
    if not value:
        return {}
    try:
        raw = read_bounded_file(value, 131072)
        return validate_registry(decode(raw), secrets)
    except (OSError, ValueError, TypeError, AttributeError, MCPError):
        raise RuntimeError('Invalid QuickBooks MCP reference configuration') from None
