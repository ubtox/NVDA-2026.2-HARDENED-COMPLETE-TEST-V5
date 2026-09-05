# A part of NonVisual Desktop Access (NVDA)
# This file is covered by the GNU General Public License.
# See the file COPYING for more details.
# Copyright (C) 2026 NV Access Limited

"""Regression tests for NextGen rectangle helpers."""

import unittest

from locationHelper import RectLTRB, RectLTWH


class TestNextGenRectangleHelpers(unittest.TestCase):
	def test_union_preserves_receiver_representation(self):
		self.assertEqual(
			RectLTRB(left=2, top=2, right=4, bottom=4).union(
				RectLTWH(left=3, top=3, width=5, height=5),
			),
			RectLTRB(left=2, top=2, right=8, bottom=8),
		)
		self.assertEqual(
			RectLTWH(left=2, top=2, width=2, height=2).union(
				RectLTRB(left=5, top=5, right=7, bottom=7),
			),
			RectLTWH(left=2, top=2, width=5, height=5),
		)

	def test_toLTRB_is_idempotent(self):
		rectLTRB = RectLTRB(left=10, top=10, right=30, bottom=30)
		rectLTWH = RectLTWH(left=10, top=10, width=20, height=20)
		self.assertIs(rectLTRB.toLTRB(), rectLTRB)
		self.assertEqual(rectLTWH.toLTRB(), rectLTRB)

	def test_toLTWH_is_idempotent(self):
		rectLTRB = RectLTRB(left=10, top=10, right=30, bottom=30)
		rectLTWH = RectLTWH(left=10, top=10, width=20, height=20)
		self.assertIs(rectLTWH.toLTWH(), rectLTWH)
		self.assertEqual(rectLTRB.toLTWH(), rectLTWH)

	def test_union_rejects_unsupported_type(self):
		with self.assertRaises(TypeError):
			RectLTRB(left=0, top=0, right=1, bottom=1).union(object())
