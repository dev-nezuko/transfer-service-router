"""Shared fixtures for the test suite.

Geometries are built from WKT through ``GEOSGeometry`` rather than the
``Polygon`` constructor: Django 3.2 does not declare ctypes ``argtypes`` for
``GEOSGeom_createPolygon``, which breaks that constructor against recent GEOS
builds on arm64. The WKT reader is unaffected and is what the API itself uses.
"""

from testapp.models import Provider

# A 10x10 square with its lower-left corner on the origin.
SQUARE_WKT = "SRID=4326;POLYGON((0 0, 0 10, 10 10, 10 0, 0 0))"
# Overlaps the square above between x/y 5 and 10.
OVERLAPPING_WKT = "SRID=4326;POLYGON((5 5, 5 15, 15 15, 15 5, 5 5))"
# Entirely disjoint from both squares above.
FAR_AWAY_WKT = "SRID=4326;POLYGON((40 40, 40 50, 50 50, 50 40, 40 40))"


def make_provider(**overrides):
    """Create a Provider, letting individual fields be overridden."""
    defaults = {
        "name": "Provider One",
        "email": "provider1@example.com",
        "phone": "+12345678901",
        "language": "English",
        "currency": "USD",
    }
    defaults.update(overrides)
    return Provider.objects.create(**defaults)
