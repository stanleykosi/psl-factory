"""Bound data transferred by an explicitly scoped PostgreSQL snapshot reader."""
from contextlib import contextmanager

from django.db import connection, models
from django.db.models.functions import Cast


class ReadLimit(Exception):
    """An engineering hold, independent of domain validation or permission."""


@contextmanager
def limit_queries(remaining):
    def charge(execute, sql, params, many, context):
        nonlocal remaining
        if remaining == 0:
            raise ReadLimit
        remaining -= 1
        return execute(sql, params, many, context)

    with connection.execute_wrapper(charge):
        yield


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

    def load_many(self, records, field_name, *, ceiling=256 * 1024):
        if not records:
            return
        model = type(records[0])
        by_id = {row.pk: row for row in records}
        field = model._meta.get_field(field_name)
        size = models.Func(Cast(models.F(field_name), models.TextField()),
                           function='OCTET_LENGTH', output_field=models.IntegerField())
        # Admission and transfer share one statement. An over-budget batch
        # returns sizes, with no JSON values sent to the application.
        rows = list(model.objects.filter(pk__in=by_id).annotate(
            _read_size=size,
            _read_total=models.Window(models.Sum(size)),
            _read_largest=models.Window(models.Max(size)),
        ).annotate(
            _read_value=models.Case(
                models.When(_read_total__lte=self.remaining, _read_largest__lte=ceiling, then=models.F(field_name)),
                output_field=field,
            ),
        ).values_list('pk', '_read_size', '_read_value'))
        if len(rows) != len(by_id) or any(size is None or size > ceiling for _, size, _ in rows):
            raise ReadLimit
        total = sum(size for _, size, _ in rows)
        if total > self.remaining:
            raise ReadLimit
        self.remaining -= total
        for pk, _, value in rows:
            setattr(by_id[pk], field_name, value)

    def take(self, queryset, limit=100):
        rows = list(queryset[:limit + 1])
        if len(rows) > limit:
            raise ReadLimit
        return rows
