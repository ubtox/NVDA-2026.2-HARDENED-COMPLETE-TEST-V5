from __future__ import annotations

from pathlib import Path
import re
from textwrap import dedent

ROOT = Path("NVDA-2026.2-HARDENED-SOURCE-V5")
UIA = ROOT / "source/NVDAObjects/UIA/__init__.py"
WEB = ROOT / "source/NVDAObjects/UIA/web.py"
CACHE_TESTS = ROOT / "tests/unit/test_NVDAObjects_UIA_cache.py"
UIA_HANDLER_TESTS = ROOT / "tests/unit/test_UIAHandler.py"


def replace_once(path: Path, old: str, new: str, label: str) -> None:
    text = path.read_text(encoding="utf-8")
    if new in text:
        return
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected one anchor, found {count}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8", newline="\n")


def regex_replace_once(path: Path, pattern: str, replacement: str, marker: str, label: str) -> None:
    text = path.read_text(encoding="utf-8")
    if marker in text:
        return
    text, count = re.subn(pattern, replacement, text, count=1, flags=re.S)
    if count != 1:
        raise SystemExit(f"{label}: expected one match, found {count}")
    path.write_text(text, encoding="utf-8", newline="\n")


replace_once(
    UIA,
    "\t\tUIAHandler.UIA_LevelPropertyId,\n\t\tUIAHandler.UIA_IsEnabledPropertyId,\n\t}\n\n\tdef _get__controlFieldUIACacheRequest(self):",
    "\t\tUIAHandler.UIA_LevelPropertyId,\n"
    "\t\tUIAHandler.UIA_IsEnabledPropertyId,\n"
    "\t\tUIAHandler.UIA.UIA_SelectionCanSelectMultiplePropertyId,\n"
    "\t\tUIAHandler.UIA_IsOffscreenPropertyId,\n"
    "\t\tUIAHandler.UIA_AnnotationTypesPropertyId,\n"
    "\t\tUIAHandler.UIA_DragIsGrabbedPropertyId,\n"
    "\t}\n\n\tdef _get__controlFieldUIACacheRequest(self):",
    "control field cache expansion",
)

replace_once(
    UIA,
    "\tdef event_gainFocus(self):\n"
    "\t\tUIAHandler.handler.addLocalEventHandlerGroupToElement(self.UIAElement, isFocus=True)\n"
    "\t\tsuper().event_gainFocus()",
    "\tdef event_gainFocus(self):\n"
    "\t\tUIAHandler.handler.addLocalEventHandlerGroupToElement(self.UIAElement, isFocus=True)\n"
    "\t\tself._prefetchUIACacheForPropertyIDs(self._focusPrefetchUIAPropertyIDs | self._UIAStatesPropertyIDs)\n"
    "\t\tsuper().event_gainFocus()",
    "fresh focus prefetch",
)

replace_once(
    UIA,
    "\t\tUIAHandler.UIA_DragIsGrabbedPropertyId,\n\t}\n\n\tdef _get_states(self):",
    "\t\tUIAHandler.UIA_DragIsGrabbedPropertyId,\n"
    "\t}\n\n"
    "\t_focusPrefetchUIAPropertyIDs = {\n"
    "\t\tUIAHandler.UIA_FullDescriptionPropertyId,\n"
    "\t\tUIAHandler.UIA_HelpTextPropertyId,\n"
    "\t\tUIAHandler.UIA_AccessKeyPropertyId,\n"
    "\t\tUIAHandler.UIA_AcceleratorKeyPropertyId,\n"
    "\t\tUIAHandler.UIA_PositionInSetPropertyId,\n"
    "\t\tUIAHandler.UIA_SizeOfSetPropertyId,\n"
    "\t\tUIAHandler.UIA_LevelPropertyId,\n"
    "\t\tUIAHandler.UIA.UIA_ValueValuePropertyId,\n"
    "\t\tUIAHandler.UIA.UIA_RangeValueValuePropertyId,\n"
    "\t\tUIAHandler.UIA_ToggleToggleStatePropertyId,\n"
    "\t\tUIAHandler.UIA_BoundingRectanglePropertyId,\n"
    "\t}\n"
    "\t\"\"\"Properties fetched together from a fresh UIA cache when focus is gained.\n"
    "\tThis intentionally does not reuse an event sender cache, which may be stale.\n"
    "\t\"\"\"\n\n"
    "\tdef _get_states(self):",
    "focus prefetch property set",
)

