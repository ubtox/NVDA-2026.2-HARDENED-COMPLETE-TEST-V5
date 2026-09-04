# A part of NonVisual Desktop Access (NVDA)
# This file is covered by the GNU General Public License.
# See the file COPYING for more details.
# Copyright (C) 2026 NV Access Limited, NVDA Evolution contributors

import unittest
from unittest.mock import Mock, patch

from NVDAObjects.UIA import UIA


class TestUIAFocusEvent(unittest.TestCase):
	def test_shouldAllowUIAFocusEventIgnoresStaleCache(self):
		obj = object.__new__(UIA)
		obj.UIAElement = Mock(currentHasKeyboardFocus=False)

		with patch.object(UIA, "_getUIACacheablePropertyValue", return_value=True) as getCachedValue:
			self.assertFalse(obj._get_shouldAllowUIAFocusEvent())
			getCachedValue.assert_not_called()
