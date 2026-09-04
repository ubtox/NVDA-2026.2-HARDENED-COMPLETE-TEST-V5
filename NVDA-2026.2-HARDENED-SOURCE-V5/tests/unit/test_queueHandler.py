# A part of NonVisual Desktop Access (NVDA)
# This file is covered by the GNU General Public License.
# See the file COPYING for more details.
# Copyright (C) 2026 NVDA Hardened contributors

"""Unit tests for queueHandler scheduling behaviour."""

import unittest
from unittest.mock import patch

import queueHandler


class TestEventQueuePriority(unittest.TestCase):
	@staticmethod
	def _drain(queue):
		while not queue.empty():
			queue.get_nowait()

	def setUp(self):
		self._drain(queueHandler.eventQueue)
		self._drain(queueHandler._immediateEventQueue)

	def tearDown(self):
		self._drain(queueHandler.eventQueue)
		self._drain(queueHandler._immediateEventQueue)

	def test_immediateWorkRunsBeforeNormalBacklog(self):
		calls = []
		with patch.object(queueHandler.core, "requestPump"):
			queueHandler.queueFunction(queueHandler.eventQueue, calls.append, "normal-1")
			queueHandler.queueFunction(queueHandler.eventQueue, calls.append, "normal-2")
			queueHandler.queueFunction(
				queueHandler.eventQueue,
				calls.append,
				"immediate",
				_immediate=True,
			)

		with patch.object(queueHandler.watchdog, "alive"):
			queueHandler.flushQueue(queueHandler.eventQueue)

		self.assertEqual(calls, ["immediate", "normal-1", "normal-2"])

	def test_immediateWorkKeepsHistoricalPumpHint(self):
		with patch.object(queueHandler.core, "requestPump") as requestPump:
			queueHandler.queueFunction(
				queueHandler.eventQueue,
				lambda: None,
				_immediate=True,
			)

		requestPump.assert_called_once_with(immediate=True)

	def test_isPendingItemsIncludesImmediateLane(self):
		with patch.object(queueHandler.core, "requestPump"):
			queueHandler.queueFunction(
				queueHandler.eventQueue,
				lambda: None,
				_immediate=True,
			)

		self.assertTrue(queueHandler.isPendingItems(queueHandler.eventQueue))
		self.assertTrue(queueHandler.eventQueue.empty())

	def test_normalWorkRemainsOnPublicEventQueue(self):
		with patch.object(queueHandler.core, "requestPump"):
			queueHandler.queueFunction(queueHandler.eventQueue, lambda: None)

		self.assertFalse(queueHandler.eventQueue.empty())
		self.assertTrue(queueHandler._immediateEventQueue.empty())
