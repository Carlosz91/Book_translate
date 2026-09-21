import unittest

from traducir_pdf import mapear_fuente_reportlab


class EstiloFuenteTest(unittest.TestCase):
    def test_mapear_fuente_reportlab_usa_fuentes_similares_al_original(self):
        self.assertEqual(mapear_fuente_reportlab("TimesNewRomanPSMT"), "Times-Roman")
        self.assertEqual(mapear_fuente_reportlab("ArialMT"), "Helvetica")
        self.assertEqual(mapear_fuente_reportlab("CourierNewPSMT"), "Courier")


if __name__ == "__main__":
    unittest.main()
