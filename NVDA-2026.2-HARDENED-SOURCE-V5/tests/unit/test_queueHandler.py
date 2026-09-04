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

	@staticmethod
	def _putRaw(queue, func, *args):
		queue.put_nowait((func, args, {}))

	@staticmethod
	def _putTimedRaw(queue, queuedAt, func, *args):
		queue.put_nowait((func, args, {}, queuedAt))

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

	def test_eventQueueItemsCarryLatencyTimestamp(self):
		with (
			patch.object(queueHandler.core, "requestPump"),
			patch.object(queueHandler, "perf_counter", return_value=12.5),
		):
			queueHandler.queueFunction(queueHandler.eventQueue, lambda: None)

		item = queueHandler.eventQueue.get_nowait()
		self.assertEqual(len(item), 4)
		self.assertEqual(item[3], 12.5)

	def test_pumpAllLimitsNormalWorkPerCycle(self):
		calls = []
		limit = queueHandler._MAX_NORMAL_EVENT_ITEMS_PER_PUMP
		for index in range(limit + 5):
			self._putRaw(queueHandler.eventQueue, calls.append, index)

		with (
			patch.object(queueHandler, "generators", {}),
			patch.object(queueHandler.core, "requestPump") as requestPump,
			patch.object(queueHandler.watchdog, "alive"),
		):
			queueHandler.pumpAll()

		self.assertEqual(len(calls), limit)
		self.assertEqual(calls, list(range(limit)))
		self.assertTrue(queueHandler.isPendingItems(queueHandler.eventQueue))
		requestPump.assert_called_once_with()

	def test_pumpAllDrainsImmediateLaneBeforeFairNormalSlice(self):
		calls = []
		limit = queueHandler._MAX_NORMAL_EVENT_ITEMS_PER_PUMP
		for index in range(limit + 1):
			self._putRaw(queueHandler.eventQueue, calls.append, f"normal-{index}")
		self._putRaw(queueHandler._immediateEventQueue, calls.append, "immediate-1")
		self._putRaw(queueHandler._immediateEventQueue, calls.append, "immediate-2")

		with (
			patch.object(queueHandler, "generators", {}),
			patch.object(queueHandler.core, "requestPump"),
			patch.object(queueHandler.watchdog, "alive"),
		):
			queueHandler.pumpAll()

		self.assertEqual(calls[:2], ["immediate-1", "immediate-2"])
		self.assertEqual(len(calls), limit + 2)
		self.assertTrue(queueHandler.isPendingItems(queueHandler.eventQueue))

	def test_pumpDiagnosticsMeasureBacklogWorkAndLatency(self):
		calls = []
		self._putTimedRaw(queueHandler._immediateEventQueue, 9.5, calls.append, "immediate")
		self._putTimedRaw(queueHandler.eventQueue, 9.0, calls.append, "normal")

		with (
			patch.object(queueHandler, "generators", {}),
			patch.object(queueHandler.core, "requestPump"),
			patch.object(queueHandler.watchdog, "alive"),
			patch.object(queueHandler.log, "debug") as debug,
			patch.object(queueHandler, "perf_counter", side_effect=[10.0, 10.1, 10.2, 10.3]),
		):
			queueHandler.pumpAll()

		diagnostics = queueHandler._getEventQueueDiagnostics()
		self.assertEqual(calls, ["immediate", "normal"])
		self.assertEqual(diagnostics.immediatePendingBefore, 1)
		self.assertEqual(diagnostics.normalPendingBefore, 1)
		self.assertEqual(diagnostics.immediateProcessed, 1)
		self.assertEqual(diagnostics.normalProcessed, 1)
		self.assertAlmostEqual(diagnostics.maxWaitMs, 1200.0)
		self.assertAlmostEqual(diagnostics.pumpDurationMs, 300.0)
		self.assertEqual(diagnostics.normalPendingAfter, 0)
		debug.assert_called_once()

	def test_largeNormalBacklogDrainsAcrossFairSlicesWithoutLoss(self):
		calls = []
		limit = queueHandler._MAX_NORMAL_EVENT_ITEMS_PER_PUMP
		total = (limit * 16) + 7
		for index in range(total):
			self._putRaw(queueHandler.eventQueue, calls.append, index)

		cycles = 0
		with (
			patch.object(queueHandler, "generators", {}),
			patch.object(queueHandler.core, "requestPump"),
			patch.object(queueHandler.watchdog, "alive"),
			patch.object(queueHandler.log, "debug"),
		):
			while queueHandler.isPendingItems(queueHandler.eventQueue):
				queueHandler.pumpAll()
				cycles += 1

		self.assertEqual(calls, list(range(total)))
		self.assertEqual(cycles, 17)
		self.assertFalse(queueHandler.isPendingItems(queueHandler.eventQueue))

	def test_directFlushQueueKeepsFullSnapshotBehaviour(self):
		calls = []
		limit = queueHandler._MAX_NORMAL_EVENT_ITEMS_PER_PUMP
		for index in range(limit + 5):
			self._putRaw(queueHandler.eventQueue, calls.append, index)

		with patch.object(queueHandler.watchdog, "alive"):
			queueHandler.flushQueue(queueHandler.eventQueue)

		self.assertEqual(calls, list(range(limit + 5)))
		self.assertFalse(queueHandler.isPendingItems(queueHandler.eventQueue))
