"""Measure the point-in-polygon search against a large table.

Generates throwaway polygons, then prints the PostgreSQL plan for the search
query twice: once as it really runs, and once with index scans disabled, so the
GiST index can be credited with a number rather than an assertion.

    python manage.py benchmark_search --count 100000 --lat 38.7369 --lng -9.1399
"""

import statistics
import time

from django.core.management.base import BaseCommand
from django.db import connection, transaction

from testapp.models import ServiceArea
from testapp.queries import ServiceAreaCoverageQuery, point_from_lat_lng

BENCH_PREFIX = "bench-"

# Random boxes roughly 0.05 degrees across, scattered over the whole globe.
INSERT_RANDOM_SQL = """
INSERT INTO {table} (name, price, area_polygon, provider_id)
SELECT
    '{prefix}' || g,
    10.00,
    ST_SetSRID(
        ST_MakeEnvelope(lng, lat, lng + 0.05, lat + 0.05),
        4326
    ),
    NULL
FROM generate_series(1, %s) AS g
CROSS JOIN LATERAL (
    SELECT random() * 359.0 - 179.5 AS lng, random() * 169.0 - 84.5 AS lat
) AS r
"""

# A few boxes guaranteed to contain the probe point, so the query has work to do.
INSERT_MATCHING_SQL = """
INSERT INTO {table} (name, price, area_polygon, provider_id)
SELECT
    '{prefix}hit-' || g,
    10.00,
    ST_SetSRID(ST_MakeEnvelope(%s - g * 0.01, %s - g * 0.01,
                               %s + g * 0.01, %s + g * 0.01), 4326),
    NULL
FROM generate_series(1, 3) AS g
"""


class Command(BaseCommand):
    help = "Benchmark the point-in-polygon search over a synthetic dataset."

    def add_arguments(self, parser):
        parser.add_argument("--count", type=int, default=100000)
        parser.add_argument("--lat", type=float, default=38.7369)
        parser.add_argument("--lng", type=float, default=-9.1399)
        parser.add_argument("--repeat", type=int, default=25)
        parser.add_argument(
            "--keep",
            action="store_true",
            help="Leave the generated rows in place instead of deleting them.",
        )

    def handle(self, *args, **options):
        table = ServiceArea._meta.db_table
        point = point_from_lat_lng(options["lat"], options["lng"])
        query = ServiceAreaCoverageQuery()

        try:
            self._generate(table, options)
            self._report_size(table)
            self._time_query(query, point, options["repeat"])
            self._print_plan(query, point, "WITH the GiST index", use_index=True)
            self._print_plan(query, point, "WITHOUT any index", use_index=False)
        finally:
            if not options["keep"]:
                deleted, _ = ServiceArea.objects.filter(
                    name__startswith=BENCH_PREFIX
                ).delete()
                self.stdout.write("\nremoved %d generated rows" % deleted)

    def _generate(self, table, options):
        count = options["count"]
        self.stdout.write("generating %d polygons ..." % count)
        started = time.perf_counter()
        with transaction.atomic(), connection.cursor() as cursor:
            cursor.execute(
                INSERT_RANDOM_SQL.format(table=table, prefix=BENCH_PREFIX), [count]
            )
            cursor.execute(
                INSERT_MATCHING_SQL.format(table=table, prefix=BENCH_PREFIX),
                [options["lng"], options["lat"], options["lng"], options["lat"]],
            )
        with connection.cursor() as cursor:
            cursor.execute("ANALYZE %s" % table)
        self.stdout.write(
            "inserted in %.1fs; table now holds %d rows"
            % (time.perf_counter() - started, ServiceArea.objects.count())
        )

    def _report_size(self, table):
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT i.indexname,
                       pg_size_pretty(pg_relation_size(c.oid)),
                       a.amname
                FROM pg_indexes i
                JOIN pg_class c ON c.relname = i.indexname
                JOIN pg_am a ON a.oid = c.relam
                WHERE i.tablename = %s
                ORDER BY i.indexname
                """,
                [table],
            )
            rows = cursor.fetchall()
            cursor.execute("SELECT pg_size_pretty(pg_total_relation_size(%s))", [table])
            total = cursor.fetchone()[0]
        self.stdout.write("\ntable %s total size: %s" % (table, total))
        for name, size, method in rows:
            self.stdout.write("  index %-45s %-8s %s" % (name, method, size))

    def _time_query(self, query, point, repeat):
        durations = []
        for _ in range(repeat):
            started = time.perf_counter()
            list(query.for_point(point)[:10])
            durations.append((time.perf_counter() - started) * 1000.0)
        self.stdout.write(
            "\nsearch query over %d runs: median %.2f ms, min %.2f ms, max %.2f ms"
            % (repeat, statistics.median(durations), min(durations), max(durations))
        )

    def _print_plan(self, query, point, label, use_index):
        compiled_sql, params = query.for_point(point).query.sql_with_params()
        with connection.cursor() as cursor:
            if not use_index:
                cursor.execute("SET enable_indexscan = off")
                cursor.execute("SET enable_bitmapscan = off")
                cursor.execute("SET enable_indexonlyscan = off")
            cursor.execute("EXPLAIN (ANALYZE, BUFFERS, TIMING) " + compiled_sql, params)
            plan = "\n".join(row[0] for row in cursor.fetchall())
            if not use_index:
                cursor.execute("RESET enable_indexscan")
                cursor.execute("RESET enable_bitmapscan")
                cursor.execute("RESET enable_indexonlyscan")
        self.stdout.write("\n--- EXPLAIN ANALYZE %s ---\n%s" % (label, plan))
