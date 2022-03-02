# Scalability: the point-in-polygon search under load

The search endpoint is a single spatial query, so its scaling behaviour is
entirely the behaviour of the GiST index on `testapp_servicearea.area_polygon`.
This file records a measurement rather than an assertion.

## How the index gets created

`ServiceArea.area_polygon` is a `PolygonField`, which defaults to
`spatial_index=True`. Django's PostGIS backend emits the index alongside the
column, so it is in the migration history even though the migration file does
not mention it:

```console
$ python manage.py sqlmigrate testapp 0007
BEGIN;
--
-- Add field area_polygon to servicearea
--
ALTER TABLE "testapp_servicearea" ADD COLUMN "area_polygon" geometry(POLYGON,4326) NULL;
CREATE INDEX "testapp_servicearea_area_polygon_id" ON "testapp_servicearea" USING GIST ("area_polygon");
COMMIT;
```

And in a migrated database:

```console
$ psql -d mozio_uplift -c '\d testapp_servicearea'
                                       Table "public.testapp_servicearea"
    Column    |          Type          | Collation | Nullable |                     Default
--------------+------------------------+-----------+----------+-------------------------------------------------
 id           | bigint                 |           | not null | nextval('testapp_servicearea_id_seq'::regclass)
 name         | character varying(60)  |           | not null |
 price        | numeric(6,2)           |           | not null |
 area_polygon | geometry(Polygon,4326) |           |          |
 provider_id  | bigint                 |           |          |
Indexes:
    "testapp_servicearea_pkey" PRIMARY KEY, btree (id)
    "testapp_servicearea_area_polygon_id" gist (area_polygon)
    "testapp_servicearea_provider_id_bbbb8375" btree (provider_id)
```

`testapp/tests/test_queries.py` asserts the GiST index exists by reading
`pg_am`, so a future migration that drops it fails the suite.

## The measurement

`manage.py benchmark_search` generates throwaway polygons, times the query, and
prints the plan twice: once as it really runs, and once with index scans turned
off, so the index can be credited with a number. Measured on 2026-09-23,
PostgreSQL 17.6 / PostGIS 3.5.3, Apple Silicon, default `shared_buffers`:

```console
$ python manage.py benchmark_search --count 100000
generating 100000 polygons ...
inserted in 6.4s; table now holds 100012 rows

table testapp_servicearea total size: 25 MB
  index testapp_servicearea_area_polygon_id           gist     5472 kB
  index testapp_servicearea_pkey                      btree    2208 kB
  index testapp_servicearea_provider_id_bbbb8375      btree    656 kB

search query over 25 runs: median 0.56 ms, min 0.53 ms, max 4.90 ms

--- EXPLAIN ANALYZE WITH the GiST index ---
Sort  (cost=29.27..29.27 rows=1 width=934) (actual time=0.022..0.022 rows=6 loops=1)
  Sort Key: testapp_servicearea.id
  Sort Method: quicksort  Memory: 26kB
  Buffers: shared hit=11
  ->  Nested Loop Left Join  (cost=0.42..29.26 rows=1 width=934) (actual time=0.015..0.019 rows=6 loops=1)
        Buffers: shared hit=11
        ->  Index Scan using testapp_servicearea_area_polygon_id on testapp_servicearea  (cost=0.28..20.80 rows=1 width=152) (actual time=0.013..0.015 rows=6 loops=1)
              Index Cond: (area_polygon ~ '0101000020E6100000BA6B09F9A04722C011363CBD525E4340'::geometry)
              Filter: st_contains(area_polygon, '0101000020E6100000BA6B09F9A04722C011363CBD525E4340'::geometry)
              Buffers: shared hit=5
        ->  Index Scan using testapp_provider_pkey on testapp_provider  (cost=0.14..8.16 rows=1 width=870) (actual time=0.000..0.000 rows=0 loops=6)
              Index Cond: (id = testapp_servicearea.provider_id)
              Buffers: shared hit=6
Planning Time: 0.051 ms
Execution Time: 0.028 ms

--- EXPLAIN ANALYZE WITHOUT any index ---
Sort  (cost=739110.92..739110.92 rows=1 width=934) (actual time=14.249..15.914 rows=6 loops=1)
  Sort Key: testapp_servicearea.id
  Sort Method: quicksort  Memory: 26kB
  Buffers: shared hit=2134
  ->  Nested Loop Left Join  (cost=1000.00..739110.91 rows=1 width=934) (actual time=0.116..15.911 rows=6 loops=1)
        Join Filter: (testapp_servicearea.provider_id = testapp_provider.id)
        Rows Removed by Join Filter: 20
        Buffers: shared hit=2134
        ->  Gather  (cost=1000.00..739098.76 rows=1 width=152) (actual time=0.113..15.898 rows=6 loops=1)
              Workers Planned: 1
              Workers Launched: 1
              Buffers: shared hit=2128
              ->  Parallel Seq Scan on testapp_servicearea  (cost=0.00..738098.66 rows=1 width=152) (actual time=0.002..4.721 rows=3 loops=2)
                    Filter: st_contains(area_polygon, '0101000020E6100000BA6B09F9A04722C011363CBD525E4340'::geometry)
                    Rows Removed by Filter: 50003
                    Buffers: shared hit=2128
        ->  Seq Scan on testapp_provider  (cost=0.00..10.90 rows=90 width=870) (actual time=0.000..0.001 rows=4 loops=6)
              Buffers: shared hit=6
Planning Time: 0.046 ms
Execution Time: 15.928 ms

removed 100003 generated rows
```

