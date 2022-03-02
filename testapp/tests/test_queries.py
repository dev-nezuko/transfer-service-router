"""The spatial query object and the index it depends on."""

from django.contrib.gis.geos import GEOSGeometry, Point
from django.db import connection
from django.test import TestCase

from testapp.models import ServiceArea
from testapp.queries import (
    ServiceAreaCoverageQuery,
    point_from_lat_lng,
    service_area_coverage,
)
from testapp.tests.factories import OVERLAPPING_WKT, SQUARE_WKT, make_provider


class PointFromLatLngTests(TestCase):
    def test_builds_a_wgs84_point_with_x_as_longitude(self):
        point = point_from_lat_lng(lat=52.5, lng=13.4)

        self.assertEqual(point.srid, 4326)
        self.assertEqual((point.x, point.y), (13.4, 52.5))

    def test_accepts_numeric_strings(self):
        point = point_from_lat_lng("1.5", "2.5")

        self.assertEqual((point.x, point.y), (2.5, 1.5))


class ServiceAreaCoverageQueryTests(TestCase):
    def setUp(self):
        self.provider = make_provider()
        self.square = ServiceArea.objects.create(
            name="City Center",
            price="10.00",
            provider=self.provider,
            area_polygon=GEOSGeometry(SQUARE_WKT),
        )
        self.overlap = ServiceArea.objects.create(
            name="Suburbs",
            price="20.00",
            provider=self.provider,
            area_polygon=GEOSGeometry(OVERLAPPING_WKT),
        )

    def test_returns_every_containing_area_ordered_by_id(self):
        result = service_area_coverage.for_lat_lng(lat=7, lng=7)

        self.assertEqual([area.id for area in result], [self.square.id, self.overlap.id])

    def test_excludes_areas_that_do_not_contain_the_point(self):
        result = service_area_coverage.for_lat_lng(lat=1, lng=1)

        self.assertEqual([area.name for area in result], ["City Center"])

    def test_rejects_a_point_in_the_wrong_srid(self):
        """A mismatched SRID must fail loudly rather than return nothing."""
        with self.assertRaises(ValueError):
            service_area_coverage.for_point(Point(7, 7, srid=3857))

    def test_accepts_a_narrowed_base_queryset(self):
        other = make_provider(email="other@example.com", phone="+12345678999")
        ServiceArea.objects.create(
            name="Rival Area",
            price="5.00",
            provider=other,
            area_polygon=GEOSGeometry(SQUARE_WKT),
        )

        query = ServiceAreaCoverageQuery(ServiceArea.objects.filter(provider=other))
        result = query.for_lat_lng(lat=5, lng=5)

        self.assertEqual([area.name for area in result], ["Rival Area"])

    def test_provider_is_joined_in_so_serialisation_does_not_re_query(self):
        result = list(service_area_coverage.for_lat_lng(lat=7, lng=7))

        with self.assertNumQueries(0):
            [area.provider.name for area in result]

    def test_explain_returns_a_query_plan(self):
        plan = service_area_coverage.explain_for_point(point_from_lat_lng(7, 7))

        self.assertIn("testapp_servicearea", plan)


class SpatialIndexTests(TestCase):
    """The GiST index is the whole scalability story; assert it is really there."""

    def test_area_polygon_has_a_gist_index(self):
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT i.indexname, a.amname
                FROM pg_indexes i
                JOIN pg_class c ON c.relname = i.indexname
                JOIN pg_am a ON a.oid = c.relam
                WHERE i.tablename = %s
                """,
                [ServiceArea._meta.db_table],
            )
            access_methods = dict(cursor.fetchall())

        gist_indexes = [name for name, am in access_methods.items() if am == "gist"]
        self.assertTrue(
            gist_indexes,
            "no GiST index on %s: the point-in-polygon search would fall back "
            "to a sequential scan (indexes found: %s)"
            % (ServiceArea._meta.db_table, access_methods),
        )
