# Captured API session

Every console block below is real, unedited output recorded on 2026-09-23
against a freshly migrated and seeded database:

```
python manage.py migrate
python manage.py seed_demo
python manage.py runserver 127.0.0.1:8300
```

Environment: Python 3.10.14, Django 3.2.12, PostgreSQL 17.6 with PostGIS 3.5.3
(Postgres.app, macOS arm64). `$BASE` is `http://localhost:8300`.

## Point-in-polygon search

The seeded Lisbon areas deliberately overlap, so the city-centre coordinate
matches two of them, Times Square matches one, and a point in the Atlantic
matches none.

```console
$ curl -s "$BASE/testapp/search_service_area/?lat=38.7369&lng=-9.1399" | python3 -m json.tool --compact
{"count":2,"next":null,"previous":null,"results":[{"id":1,"name":"Lisbon City","price":"24.50","area_polygon":{"type":"Polygon","coordinates":[[[-9.25,38.68],[-9.25,38.8],[-9.05,38.8],[-9.05,38.68],[-9.25,38.68]]]},"provider":1},{"id":3,"name":"Lisbon Centre Premium","price":"58.75","area_polygon":{"type":"Polygon","coordinates":[[[-9.2,38.7],[-9.2,38.76],[-9.1,38.76],[-9.1,38.7],[-9.2,38.7]]]},"provider":2}]}

$ curl -s "$BASE/testapp/search_service_area/?lat=40.7580&lng=-73.9855" | python3 -m json.tool --compact
{"count":1,"next":null,"previous":null,"results":[{"id":7,"name":"Manhattan","price":"65.00","area_polygon":{"type":"Polygon","coordinates":[[[-74.02,40.7],[-74.02,40.88],[-73.91,40.88],[-73.91,40.7],[-74.02,40.7]]]},"provider":4}]}

$ curl -s "$BASE/testapp/search_service_area/?lat=0&lng=0" | python3 -m json.tool --compact
{"count":0,"next":null,"previous":null,"results":[]}
```

## Input validation

`lat` and `lng` are validated by a serializer before any query runs. Failures
come back as one readable `message` string rather than a nested error object.

```console
$ curl -s -w '\nHTTP %{http_code}\n' "$BASE/testapp/search_service_area/?lat=91&lng=-9.14"
{"message":"lat: Ensure this value is less than or equal to 90.0."}
HTTP 400

$ curl -s -w '\nHTTP %{http_code}\n' "$BASE/testapp/search_service_area/?lng=-9.14"
{"message":"lat: This field is required."}
HTTP 400
```

## Pagination

Both list endpoints are paginated, and `?page_size=` is honoured up to
`API_MAX_PAGE_SIZE` (100 by default) so that a client cannot turn a paginated
endpoint back into a full table read.

```console
$ curl -s "$BASE/testapp/provider/?page_size=2" | python3 -m json.tool
{
    "count": 4,
    "next": "http://localhost:8300/testapp/provider/?page=2&page_size=2",
    "previous": null,
    "results": [
        {
            "id": 1,
            "name": "Aurora Transfers",
            "email": "ops@auroratransfers.example",
            "phone": "+351210000001",
            "language": "Portuguese",
            "currency": "EUR"
        },
        {
            "id": 2,
            "name": "Lisboa Prime Cars",
            "email": "ops@lisboaprime.example",
            "phone": "+351210000002",
            "language": "Portuguese",
            "currency": "EUR"
        }
    ]
}

$ curl -s "$BASE/testapp/service_area/?page_size=1" | python3 -m json.tool
{
    "count": 8,
    "next": "http://localhost:8300/testapp/service_area/?page=2&page_size=1",
    "previous": null,
    "results": [
        {
            "id": 1,
            "name": "Lisbon City",
            "price": "24.50",
            "area_polygon": {
                "type": "Polygon",
                "coordinates": [
                    [
                        [
                            -9.25,
                            38.68
                        ],
                        [
                            -9.25,
                            38.8
                        ],
                        [
                            -9.05,
                            38.8
                        ],
                        [
                            -9.05,
                            38.68
                        ],
                        [
                            -9.25,
                            38.68
                        ]
                    ]
                ]
            },
            "provider": 1
        }
    ]
}
```

## Writes, uniqueness and geometry validation

A self-intersecting ring is rejected by the serializer rather than stored: the
`geometry(Polygon,4326)` column accepts it, but every later `ST_Contains`
against it is undefined.

