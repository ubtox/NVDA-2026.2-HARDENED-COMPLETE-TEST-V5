# A part of NonVisual Desktop Access (NVDA)
# Copyright (C) 2026 NVDA Evolution contributors
# This file is covered by the GNU General Public License.
# See the file COPYING for more details.

from unittest import TestCase
from unittest.mock import Mock

from comtypes import COMError

from NVDAObjects.UIA import UIA


class _FailingSelectionItemPattern:
	@property
	def currentSelectionContainer(self) -> object:
		raise COMError(-2147220991, "provider failure", None)


class TestUIASelectionContainerProviderFailure(TestCase):
	def test_COMErrorIsTreatedAsMissingSelectionContainer(self) -> None:
		uiObject = Mock()
		uiObject.UIASelectionItemPattern = _FailingSelectionItemPattern()

		self.assertIsNone(UIA._get_selectionContainer(uiObject))
