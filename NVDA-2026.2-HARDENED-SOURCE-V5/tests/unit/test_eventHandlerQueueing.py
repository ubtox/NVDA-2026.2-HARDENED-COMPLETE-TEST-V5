# A part of NonVisual Desktop Access (NVDA)
# Copyright (C) 2026 NVDA Evolution contributors
# This file is covered by the GNU General Public License.
# See the file COPYING for more details.

import unittest
from unittest.mock import patch

import eventHandler


class TestEventQueueCoalescing(unittest.TestCase):
	def setUp(self) -> None:
		self.obj = object()
		self._previousLastQueuedFocusObject = eventHandler.lastQueuedFocusObject
		with eventHandler._pendingEventCountsLock:
			eventHandler._pendingEventCountsByName.clear()
			eventHandler._pendingEventCountsByObj.clear()
			eventHandler._pendingEventCountsByNameAndObj.clear()

	def tearDown(self) -> None:
		eventHandler.lastQueuedFocusObject = self._previousLastQueuedFocusObject
		with eventHandler._pendingEventCountsLock:
			eventHandler._pendingEventCountsByName.clear()
			eventHandler._pendingEventCountsByObj.clear()
			eventHandler._pendingEventCountsByNameAndObj.clear()

	def _pendingCount(self, eventName: str, obj: object) -> int:
		return eventHandler._pendingEventCountsByNameAndObj.get((eventName, obj), 0)

	def test_locationChange_duplicate_without_payload_is_coalesced(self) -> None:
		with patch.object(eventHandler.queueHandler, "queueFunction") as queueFunction:
			eventHandler.queueEvent("locationChange", self.obj)
			eventHandler.queueEvent("locationChange", self.obj)

		self.assertEqual(queueFunction.call_count, 1)
		self.assertEqual(self._pendingCount("locationChange", self.obj), 1)

	def test_visibleDataChange_duplicate_without_payload_is_coalesced(self) -> None:
		with patch.object(eventHandler.queueHandler, "queueFunction") as queueFunction:
			eventHandler.queueEvent("visibleDataChange", self.obj)
			eventHandler.queueEvent("visibleDataChange", self.obj)

		self.assertEqual(queueFunction.call_count, 1)
		self.assertEqual(self._pendingCount("visibleDataChange", self.obj), 1)

	def test_payload_carrying_event_is_never_coalesced(self) -> None:
		with patch.object(eventHandler.queueHandler, "queueFunction") as queueFunction:
			eventHandler.queueEvent("locationChange", self.obj, revision=1)
			eventHandler.queueEvent("locationChange", self.obj, revision=2)

		self.assertEqual(queueFunction.call_count, 2)
		self.assertEqual(self._pendingCount("locationChange", self.obj), 2)

	def test_non_coalescible_event_remains_fifo(self) -> None:
		with patch.object(eventHandler.queueHandler, "queueFunction") as queueFunction:
			eventHandler.queueEvent("caret", self.obj)
			eventHandler.queueEvent("caret", self.obj)

		self.assertEqual(queueFunction.call_count, 2)
		self.assertEqual(self._pendingCount("caret", self.obj), 2)

	def test_same_event_for_different_objects_is_not_coalesced(self) -> None:
		otherObj = object()
		with patch.object(eventHandler.queueHandler, "queueFunction") as queueFunction:
			eventHandler.queueEvent("visibleDataChange", self.obj)
			eventHandler.queueEvent("visibleDataChange", otherObj)

		self.assertEqual(queueFunction.call_count, 2)
		self.assertEqual(self._pendingCount("visibleDataChange", self.obj), 1)
		self.assertEqual(self._pendingCount("visibleDataChange", otherObj), 1)

	def test_event_can_be_queued_again_after_pending_callback_runs(self) -> None:
		with (
			patch.object(eventHandler.queueHandler, "queueFunction") as queueFunction,
			patch.object(eventHandler, "executeEvent"),
		):
			eventHandler.queueEvent("locationChange", self.obj)
			eventHandler._queueEventCallback("locationChange", self.obj, {})
			self.assertFalse(eventHandler.isPendingEvents("locationChange", self.obj))
			eventHandler.queueEvent("locationChange", self.obj)

		self.assertEqual(queueFunction.call_count, 2)
		self.assertEqual(self._pendingCount("locationChange", self.obj), 1)

	def test_large_duplicate_state_burst_collapses_to_single_pending_event(self) -> None:
		with patch.object(eventHandler.queueHandler, "queueFunction") as queueFunction:
			for _ in range(1000):
				eventHandler.queueEvent("visibleDataChange", self.obj)

		self.assertEqual(queueFunction.call_count, 1)
		self.assertEqual(self._pendingCount("visibleDataChange", self.obj), 1)

	def test_focus_is_preserved_and_prioritized_during_state_event_storm(self) -> None:
		with (
			patch.object(eventHandler.queueHandler, "queueFunction") as queueFunction,
			patch.object(eventHandler, "objectBelowLockScreenAndWindowsIsLocked", return_value=False),
		):
			for _ in range(1000):
				eventHandler.queueEvent("locationChange", self.obj)
			eventHandler.queueEvent("gainFocus", self.obj)

		self.assertEqual(queueFunction.call_count, 2)
		self.assertEqual(self._pendingCount("locationChange", self.obj), 1)
		self.assertEqual(self._pendingCount("gainFocus", self.obj), 1)
		self.assertIs(eventHandler.lastQueuedFocusObject, self.obj)
		focusCall = queueFunction.call_args_list[-1]
		self.assertEqual(focusCall.args[2], "gainFocus")
		self.assertTrue(focusCall.kwargs["_immediate"])
