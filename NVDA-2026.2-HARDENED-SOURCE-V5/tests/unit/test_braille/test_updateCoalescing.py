# A part of NonVisual Desktop Access (NVDA)
# This file is covered by the GNU General Public License.
# See the file COPYING for more details.
# Copyright (C) 2026 NVDA Evolution contributors

"""Regression tests for braille region update coalescing."""

import unittest
from unittest.mock import Mock, patch

import braille


class TestPendingRegionUpdateCoalescing(unittest.TestCase):
	@staticmethod
	def _makeHandler() -> braille.BrailleHandler:
		handler = object.__new__(braille.BrailleHandler)
		handler._regionsPendingUpdate = set()
		handler.mainBuffer = Mock()
		handler.messageBuffer = Mock()
		handler.buffer = handler.mainBuffer
		return handler

	def test_duplicatePendingRegionIsUpdatedOncePerPump(self) -> None:
		handler = self._makeHandler()
		region = Mock()
		region.obj = object()

		for _ in range(1000):
			handler._regionsPendingUpdate.add(region)

		with patch.object(braille.BrailleHandler, "update") as displayUpdate:
			handler._handlePendingUpdate()

		region.update.assert_called_once_with()
		handler.mainBuffer.saveWindow.assert_called_once_with()
		handler.mainBuffer.update.assert_called_once_with()
		handler.mainBuffer.restoreWindow.assert_called_once_with()
		displayUpdate.assert_called_once_with()
		self.assertFalse(handler._regionsPendingUpdate)

	def test_distinctPendingRegionsShareOneBufferAndDisplayRefresh(self) -> None:
		handler = self._makeHandler()
		regions = [Mock(), Mock(), Mock()]
		for region in regions:
			region.obj = object()
			handler._regionsPendingUpdate.add(region)

		with patch.object(braille.BrailleHandler, "update") as displayUpdate:
			handler._handlePendingUpdate()

		for region in regions:
			region.update.assert_called_once_with()
		handler.mainBuffer.update.assert_called_once_with()
		displayUpdate.assert_called_once_with()
		self.assertFalse(handler._regionsPendingUpdate)
