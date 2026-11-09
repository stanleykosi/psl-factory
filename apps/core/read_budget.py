"""Bound data transferred by an explicitly scoped PostgreSQL snapshot reader."""
from django.db import models
from django.db.models.functions import Cast


class ReadLimit(Exception):
    """An engineering hold, independent of domain validation or permission."""


class ReadBudget:
    def __init__(self):
        self.remaining = 1024 * 1024

    def load(self, row, field_name, *, ceiling=256 * 1024):
        field = row._meta.get_field(field_name)
        size = models.Func(Cast(models.F(field_name), models.TextField()),
                           function='OCTET_LENGTH', output_field=models.IntegerField())
        # Both expressions use the same row in the same SQL statement. Large
        # values are measured in PostgreSQL and never decoded by the driver.
        row_data = type(row).objects.filter(pk=row.pk).annotate(
            _read_size=size,
            _read_value=models.Case(
                models.When(_read_size__lte=min(ceiling, self.remaining), then=models.F(field_name)),
                output_field=field,
            ),
        ).values_list('_read_size', '_read_value').first()
        if row_data is None or row_data[0] is None or row_data[0] > min(ceiling, self.remaining):
            raise ReadLimit
        size_bytes, value = row_data
        self.remaining -= size_bytes
        setattr(row, field_name, value)
        return value

    def take(self, queryset, limit=100):
        rows = list(queryset[:limit + 1])
        if len(rows) > limit:
            raise ReadLimit
        return rows
