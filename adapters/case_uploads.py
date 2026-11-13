import hashlib
import os

from django.core.exceptions import ValidationError

LIMIT = 5 * 1024 * 1024


def bucket():
    import boto3
    from botocore.config import Config

    names = ['BUCKET', 'ENDPOINT', 'REGION', 'ACCESS_KEY_ID', 'SECRET_ACCESS_KEY']
    values = [os.getenv('PSL_UPLOAD_' + name) for name in names]
    if not all(values) or not values[1].startswith('https://'):
        raise ValidationError('Private uploads are unavailable.')
    name, endpoint, region, access, secret = values
    client = boto3.client('s3', endpoint_url=endpoint, region_name=region,
                          aws_access_key_id=access, aws_secret_access_key=secret,
                          config=Config(signature_version='s3v4', s3={'addressing_style': 'virtual'},
                                        connect_timeout=5, read_timeout=15))
    return client, name


def put(key, data):
    client, name = bucket()
    client.put_object(Bucket=name, Key=key, Body=data, ContentType='application/octet-stream')


def read(upload):
    client, name = bucket()
    stream = client.get_object(Bucket=name, Key=upload.key)['Body']
    try:
        data = stream.read(LIMIT + 1)
    finally:
        stream.close()
    if len(data) != upload.size or hashlib.sha256(data).hexdigest() != upload.sha256:
        raise ValidationError('File integrity check failed.')
    return data
