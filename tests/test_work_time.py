import unittest
from datetime import datetime, time
from projectit.work_time import split_work_time


class WorkTimeTests(unittest.TestCase):
    def split(self, start, end, regular_start=time(8), regular_end=time(17)):
        return split_work_time(datetime.fromisoformat(start), datetime.fromisoformat(end), regular_start, regular_end)

    def test_regular_work(self):
        rows = self.split("2026-09-29 09:00:00", "2026-09-29 16:00:00")
        self.assertEqual([(b-a).total_seconds() for a,b,_ in rows], [7*3600])
        self.assertTrue(rows[0][2])

    def test_overtime_splits_preserve_every_second(self):
        rows = self.split("2026-09-29 07:00:00", "2026-09-29 18:00:00")
        self.assertEqual([regular for _,_,regular in rows], [False, True, False])
        self.assertEqual(sum((b-a).total_seconds() for a,b,_ in rows), 11*3600)
        self.assertEqual(rows[0][1], rows[1][0])
        self.assertEqual(rows[1][1], rows[2][0])
        self.assertEqual(rows[-1][1].hour, 18)

    def test_boundary_checkout_has_no_zero_or_negative_segment(self):
        for end in ("08:00:00", "17:00:00"):
            rows = self.split("2026-09-29 07:00:00", "2026-09-29 " + end)
            self.assertTrue(all(b > a for a,b,_ in rows))

    def test_overnight_work_is_not_lost(self):
        rows = self.split("2026-09-29 22:00:00", "2026-09-30 09:00:00")
        self.assertEqual([regular for _,_,regular in rows], [False, True])
        self.assertEqual(sum((b-a).total_seconds() for a,b,_ in rows), 11*3600)

    def test_overnight_regular_window(self):
        rows = self.split("2026-09-29 21:00:00", "2026-09-30 07:00:00", time(22), time(6))
        self.assertEqual([regular for _,_,regular in rows], [False, True, False])
        self.assertEqual([(b-a).total_seconds() for a,b,_ in rows], [3600,8*3600,3600])

    def test_early_morning_in_previous_night_window(self):
        rows = self.split("2026-09-30 01:00:00", "2026-09-30 05:00:00", time(22), time(6))
        self.assertEqual(len(rows), 1)
        self.assertTrue(rows[0][2])

    def test_invalid_interval_and_equal_settings(self):
        with self.assertRaises(ValueError):
            self.split("2026-09-29 09:00:00", "2026-09-29 09:00:00")
        with self.assertRaises(ValueError):
            self.split("2026-09-29 09:00:00", "2026-09-29 10:00:00", time(8), time(8))


if __name__ == "__main__":
    unittest.main()