regex_replace_once(
    UIA,
    r"\tdef _prefetchUIACacheForPropertyIDs\(self, IDs\):\n.*?\n\t# C901 'findOverlayClasses' is too complex",
    """\tdef _prefetchUIACacheForPropertyIDs(self, IDs):
\t\t\"\"\"Fetch several UIA properties in one fresh cache request for this core cycle.

\t\tOnly properties accepted by the provider are registered as cached. A failed
\t\tBuildUpdatedCache call leaves the existing cache untouched.
\t\t\"\"\"
\t\telementCache = self._coreCycleUIAPropertyCacheElementCache
\t\tIDs = set(IDs)
\t\tif elementCache:
\t\t\tIDs.difference_update(elementCache)
\t\tif len(IDs) < 2:
\t\t\treturn

\t\tcacheRequest = UIAHandler.handler.clientObject.createCacheRequest()
\t\tacceptedIDs = set()
\t\tfor ID in IDs:
\t\t\ttry:
\t\t\t\tcacheRequest.addProperty(ID)
\t\t\texcept COMError:
\t\t\t\tlog.debug(
\t\t\t\t\t\"Couldn't add property ID %d to cache request, most likely unsupported on this version of Windows\"
\t\t\t\t\t% ID,
\t\t\t\t)
\t\t\telse:
\t\t\t\tacceptedIDs.add(ID)
\t\tif len(acceptedIDs) < 2:
\t\t\treturn

\t\ttry:
\t\t\tcacheElement = self.UIAElement.buildUpdatedCache(cacheRequest)
\t\texcept COMError:
\t\t\tlog.debugWarning(\"IUIAutomationElement.buildUpdatedCache failed given IDs of %s\" % acceptedIDs)
\t\t\treturn
\t\tfor ID in acceptedIDs:
\t\t\telementCache[ID] = cacheElement

\t# C901 'findOverlayClasses' is too complex""",
    "acceptedIDs = set()",
    "cache bookkeeping hardening",
)

replace_once(
    WEB,
    "\t_TextInfo = UIAWebTextInfo\n\n\tdef _isIframe(self):",
    "\t_TextInfo = UIAWebTextInfo\n\n"
    "\t_focusPrefetchUIAPropertyIDs = UIA._focusPrefetchUIAPropertyIDs | {\n"
    "\t\tUIAHandler.UIA_AriaPropertiesPropertyId,\n"
    "\t\tUIAHandler.UIA_AriaRolePropertyId,\n"
    "\t\tUIAHandler.UIA_LandmarkTypePropertyId,\n"
    "\t}\n\n"
    "\tdef _isIframe(self):",
    "web focus prefetch set",
)

replace_once(
    WEB,
    "\tdef _get_ariaProperties(self):\n\t\treturn splitUIAElementAttribs(self.UIAElement.currentAriaProperties)",
    "\tdef _get_ariaProperties(self):\n"
    "\t\treturn splitUIAElementAttribs(\n"
    "\t\t\tself._getUIACacheablePropertyValue(UIAHandler.UIA_AriaPropertiesPropertyId),\n"
    "\t\t)",
    "web aria core-cycle cache",
)

uia_text = UIA.read_text(encoding="utf-8")
selection_marker = "except COMError:\n\t\t\t# Some providers (e.g. Qt's QWindowsUiaSelectionItemProvider"
if selection_marker not in uia_text:
    replace_once(
        UIA,
        "\t\te = p.currentSelectionContainer\n\t\tif not e:",
        "\t\ttry:\n"
        "\t\t\te = p.currentSelectionContainer\n"
        "\t\texcept COMError:\n"
        "\t\t\t# Some providers (e.g. Qt's QWindowsUiaSelectionItemProvider when the\n"
        "\t\t\t# accessible has no actionInterface) raise instead of returning a value.\n"
        "\t\t\t# Treat the same as no selection container so focus speech is not aborted.\n"
        "\t\t\treturn None\n"
        "\t\tif not e:",
        "selection container COM failure handling",
    )

