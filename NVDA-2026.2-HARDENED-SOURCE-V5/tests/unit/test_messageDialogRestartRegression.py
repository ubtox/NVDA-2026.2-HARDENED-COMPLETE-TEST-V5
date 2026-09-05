# A part of NonVisual Desktop Access (NVDA)
# Copyright (C) 2026 NV Access Limited
# This file may be used under the terms of the GNU General Public License, version 2 or later, as modified by the NVDA license.
# For full terms and any additional permissions, see the NVDA license file: https://github.com/nvaccess/nvda/blob/master/copying.txt

import unittest
from unittest.mock import MagicMock, patch

import wx

from gui.message import displayDialogAsModal


@patch("gui.mainFrame")
class TestDisplayDialogAsModalRegression(unittest.TestCase):
	def test_dialogDeletedDuringShowModal(self, mockedMainFrame: MagicMock) -> None:
		"""The dialog must not be accessed after ShowModal returns."""
		dialog = MagicMock(spec_set=wx.Dialog)
		dialog.GetParent.side_effect = (None, RuntimeError("wrapped C/C++ object has been deleted"))
		dialog.ShowModal.return_value = wx.ID_YES

		self.assertEqual(wx.ID_YES, displayDialogAsModal(dialog))

		dialog.GetParent.assert_called_once()
		dialog.ShowModal.assert_called_once()
		mockedMainFrame.prePopup.assert_called_once()
		mockedMainFrame.postPopup.assert_called_once()
