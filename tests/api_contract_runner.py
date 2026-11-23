"""Verify registered API responses produced by existing Django integration tests."""

import json
from unittest.mock import patch

from django.test import Client
from django.test.runner import DiscoverRunner
from django.urls import Resolver404, resolve
from jsonschema import Draft202012Validator, FormatChecker

from apps.core.factory_api.urls import PREFIX, contract, operation_id


class ContractRunner(DiscoverRunner):
    def record_response(self, identity, status):
        """Allow specialised runners to collect the validated operation and status."""

    def run_tests(self, test_labels, **kwargs):
        document = contract()
        operations = {
            operation['operationId']: operation
            for methods in document['paths'].values()
            for operation in methods.values()
        }
        components = document['components']
        successful = set()
        exercised = set()
        request = Client.request

        def checked(client, **values):
            response = request(client, **values)
            path = response.wsgi_request.path_info
            method = response.wsgi_request.method
            if not path.startswith(PREFIX) or method == 'HEAD':
                return response
            try:
                handler = getattr(resolve(path).func, 'api_handlers', {}).get(method)
            except Resolver404:
                return response
            if handler is None:
                return response
            identity = operation_id(handler)
            exercised.add(identity)
            returns = operations[identity]['responses']
            status = str(response.status_code)
            if status not in returns and response.status_code < 400:
                raise AssertionError(f'{identity} returned undocumented status {status}.')
            details = returns.get(status, returns['default'])
            if '$ref' in details:
                details = components['responses'][details['$ref'].rsplit('/', 1)[1]]
            media_type = response.get('Content-Type')
            if media_type not in details['content']:
                raise AssertionError(f'{identity} returned {status} with an undeclared media type.')
            schema = details['content'][media_type]['schema']
            if media_type != 'application/json':
                if schema.get('format') != 'binary' or not response.get('Content-Disposition', '').startswith('attachment;'):
                    raise AssertionError(f'{identity} returned {status} without the declared attachment.')
                self.record_response(identity, status)
                if response.status_code < 300:
                    successful.add(identity)
                return response
            if '$ref' in schema:
                schema = components['schemas'][schema['$ref'].rsplit('/', 1)[1]]
            failures = Draft202012Validator(schema, format_checker=FormatChecker()).iter_errors(response.json())
            failure = next(failures, None)
            if failure:
                field = '.'.join(map(str, failure.absolute_path)) or 'body'
                raise AssertionError(f'{identity} {status} failed the {failure.validator} contract at {field}.')
            self.record_response(identity, status)
            if response.status_code < 300:
                successful.add(identity)
            return response

        with patch.object(Client, 'request', checked):
            result = super().run_tests(test_labels, **kwargs)
        self.log(f'API responses checked for {len(exercised)}/{len(operations)} operations, '
                 f'{len(successful)} with a successful response.')
        if not result:
            self.log('PSL_API_OPERATIONS_PASSED=' + json.dumps(sorted(successful), separators=(',', ':')))
        self.log('Operations without success evidence: ' + ', '.join(sorted(operations.keys() - successful)))
        return result