```console
$ curl -s -X POST "$BASE/testapp/provider/" -H 'Content-Type: application/json' -d '{"name": "Tagus Cabs", "email": "ops@taguscabs.example", "phone": "+351210000009", "language": "Portuguese", "currency": "EUR"}' -w '\nHTTP %{http_code}\n'
{"id":5,"name":"Tagus Cabs","email":"ops@taguscabs.example","phone":"+351210000009","language":"Portuguese","currency":"EUR"}
HTTP 201

$ curl -s -X POST "$BASE/testapp/provider/" -H 'Content-Type: application/json' -d '{"name": "Duplicate", "email": "ops@taguscabs.example", "phone": "+351210000010", "language": "Portuguese", "currency": "EUR"}' -w '\nHTTP %{http_code}\n'
{"email":["A provider with this email already exists, please use a different one!"]}
HTTP 400

$ curl -s -X POST "$BASE/testapp/service_area/" -H 'Content-Type: application/json' -d '{"name": "Bow tie", "price": "10.00", "provider": 1, "area_polygon": {"type": "Polygon", "coordinates": [[[0, 0], [10, 10], [10, 0], [0, 10], [0, 0]]]}}' -w '\nHTTP %{http_code}\n'
{"area_polygon":["invalid polygon: Self-intersection[5 5]"]}
HTTP 400

$ curl -s -X POST "$BASE/testapp/service_area/" -H 'Content-Type: application/json' -d '{"name": "Tagus North", "price": "19.90", "provider": 5, "area_polygon": {"type": "Polygon", "coordinates": [[[-9.16, 38.72], [-9.16, 38.78], [-9.08, 38.78], [-9.08, 38.72], [-9.16, 38.72]]]}}' -w '\nHTTP %{http_code}\n'
{"id":9,"name":"Tagus North","price":"19.90","area_polygon":{"type":"Polygon","coordinates":[[[-9.16,38.72],[-9.16,38.78],[-9.08,38.78],[-9.08,38.72],[-9.16,38.72]]]},"provider":5}
HTTP 201

$ curl -s "$BASE/testapp/search_service_area/?lat=38.7369&lng=-9.1399" | python3 -c 'import sys, json; d = json.load(sys.stdin); print(json.dumps([(r["id"], r["name"], r["price"]) for r in d["results"]]))'
[[1, "Lisbon City", "24.50"], [3, "Lisbon Centre Premium", "58.75"], [9, "Tagus North", "19.90"]]
```

The last call shows the area created two steps earlier taking part in the
search immediately: the search reads the same table, with nothing to rebuild.

## The `API_REQUIRE_AUTH` switch

The assessment's documented surface is a fully open API, so anonymous access
stays the default. With `API_REQUIRE_AUTH=true` reads stay anonymous and every
write requires an authenticated user. Captured against a second server started
with that variable set, on port 8302, with `$BASE` pointing at it:

```console
$ curl -s -o /dev/null -w 'HTTP %{http_code}\n' "$BASE/testapp/search_service_area/?lat=38.7369&lng=-9.1399"
HTTP 200

$ curl -s -w '\nHTTP %{http_code}\n' -X DELETE "$BASE/testapp/provider/5/"
{"detail":"Authentication credentials were not provided."}
HTTP 403

$ curl -s -u "admin:$ADMIN_PASSWORD" -w '\nHTTP %{http_code}\n' -X DELETE "$BASE/testapp/provider/5/"

HTTP 204
```

## Bulk import through the geometry registry

```console
$ python manage.py import_service_areas examples/service_areas.json --dry-run
created Lisbon Riverside (Aurora Transfers)
created Sintra Hills (Lisboa Prime Cars)
2 created, 0 updated (dry run: rolled back)

$ python manage.py import_service_areas --help | grep -A2 -- --format
  --format {geojson,wkt}
                        Geometry format of the 'geometry' field (default:
                        geojson).
```

## Test suite and linters

```console
$ python manage.py test
Creating test database for alias 'default'...
System check identified no issues (0 silenced).
..................................................................................
----------------------------------------------------------------------
Ran 82 tests in 0.742s

OK
Destroying test database for alias 'default' ('test_mozio_uplift')...

$ ruff check .
All checks passed!

$ black --check .
All done! 31 files would be left unchanged.
```
