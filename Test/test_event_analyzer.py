import unittest
from datetime import datetime
from analysis.event_analyzer import generate_corporate_events, _parse_date


class TestEventAnalyzer(unittest.TestCase):

    def test_parse_date_valid(self):
        self.assertEqual(_parse_date("2023-05-10").year, 2023)
        self.assertEqual(_parse_date("May 2022").year, 2022)
        self.assertEqual(_parse_date("2021").year, 2021)

    def test_parse_date_invalid(self):
        self.assertEqual(_parse_date("Not A Date").year, datetime.min.year)
        self.assertEqual(_parse_date("").year, datetime.min.year)
        self.assertEqual(_parse_date("N/A").year, datetime.min.year)

    def test_generate_events_filtered_last_5_years(self):
        input_text = """
        In 2024, the company acquired AlphaTech.
        In 2023, they launched a new cloud service.
        In 2017, a small local expansion occurred.
        """
        result = generate_corporate_events("TestCorp", text=input_text)
        result_lower = result.lower()

        # ✅ It must include recent years
        self.assertIn("2024", result)
        self.assertIn("2023", result)

        # ✅ It must exclude older than 5 years (2017 --> filtered out)
        self.assertNotIn("2017", result)

    def test_generate_events_ai_fallback(self):
        """ Ensure fallback still returns events """
        text = ""  # triggers Wikipedia or final fallback
        result = generate_corporate_events("UnknownCorp", text=text)
        self.assertTrue(len(result) > 0)
        self.assertIn("Event Description", result)


if __name__ == "__main__":
    unittest.main()
