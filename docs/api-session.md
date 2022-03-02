# Captured API session

Every console block below is real output, recorded on 2026-11-08 against the
Docker Compose stack started from a clean volume:

```
DJANGO_SUPERUSER_PASSWORD=... docker compose up --build
```

Environment: Python 3.12, Django 5.2.19, DRF 3.18.3, gunicorn 26.2.0, on
`ghcr.io/osgeo/gdal:ubuntu-small-3.12.0`; PostgreSQL 17 with PostGIS 3.5 from
`postgis/postgis:17-3.5`. Requests were made from a container on the compose
network, so `$BASE` is `http://api:8000` (from the host it is
`http://localhost:8300`). Responses are printed as returned, without
pretty-printing.

## Point-in-polygon search

The seeded Lisbon areas deliberately overlap, so the city-centre coordinate
matches two of them, Times Square matches one, and a point in the Atlantic
matches none.

```console
$ curl -s "$BASE/testapp/search_service_area/?lat=38.7369&lng=-9.1399"
{"count":2,"next":null,"previous":null,"results":[{"id":1,"name":"Lisbon City","price":"24.50","area_polygon":{"type":"Polygon","coordinates":[[[-9.25,38.68],[-9.25,38.8],[-9.05,38.8],[-9.05,38.68],[-9.25,38.68]]]},"provider":1},{"id":3,"name":"Lisbon Centre Premium","price":"58.75","area_polygon":{"type":"Polygon","coordinates":[[[-9.2,38.7],[-9.2,38.76],[-9.1,38.76],[-9.1,38.7],[-9.2,38.7]]]},"provider":2}]}

$ curl -s "$BASE/testapp/search_service_area/?lat=40.7580&lng=-73.9855"
{"count":1,"next":null,"previous":null,"results":[{"id":7,"name":"Manhattan","price":"65.00","area_polygon":{"type":"Polygon","coordinates":[[[-74.02,40.7],[-74.02,40.88],[-73.91,40.88],[-73.91,40.7],[-74.02,40.7]]]},"provider":4}]}

$ curl -s "$BASE/testapp/search_service_area/?lat=0&lng=0"
{"count":0,"next":null,"previous":null,"results":[]}
```

## Input validation

`lat` and `lng` are validated by a serializer before any query runs. Failures
come back as one readable `message` string rather than a nested error object.
`nan` deserves a mention: it parses as a float and every range comparison
with it is false, so it is DRF's `FloatField` that has to refuse it.

```console
$ curl -s -w '\nHTTP %{http_code}\n' "$BASE/testapp/search_service_area/?lat=91&lng=-9.14"
{"message":"lat: Ensure this value is less than or equal to 90.0."}
HTTP 400

$ curl -s -w '\nHTTP %{http_code}\n' "$BASE/testapp/search_service_area/?lng=-9.14"
{"message":"lat: This field is required."}
HTTP 400

$ curl -s -w '\nHTTP %{http_code}\n' "$BASE/testapp/search_service_area/?lat=nan&lng=-9.14"
{"message":"lat: A valid number is required."}
HTTP 400
```

## Pagination

Both list endpoints are paginated, and `?page_size=` is honoured up to
`API_MAX_PAGE_SIZE` (100 by default) so that a client cannot turn a paginated
endpoint back into a full table read.

```console
$ curl -s "$BASE/testapp/provider/?page_size=2"
{"count":4,"next":"http://api:8000/testapp/provider/?page=2&page_size=2","previous":null,"results":[{"id":1,"name":"Aurora Transfers","email":"ops@auroratransfers.example","phone":"+351210000001","language":"Portuguese","currency":"EUR"},{"id":2,"name":"Lisboa Prime Cars","email":"ops@lisboaprime.example","phone":"+351210000002","language":"Portuguese","currency":"EUR"}]}
```

## Writes, uniqueness and validation

A self-intersecting ring is rejected by the serializer rather than stored: the
`geometry(Polygon,4326)` column accepts it, but every later `ST_Contains`
against it is undefined. Negative prices are refused too; zero is allowed.

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

$ curl -s -X POST "$BASE/testapp/service_area/" -H 'Content-Type: application/json' -d '{"name": "Refund zone", "price": "-5.00", "provider": 1}' -w '\nHTTP %{http_code}\n'
{"price":["Ensure this value is greater than or equal to 0."]}
HTTP 400

$ curl -s -X POST "$BASE/testapp/service_area/" -H 'Content-Type: application/json' -d '{"name": "Tagus North", "price": "19.90", "provider": 5, "area_polygon": {"type": "Polygon", "coordinates": [[[-9.16, 38.72], [-9.16, 38.78], [-9.08, 38.78], [-9.08, 38.72], [-9.16, 38.72]]]}}' -w '\nHTTP %{http_code}\n'
{"id":9,"name":"Tagus North","price":"19.90","area_polygon":{"type":"Polygon","coordinates":[[[-9.16,38.72],[-9.16,38.78],[-9.08,38.78],[-9.08,38.72],[-9.16,38.72]]]},"provider":5}
HTTP 201

$ curl -s "$BASE/testapp/search_service_area/?lat=38.7369&lng=-9.1399"
{"count":3,"next":null,"previous":null,"results":[{"id":1,"name":"Lisbon City","price":"24.50","area_polygon":{"type":"Polygon","coordinates":[[[-9.25,38.68],[-9.25,38.8],[-9.05,38.8],[-9.05,38.68],[-9.25,38.68]]]},"provider":1},{"id":3,"name":"Lisbon Centre Premium","price":"58.75","area_polygon":{"type":"Polygon","coordinates":[[[-9.2,38.7],[-9.2,38.76],[-9.1,38.76],[-9.1,38.7],[-9.2,38.7]]]},"provider":2},{"id":9,"name":"Tagus North","price":"19.90","area_polygon":{"type":"Polygon","coordinates":[[[-9.16,38.72],[-9.16,38.78],[-9.08,38.78],[-9.08,38.72],[-9.16,38.72]]]},"provider":5}]}
```

The last call shows the area created two steps earlier taking part in the
search immediately: the search reads the same table, with nothing to rebuild.

## The `API_REQUIRE_AUTH` switch

Anonymous access is the default. With `API_REQUIRE_AUTH=true` reads stay
anonymous and every write requires an authenticated user. Captured after
restarting the same stack with `API_REQUIRE_AUTH=true docker compose up`, with
`ADMIN_PASSWORD` holding the value given as `DJANGO_SUPERUSER_PASSWORD`:

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
$ docker compose exec api python3 manage.py import_service_areas examples/service_areas.json --dry-run
created Lisbon Riverside (Aurora Transfers)
created Sintra Hills (Lisboa Prime Cars)
2 created, 0 updated (dry run: rolled back)
```
