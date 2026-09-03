import unittest

from app.process_product import ENGLISH_TITLE, translate_attributes, translate_skus


class ProcessProductTests(unittest.TestCase):
    def test_supplier_fields_are_removed_and_product_fields_translated(self):
        source = {
            "normalCpv": [
                {"name": "品牌", "values": ["征程"]},
                {"name": "颜色", "values": ["黑", "玫瑰金"]},
                {"name": "加印LOGO", "values": ["可以"]},
            ]
        }
        self.assertEqual(
            translate_attributes(source),
            {"normalCpv": [{"name": "Color", "values": ["Black", "Rose Gold"]}]},
        )

    def test_sku_identifiers_and_prices_are_unchanged(self):
        source = [
            {
                "sku": "6011544982688",
                "variation_id": "6011544982688",
                "spec_id": "abc",
                "attributes": {"颜色": "黑", "规格": "40mm（四层）"},
                "source_price": "6.60",
                "sale_price": "1.41",
            }
        ]
        result = translate_skus(source)
        for name in ("sku", "variation_id", "spec_id", "source_price", "sale_price"):
            self.assertEqual(result[0][name], source[0][name])
        self.assertEqual(result[0]["attributes"], {"Color": "Black", "Size": "40 mm (4-Layer)"})
        self.assertNotEqual(ENGLISH_TITLE, "")


if __name__ == "__main__":
    unittest.main()
