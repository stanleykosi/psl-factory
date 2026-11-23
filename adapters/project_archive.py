"""Immutable private file copies with byte-level readback by stable object key."""
import hashlib
import json
import os

from django.core.exceptions import ValidationError

from adapters import case_uploads


def destination(value):
    if value['adapter'] == 'synthetic_archive/v1':
        return hashlib.sha256(b'psl-synthetic-project-archive/v1').hexdigest()
    location = [os.getenv('PSL_UPLOAD_' + name) for name in ['BUCKET', 'ENDPOINT', 'REGION']]
    if not all(location) or not location[1].startswith('https://'):
        raise ValidationError('Configure the reviewed private file store before archiving files.')
    return hashlib.sha256(json.dumps(location).encode()).hexdigest()


def object_key(file):
    return f'archives/v1/{file.plan.work.case_id}/{file.plan_id}/{file.pk}/{file.sha256}'


def proof(file, data):
    if len(data) != file.size or hashlib.sha256(data).hexdigest() != file.sha256:
        raise ValidationError('The archive object differs from the exact declared file.')
    return {'object_key': object_key(file), 'sha256': file.sha256, 'size': file.size}


class PrivateObjectArchive:
    def lookup(self, file):
        from botocore.exceptions import ClientError

        with case_uploads.storage_client() as (client, bucket):
            try:
                stream = client.get_object(Bucket=bucket, Key=object_key(file))['Body']
            except ClientError as exc:
                if exc.response.get('Error', {}).get('Code') in ['NoSuchKey', '404', 'NotFound']:
                    return None
                raise
            try:
                data = stream.read(file.size + 1)
            finally:
                stream.close()
        return proof(file, data)

    def copy(self, file, data):
        from botocore.exceptions import ClientError

        proof(file, data)
        with case_uploads.storage_client() as (client, bucket):
            try:
                client.put_object(Bucket=bucket, Key=object_key(file), Body=data,
                                  ContentType='application/octet-stream', IfNoneMatch='*')
            except ClientError as exc:
                if exc.response.get('Error', {}).get('Code') not in ['PreconditionFailed', '412']:
                    raise
        return self.lookup(file)


class SyntheticObjectArchive:
    """Persistent test-store state survives interrupted delivery and worker restart."""

    def lookup(self, file):
        from apps.pmo.models import SyntheticArchiveObject

        if not file.plan.work.case.synthetic:
            raise ValidationError('The sample archive store requires a synthetic project.')
        stored = SyntheticArchiveObject.objects.filter(file=file).first()
        return proof(file, bytes(stored.data)) if stored else None

    def copy(self, file, data):
        from apps.pmo.models import SyntheticArchiveObject

        if not file.plan.work.case.synthetic:
            raise ValidationError('The sample archive store requires a synthetic project.')
        proof(file, data)
        stored, _ = SyntheticArchiveObject.objects.get_or_create(
            file=file, defaults={'data': data, 'sha256': file.sha256})
        proof(file, bytes(stored.data))
        return self.lookup(file)


def configured_adapter(value):
    if value['adapter'] == 'synthetic_archive/v1':
        return SyntheticObjectArchive()
    if value['adapter'] == 'private_object_store/v1':
        return PrivateObjectArchive()
    raise ValidationError('Review the archive store connection before copying files.')
