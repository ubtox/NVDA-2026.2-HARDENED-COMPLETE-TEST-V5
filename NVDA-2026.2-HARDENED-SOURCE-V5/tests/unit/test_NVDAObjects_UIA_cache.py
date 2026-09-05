# A part of NonVisual Desktop Access (NVDA)
# This file is covered by the GNU General Public License.
# See the file COPYING for more details.
# Copyright (C) 2026 NVDA Evolution contributors

import unittest
from unittest.mock import Mock, patch

from comtypes import COMError

import UIAHandler
from NVDAObjects.UIA import UIA, UIATextInfo
from NVDAObjects.UIA.web import UIAWeb


class TestUIACacheBatching(unittest.TestCase):
	def test_rejectedPropertyIsNotMarkedCached(self) -> None:
		elementCache = {}
		cacheRequest = Mock()
		cacheElement = Mock()
		handler = Mock()
		handler.clientObject.createCacheRequest.return_value = cacheRequest
		uiObject = Mock()
		uiObject._coreCycleUIAPropertyCacheElementCache = elementCache
		uiObject.UIAElement.buildUpdatedCache.return_value = cacheElement

		def addProperty(propertyID: int) -> None:
			if propertyID == 102:
				raise COMError(-1, "failure", None)

		cacheRequest.addProperty.side_effect = addProperty
		with patch.object(UIAHandler, "handler", handler):
			UIA._prefetchUIACacheForPropertyIDs(uiObject, {101, 102, 103})

		self.assertEqual({101, 103}, set(elementCache))
		self.assertNotIn(102, elementCache)

	def test_buildFailureLeavesCacheEmpty(self) -> None:
		elementCache = {}
		cacheRequest = Mock()
		handler = Mock()
		handler.clientObject.createCacheRequest.return_value = cacheRequest
		uiObject = Mock()
		uiObject._coreCycleUIAPropertyCacheElementCache = elementCache
		uiObject.UIAElement.buildUpdatedCache.side_effect = COMError(-1, "failure", None)

		with patch.object(UIAHandler, "handler", handler):
			UIA._prefetchUIACacheForPropertyIDs(uiObject, {101, 103})

		self.assertEqual({}, elementCache)

	def test_invalidatedCacheFallsBackToCurrentValue(self) -> None:
		cacheElement = Mock()
		cacheElement.getCachedPropertyValueEx.return_value = "cached"
		elementCache = {123: cacheElement}
		uiObject = Mock()
		uiObject._coreCycleUIAPropertyCacheElementCache = elementCache
		uiObject.UIAElement.getCurrentPropertyValueEx.return_value = "current"

		self.assertEqual("cached", UIA._getUIACacheablePropertyValue(uiObject, 123))
		elementCache.clear()
		self.assertEqual("current", UIA._getUIACacheablePropertyValue(uiObject, 123))
		uiObject.UIAElement.getCurrentPropertyValueEx.assert_called_once_with(123, False)

	def test_controlFieldCacheContainsStateProperties(self) -> None:
		expected = {
			UIAHandler.UIA.UIA_SelectionCanSelectMultiplePropertyId,
			UIAHandler.UIA_IsOffscreenPropertyId,
			UIAHandler.UIA_AnnotationTypesPropertyId,
			UIAHandler.UIA_DragIsGrabbedPropertyId,
		}
		self.assertTrue(expected.issubset(UIATextInfo._controlFieldUIACachedPropertyIDs))

	def test_focusPrefetchContainsSpeechCriticalProperties(self) -> None:
		expected = {
			UIAHandler.UIA_FullDescriptionPropertyId,
			UIAHandler.UIA_HelpTextPropertyId,
			UIAHandler.UIA_AccessKeyPropertyId,
			UIAHandler.UIA_AcceleratorKeyPropertyId,
			UIAHandler.UIA_PositionInSetPropertyId,
			UIAHandler.UIA_SizeOfSetPropertyId,
			UIAHandler.UIA_LevelPropertyId,
			UIAHandler.UIA_BoundingRectanglePropertyId,
		}
		self.assertTrue(expected.issubset(UIA._focusPrefetchUIAPropertyIDs))

	def test_webFocusPrefetchContainsAriaProperties(self) -> None:
		expected = {
			UIAHandler.UIA_AriaPropertiesPropertyId,
			UIAHandler.UIA_AriaRolePropertyId,
			UIAHandler.UIA_LandmarkTypePropertyId,
		}
		self.assertTrue(expected.issubset(UIAWeb._focusPrefetchUIAPropertyIDs))

	def test_webAriaPropertiesUsesCoreCycleCache(self) -> None:
		obj = object.__new__(UIAWeb)
		with patch.object(UIAWeb, "_getUIACacheablePropertyValue", return_value="role=button;") as getter:
			self.assertEqual({"role": "button"}, obj._get_ariaProperties())
		getter.assert_called_once_with(UIAHandler.UIA_AriaPropertiesPropertyId)
