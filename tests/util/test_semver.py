import pytest

from esphome_deployment.util.semver import SemVerVersion
from tests import TestBase


class SemVerVersionParsingTest(TestBase):

    def test_parses_standard_version(self):
        v = SemVerVersion("2025.12.3")
        self.assertEqual(v.major, 2025)
        self.assertEqual(v.minor, 12)
        self.assertEqual(v.patch, 3)
        self.assertEqual(v.suffix, "")

    def test_parses_version_with_v_prefix(self):
        v = SemVerVersion("v2025.12.3")
        self.assertEqual(v.major, 2025)
        self.assertEqual(v.minor, 12)
        self.assertEqual(v.patch, 3)

    def test_parses_version_with_leading_whitespace(self):
        v = SemVerVersion("  2025.12.3")
        self.assertEqual(v.major, 2025)
        self.assertEqual(v.minor, 12)
        self.assertEqual(v.patch, 3)

    def test_parses_version_with_suffix(self):
        v = SemVerVersion("2025.12.3b4")
        self.assertEqual(v.major, 2025)
        self.assertEqual(v.minor, 12)
        self.assertEqual(v.patch, 3)
        self.assertEqual(v.suffix, "b4")

    def test_parses_version_with_dev_suffix(self):
        v = SemVerVersion("2025.12.3-dev")
        self.assertEqual(v.patch, 3)
        self.assertEqual(v.suffix, "-dev")

    def test_raises_on_too_few_parts(self):
        with self.assertRaises(ValueError):
            SemVerVersion("2025.12")

    def test_raises_on_too_many_parts(self):
        with self.assertRaises(ValueError):
            SemVerVersion("2025.12.3.4")

    def test_raises_on_non_numeric_patch(self):
        with self.assertRaises(ValueError):
            SemVerVersion("2025.12.patch")

    def test_raises_on_empty_string(self):
        with self.assertRaises((ValueError, IndexError)):
            SemVerVersion("")


class SemVerVersionStrTest(TestBase):

    def test_str_returns_version_without_suffix(self):
        v = SemVerVersion("2025.12.3")
        self.assertEqual(str(v), "2025.12.3")

    def test_str_includes_suffix(self):
        v = SemVerVersion("2025.12.3b4")
        self.assertEqual(str(v), "2025.12.3b4")

    def test_str_includes_dev_suffix(self):
        v = SemVerVersion("2025.12.3-dev")
        self.assertEqual(str(v), "2025.12.3-dev")

    def test_str_strips_v_prefix(self):
        v = SemVerVersion("v2025.12.3")
        self.assertEqual(str(v), "2025.12.3")


class SemVerVersionEqualityTest(TestBase):

    def test_equal_versions_are_equal(self):
        self.assertEqual(SemVerVersion("2025.12.3"), SemVerVersion("2025.12.3"))

    def test_versions_with_same_numbers_but_different_suffix_are_not_equal(self):
        self.assertNotEqual(SemVerVersion("2025.12.3"), SemVerVersion("2025.12.3b1"))

    def test_versions_differing_in_patch_are_not_equal(self):
        self.assertNotEqual(SemVerVersion("2025.12.3"), SemVerVersion("2025.12.4"))

    def test_versions_differing_in_minor_are_not_equal(self):
        self.assertNotEqual(SemVerVersion("2025.11.0"), SemVerVersion("2025.12.0"))

    def test_versions_differing_in_major_are_not_equal(self):
        self.assertNotEqual(SemVerVersion("2024.12.0"), SemVerVersion("2025.12.0"))


class SemVerVersionComparisonTest(TestBase):

    def test_lower_major_is_less_than_higher_major(self):
        self.assertLess(SemVerVersion("2024.1.0"), SemVerVersion("2025.1.0"))

    def test_lower_minor_is_less_than_higher_minor(self):
        self.assertLess(SemVerVersion("2025.11.0"), SemVerVersion("2025.12.0"))

    def test_lower_patch_is_less_than_higher_patch(self):
        self.assertLess(SemVerVersion("2025.12.2"), SemVerVersion("2025.12.3"))

    def test_higher_major_is_not_less_than_lower_major(self):
        self.assertFalse(SemVerVersion("2025.1.0") < SemVerVersion("2024.1.0"))

    def test_equal_versions_are_not_less_than_each_other(self):
        self.assertFalse(SemVerVersion("2025.12.3") < SemVerVersion("2025.12.3"))

    def test_major_takes_precedence_over_minor(self):
        self.assertLess(SemVerVersion("2024.99.99"), SemVerVersion("2025.0.0"))

    def test_minor_takes_precedence_over_patch(self):
        self.assertLess(SemVerVersion("2025.11.99"), SemVerVersion("2025.12.0"))

    def test_suffix_does_not_affect_less_than_comparison(self):
        # suffix is not considered in __lt__, only in __eq__
        self.assertFalse(SemVerVersion("2025.12.3b1") < SemVerVersion("2025.12.3"))
        self.assertFalse(SemVerVersion("2025.12.3") < SemVerVersion("2025.12.3b1"))

