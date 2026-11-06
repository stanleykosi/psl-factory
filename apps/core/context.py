"""Presentation boundaries do not add routes or authority to the recovery plane."""
from django.conf import settings

def interface(request):
    return {'control_plane':settings.ROOT_URLCONF=='config.cold_urls'}
