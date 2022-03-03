import unittest
from .coordinates import parse_coordinates


class CoordinateTests(unittest.TestCase):
    def test_valid_and_boundary_values(self):
        for latitude, longitude in [('0','0'),('-90','-180'),('90','180'),('12.5','-3.25')]:
            self.assertEqual(parse_coordinates(latitude,longitude),(float(latitude),float(longitude)))

    def test_missing_inputs(self):
        for latitude, longitude in [(None,'0'),('0',None),('','0'),('0','')]:
            with self.subTest(lat=latitude,lng=longitude), self.assertRaises(ValueError):
                parse_coordinates(latitude,longitude)

    def test_rejects_nonfinite_and_out_of_range(self):
        for latitude,longitude in [('NaN','0'),('0','inf'),('91','0'),('0','181'),('abc','0')]:
            with self.subTest(lat=latitude,lng=longitude),self.assertRaises(ValueError):
                parse_coordinates(latitude,longitude)
