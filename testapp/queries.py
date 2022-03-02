"""Read-side query objects for :mod:`testapp`.

The point-in-polygon lookup is the heart of this service, so it lives here as a
named query object rather than inline in a viewset. That keeps the spatial
reasoning (SRID, operator choice, ordering) in one testable place and lets the
same query be reused by the API, the management commands and the benchmark.

Why ``ST_Contains`` and not ``ST_Intersects``
---------------------------------------------
``__contains`` compiles to ``ST_Contains(area_polygon, point)``. For a point
argument the only difference between the two is the boundary: ``ST_Contains``
excludes points lying exactly on the polygon edge, ``ST_Intersects`` includes
them. A service area that covers a coordinate "up to but not including its
border" is the stricter, more predictable contract for a pricing lookup, and it
is the behaviour the test suite pins. Both operators are index-assisted in the
same way, so this is a semantics decision, not a performance one.

How the index is used
---------------------
``ServiceArea.area_polygon`` is a ``PolygonField`` with ``spatial_index=True``
(the default), so migration ``0007`` emits
``CREATE INDEX ... USING GIST ("area_polygon")`` alongside the ``ADD COLUMN``.
PostGIS then inlines ``ST_Contains(a, b)`` into ``a ~ b AND _ST_Contains(a, b)``:
the ``~`` bounding-box-contains operator is answered from the GiST index, and the
exact ``_ST_Contains`` predicate only runs for the handful of candidate rows that
survive it. Over a 100k-row table that two-phase plan is an index scan touching
5 buffers instead of a parallel sequential scan touching 2128 — see the
"Scalability" section of the README for the measured ``EXPLAIN ANALYZE``, which
``manage.py benchmark_search`` reproduces.
"""

from django.contrib.gis.geos import Point

from .models import ServiceArea

#: WGS 84 — the SRID declared on ``ServiceArea.area_polygon``. Every point fed
#: into the query must carry it, otherwise PostGIS raises a mixed-SRID error.
WGS84_SRID = 4326


def point_from_lat_lng(lat, lng):
    """Build a WGS 84 :class:`Point` from a latitude/longitude pair.

    ``Point`` takes ``(x, y)``, i.e. ``(longitude, latitude)``. Passing them the
    other way round is the classic GeoDjango bug: it silently returns wrong
    results instead of failing, so the conversion is centralised here.
    """
    return Point(float(lng), float(lat), srid=WGS84_SRID)


class ServiceAreaCoverageQuery:
    """Service areas whose polygon contains a given point.

    Instantiated with an optional base queryset so callers can narrow the search
    (for example to a single provider) without reimplementing the spatial part.
    """

    def __init__(self, base_queryset=None):
        self._base_queryset = (
            ServiceArea.objects.all() if base_queryset is None else base_queryset
        )

    def for_point(self, point):
        """Return the matching areas, ordered for stable pagination.

        ``select_related`` avoids one provider query per row when the results are
        serialised; the explicit ``order_by`` stops PostgreSQL from returning
        rows in an arbitrary order between pages of the same result set.
        """
        if point.srid != WGS84_SRID:
            raise ValueError(
                "point must be in SRID %d, got %r" % (WGS84_SRID, point.srid)
            )
        return (
            self._base_queryset.select_related("provider")
            .filter(area_polygon__contains=point)
            .order_by("id")
        )

    def for_lat_lng(self, lat, lng):
        """Convenience wrapper around :meth:`for_point`."""
        return self.for_point(point_from_lat_lng(lat, lng))

    def explain_for_point(self, point, analyze=True):
        """Return the PostgreSQL query plan for the spatial lookup."""
        return self.for_point(point).explain(analyze=analyze, buffers=analyze)


#: Module-level default used by the API layer.
service_area_coverage = ServiceAreaCoverageQuery()