if not CACHE_TESTS.exists():
    CACHE_TESTS.write_text(
        dedent(
            '''\
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
            \tdef test_rejectedPropertyIsNotMarkedCached(self) -> None:
            \t\telementCache = {}
            \t\tcacheRequest = Mock()
            \t\tcacheElement = Mock()
            \t\thandler = Mock()
            \t\thandler.clientObject.createCacheRequest.return_value = cacheRequest
            \t\tuiObject = Mock()
            \t\tuiObject._coreCycleUIAPropertyCacheElementCache = elementCache
            \t\tuiObject.UIAElement.buildUpdatedCache.return_value = cacheElement

            \t\tdef addProperty(propertyID: int) -> None:
            \t\t\tif propertyID == 102:
            \t\t\t\traise COMError(-1, "failure", None)

            \t\tcacheRequest.addProperty.side_effect = addProperty
            \t\twith patch.object(UIAHandler, "handler", handler):
            \t\t\tUIA._prefetchUIACacheForPropertyIDs(uiObject, {101, 102, 103})

            \t\tself.assertEqual({101, 103}, set(elementCache))
            \t\tself.assertNotIn(102, elementCache)

            \tdef test_buildFailureLeavesCacheEmpty(self) -> None:
            \t\telementCache = {}
            \t\tcacheRequest = Mock()
            \t\thandler = Mock()
            \t\thandler.clientObject.createCacheRequest.return_value = cacheRequest
            \t\tuiObject = Mock()
            \t\tuiObject._coreCycleUIAPropertyCacheElementCache = elementCache
            \t\tuiObject.UIAElement.buildUpdatedCache.side_effect = COMError(-1, "failure", None)

            \t\twith patch.object(UIAHandler, "handler", handler):
            \t\t\tUIA._prefetchUIACacheForPropertyIDs(uiObject, {101, 103})

            \t\tself.assertEqual({}, elementCache)

            \tdef test_invalidatedCacheFallsBackToCurrentValue(self) -> None:
            \t\tcacheElement = Mock()
            \t\tcacheElement.getCachedPropertyValueEx.return_value = "cached"
            \t\telementCache = {123: cacheElement}
            \t\tuiObject = Mock()
            \t\tuiObject._coreCycleUIAPropertyCacheElementCache = elementCache
            \t\tuiObject.UIAElement.getCurrentPropertyValueEx.return_value = "current"

            \t\tself.assertEqual("cached", UIA._getUIACacheablePropertyValue(uiObject, 123))
            \t\telementCache.clear()
            \t\tself.assertEqual("current", UIA._getUIACacheablePropertyValue(uiObject, 123))
            \t\tuiObject.UIAElement.getCurrentPropertyValueEx.assert_called_once_with(123, False)

            \tdef test_controlFieldCacheContainsStateProperties(self) -> None:
            \t\texpected = {
            \t\t\tUIAHandler.UIA.UIA_SelectionCanSelectMultiplePropertyId,
            \t\t\tUIAHandler.UIA_IsOffscreenPropertyId,
            \t\t\tUIAHandler.UIA_AnnotationTypesPropertyId,
            \t\t\tUIAHandler.UIA_DragIsGrabbedPropertyId,
            \t\t}
            \t\tself.assertTrue(expected.issubset(UIATextInfo._controlFieldUIACachedPropertyIDs))

            \tdef test_focusPrefetchContainsSpeechCriticalProperties(self) -> None:
            \t\texpected = {
            \t\t\tUIAHandler.UIA_FullDescriptionPropertyId,
            \t\t\tUIAHandler.UIA_HelpTextPropertyId,
            \t\t\tUIAHandler.UIA_AccessKeyPropertyId,
            \t\t\tUIAHandler.UIA_AcceleratorKeyPropertyId,
            \t\t\tUIAHandler.UIA_PositionInSetPropertyId,
            \t\t\tUIAHandler.UIA_SizeOfSetPropertyId,
            \t\t\tUIAHandler.UIA_LevelPropertyId,
            \t\t\tUIAHandler.UIA_BoundingRectanglePropertyId,
            \t\t}
            \t\tself.assertTrue(expected.issubset(UIA._focusPrefetchUIAPropertyIDs))

            \tdef test_webFocusPrefetchContainsAriaProperties(self) -> None:
            \t\texpected = {
            \t\t\tUIAHandler.UIA_AriaPropertiesPropertyId,
            \t\t\tUIAHandler.UIA_AriaRolePropertyId,
            \t\t\tUIAHandler.UIA_LandmarkTypePropertyId,
            \t\t}
            \t\tself.assertTrue(expected.issubset(UIAWeb._focusPrefetchUIAPropertyIDs))

            \tdef test_webAriaPropertiesUsesCoreCycleCache(self) -> None:
            \t\tobj = object.__new__(UIAWeb)
            \t\twith patch.object(UIAWeb, "_getUIACacheablePropertyValue", return_value="role=button;") as getter:
            \t\t\tself.assertEqual({"role": "button"}, obj._get_ariaProperties())
            \t\tgetter.assert_called_once_with(UIAHandler.UIA_AriaPropertiesPropertyId)
            '''
        ),
        encoding="utf-8",
        newline="\n",
    )

handler_tests = UIA_HANDLER_TESTS.read_text(encoding="utf-8")
if "class TestUIASelectionContainer(TestCase):" not in handler_tests:
    anchor = "\n\nclass TestUIATextAttributeNormalization(TestCase):"
    insertion = dedent(
        '''

        class TestUIASelectionContainer(TestCase):
        \tdef test_COMErrorIsTreatedAsNoSelectionContainer(self):
        \t\tclass FailingSelectionItemPattern:
        \t\t\t@property
        \t\t\tdef currentSelectionContainer(self):
        \t\t\t\traise COMError(-1, "failure", None)

        \t\tuiObject = Mock()
        \t\tuiObject.UIASelectionItemPattern = FailingSelectionItemPattern()

        \t\tself.assertIsNone(UIA._get_selectionContainer(uiObject))
        '''
    )
    if anchor not in handler_tests:
        raise SystemExit("selection container test anchor not found")
    UIA_HANDLER_TESTS.write_text(handler_tests.replace(anchor, insertion + anchor, 1), encoding="utf-8", newline="\n")

print("UIA finalization patch applied")
