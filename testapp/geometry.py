"""Pluggable geometry sources.

Provider onboarding is the part of this service most likely to change: today
areas arrive as GeoJSON over the API, tomorrow a partner hands over a WKT dump
or a shapefile export. Rather than scatter ``GEOSGeometry(...)`` calls through
commands and views, formats are registered against a small registry and looked
up by name. Supporting a new source is one function plus one decorator, and the
normalisation rules (SRID, geometry type, validity) stay in a single place.
"""

from django.contrib.gis.gdal.error import GDALException
from django.contrib.gis.geos import GEOSGeometry
from django.contrib.gis.geos.error import GEOSException

from .queries import WGS84_SRID


class GeometryFormatError(ValueError):
    """Raised when a payload cannot be read as a valid WGS 84 polygon."""


class GeometryFormatRegistry:
    """Name -> reader registry for polygon sources."""

    def __init__(self):
        self._readers = {}

    def register(self, name):
        """Decorator registering a ``reader(raw) -> GEOSGeometry``."""

        def decorator(func):
            key = name.lower()
            if key in self._readers:
                raise ValueError("geometry format %r is already registered" % key)
            self._readers[key] = func
            return func

        return decorator

    @property
    def formats(self):
        return sorted(self._readers)

    def read(self, raw, format_name):
        """Read ``raw`` in ``format_name`` and return a normalised polygon."""
        try:
            reader = self._readers[format_name.lower()]
        except KeyError as exc:
            raise GeometryFormatError(
                "unknown geometry format %r (known: %s)"
                % (format_name, ", ".join(self.formats))
            ) from exc
        return normalise_polygon(reader(raw))


def normalise_polygon(geometry):
    """Validate ``geometry`` and coerce it to a WGS 84 polygon."""
    if geometry.geom_type != "Polygon":
        raise GeometryFormatError("expected a Polygon, got %s" % geometry.geom_type)
    if not geometry.valid:
        raise GeometryFormatError("invalid polygon: %s" % geometry.valid_reason)
    if geometry.srid is None:
        # No SRID in the payload: the API contract says coordinates are WGS 84.
        geometry.srid = WGS84_SRID
    elif geometry.srid != WGS84_SRID:
        geometry.transform(WGS84_SRID)
    return geometry


registry = GeometryFormatRegistry()


def _parse(raw):
    """GEOSGeometry accepts WKT, EWKT, HEXEWKB and GeoJSON strings alike."""
    try:
        return GEOSGeometry(raw)
    except (GEOSException, GDALException, ValueError, TypeError) as exc:
        raise GeometryFormatError(str(exc)) from exc


@registry.register("geojson")
def read_geojson(raw):
    """Read a GeoJSON geometry, given either as a string or as a dict."""
    if isinstance(raw, dict | list):
        import json

        raw = json.dumps(raw)
    return _parse(raw)


@registry.register("wkt")
def read_wkt(raw):
    """Read WKT or EWKT (``SRID=4326;POLYGON((...))``)."""
    return _parse(raw)
