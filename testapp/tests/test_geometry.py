"""The pluggable geometry registry."""

from django.contrib.gis.geos import GEOSGeometry
from django.test import SimpleTestCase

from testapp.geometry import (
    GeometryFormatError,
    GeometryFormatRegistry,
    normalise_polygon,
    registry,
)

SELF_INTERSECTING_WKT = "POLYGON((0 0, 10 10, 10 0, 0 10, 0 0))"


class RegistryTests(SimpleTestCase):
    def test_known_formats_are_advertised(self):
        self.assertEqual(registry.formats, ["geojson", "wkt"])

    def test_reads_wkt(self):
        polygon = registry.read("POLYGON((0 0, 0 1, 1 1, 1 0, 0 0))", "wkt")

        self.assertEqual(polygon.geom_type, "Polygon")
        self.assertEqual(polygon.srid, 4326)

    def test_reads_ewkt_through_the_wkt_reader(self):
        polygon = registry.read("SRID=4326;POLYGON((0 0, 0 1, 1 1, 1 0, 0 0))", "wkt")

        self.assertEqual(polygon.srid, 4326)

    def test_reads_geojson_from_a_string(self):
        polygon = registry.read(
            '{"type": "Polygon", "coordinates": [[[0,0],[0,1],[1,1],[1,0],[0,0]]]}',
            "geojson",
        )

        self.assertEqual(polygon.num_points, 5)

    def test_reads_geojson_from_a_dict(self):
        polygon = registry.read(
            {
                "type": "Polygon",
                "coordinates": [[[0, 0], [0, 1], [1, 1], [1, 0], [0, 0]]],
            },
            "geojson",
        )

        self.assertEqual(polygon.geom_type, "Polygon")

    def test_format_name_is_case_insensitive(self):
        self.assertEqual(
            registry.read("POLYGON((0 0,0 1,1 1,1 0,0 0))", "WKT").srid, 4326
        )

    def test_unknown_format_is_reported_with_the_known_ones(self):
        with self.assertRaises(GeometryFormatError) as ctx:
            registry.read("anything", "shapefile")

        self.assertIn("geojson", str(ctx.exception))

    def test_unparsable_payload_raises_a_format_error(self):
        with self.assertRaises(GeometryFormatError):
            registry.read("not a geometry", "wkt")

    def test_a_format_cannot_be_registered_twice(self):
        local = GeometryFormatRegistry()
        local.register("wkt")(lambda raw: GEOSGeometry(raw))

        with self.assertRaises(ValueError):
            local.register("wkt")(lambda raw: GEOSGeometry(raw))

    def test_a_new_format_needs_one_function(self):
        """The seam: onboarding a new geometry source is a single registration."""
        local = GeometryFormatRegistry()

        @local.register("bbox")
        def read_bbox(raw):
            minx, miny, maxx, maxy = (float(part) for part in raw.split(","))
            return GEOSGeometry(
                "POLYGON((%s %s, %s %s, %s %s, %s %s, %s %s))"
                % (minx, miny, minx, maxy, maxx, maxy, maxx, miny, minx, miny)
            )

        polygon = local.read("0,0,1,1", "bbox")

        self.assertEqual(polygon.geom_type, "Polygon")
        self.assertEqual(polygon.srid, 4326)


class NormalisePolygonTests(SimpleTestCase):
    def test_rejects_a_non_polygon_geometry(self):
        with self.assertRaises(GeometryFormatError) as ctx:
            normalise_polygon(GEOSGeometry("POINT(1 1)"))

        self.assertIn("Point", str(ctx.exception))

    def test_rejects_a_self_intersecting_ring(self):
        with self.assertRaises(GeometryFormatError):
            normalise_polygon(GEOSGeometry(SELF_INTERSECTING_WKT))

    def test_assumes_wgs84_when_no_srid_is_given(self):
        polygon = normalise_polygon(GEOSGeometry("POLYGON((0 0,0 1,1 1,1 0,0 0))"))

        self.assertEqual(polygon.srid, 4326)

    def test_reprojects_a_polygon_given_in_another_srid(self):
        """Web-mercator metres in, degrees out."""
        mercator = GEOSGeometry(
            "SRID=3857;POLYGON((0 0, 0 1000, 1000 1000, 1000 0, 0 0))"
        )

        polygon = normalise_polygon(mercator)

        self.assertEqual(polygon.srid, 4326)
        self.assertLess(abs(polygon.centroid.x), 1.0)