### Re-run, 2026-09-27

The same command was run again on the same machine. Summarised rather than pasted
in full, because the plans are identical in shape to the ones above — the same
`Index Cond: (area_polygon ~ ...)` with `st_contains` as the refining `Filter`:

| | 2026-09-23 | 2026-09-27 |
| --- | --- | --- |
| Execution time, with the index | 0.028 ms | 0.018 ms |
| Execution time, index scans off | 15.928 ms | 20.282 ms |
| Shared buffers, with / without | 11 / 2,134 | 9 / 2,133 |
| End-to-end median over 25 runs | 0.56 ms | 0.49 ms |
| GiST index size | 5472 kB | 11 MB |

So the multiple came out nearer 1,100x than 570x. Both runs are real and neither
number is the "true" one: the ratio depends on cache state, on how many parallel
workers the planner launches for the sequential scan, and on table bloat — the
second run's index is twice the size because the table still carried dead tuples
from the first. The claims worth making are the shape of the plan and the order of
magnitude, not the exact factor.

## Reading the plan

* `Index Cond: (area_polygon ~ '...'::geometry)` is the important line. PostGIS
  rewrites `ST_Contains(A, B)` into `A ~ B AND _ST_Contains(A, B)`, where `~` is
  the bounding-box-contains operator. The `~` half is answered from the GiST
  index; the exact `_ST_Contains` predicate shows up as the `Filter` and only
  runs for the rows the bounding box already accepted.
* With the index: **6 rows returned, 11 shared buffers touched, 0.028 ms**.
* Without it: a parallel sequential scan evaluating `ST_Contains` against every
  one of the 100,000 polygons — **2,134 shared buffers, 15.9 ms**, roughly
  **570x slower**, and growing linearly with the table while the index scan does
  not.
* The 0.56 ms median in the timing line is end-to-end Python time (connection,
  psycopg2, GEOS deserialisation of the returned polygons); the 0.028 ms is the
  database's own execution time. The gap is the honest answer to "what does this
  endpoint cost": almost none of it is the spatial query.

## What would break first, and what to do about it

Reasoned, not measured — labelled as such deliberately:

1. **Response size, not query time.** Every result carries its full polygon.
   A few hundred vertices per area times a page of 10 dwarfs the query cost.
   The fix is a serializer that omits `area_polygon` from list responses, or a
   `?fields=` projection. Not done here: the assessment's documented response
   shape includes the polygon, and changing it silently would be the wrong call.
2. **Very large or very complex polygons.** GiST indexes bounding boxes, so a
   country-sized multi-part area has a bounding box that matches almost every
   probe and pushes the work into `_ST_Contains`. `ST_Subdivide` at write time,
   storing many small pieces keyed back to one logical area, is the standard
   remedy.
3. **Hot coordinates.** Repeated searches for the same point (an airport, a
   station) are perfectly cacheable, keyed on a rounded lat/lng. With a
   sub-millisecond query there is nothing to cache yet; the cost only appears
   once serialisation dominates, which is point 1 again.
4. **Write volume.** GiST maintenance on insert is the price of the read speed.
   At transfer-provider scale (thousands of areas, changing rarely) this is
   irrelevant; bulk loads should still drop and rebuild the index rather than
   insert row by row through it.

## `ST_Contains` vs `ST_Intersects`

`area_polygon__contains=point` compiles to `ST_Contains`. For a point argument
the two differ only on the boundary: `ST_Contains` excludes a point lying
exactly on the polygon edge, `ST_Intersects` includes it. "Covered up to but not
including the border" is the stricter, more predictable contract for a pricing
lookup, and `test_point_on_the_boundary_is_not_contained` in
`testapp/tests/test_search_api.py` pins it, so a future change to
`__intersects` is a visible decision rather than a silent one. Both
operators are index-assisted identically, so this is a semantics choice, not a
performance one.
