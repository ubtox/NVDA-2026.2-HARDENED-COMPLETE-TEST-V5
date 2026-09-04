# A part of NonVisual Desktop Access (NVDA)
# Copyright (C) 2026 NV Access Limited, Leonard de Ruijter, Tobias Heath
# This file may be used under the terms of the GNU General Public License, version 2 or later, as modified by the NVDA license.
# For full terms and any additional permissions, see the NVDA license file:
# https://github.com/nvaccess/nvda/blob/master/copying.txt

from unittest import TestCase
from unittest.mock import Mock

from comtypes import COMError

import textInfos
import UIAHandler
from NVDAObjects.UIA import UIA, UIATextInfo
from UIAHandler import NVDAUnitsToUIAUnits, getUIAUnitFromNVDAUnit, utils


class Test_getUIAUnitFromNVDAUnit(TestCase):
	def test_mappedUnitReturnsUIAUnit(self):
		self.assertEqual(
			getUIAUnitFromNVDAUnit(textInfos.UNIT_WORD),
			NVDAUnitsToUIAUnits[textInfos.UNIT_WORD],
		)

	def test_unmappedUnitRaisesNotImplementedError(self):
		with self.assertRaises(NotImplementedError):
			getUIAUnitFromNVDAUnit(textInfos.UNIT_SENTENCE)


class TestNormalizeUIAText(TestCase):
	def test_plainTextReturnedUnchanged(self):
		text = "NVDA WinUI 3"
		self.assertIs(utils.normalizeUIAText(text), text)

	def test_validSurrogatePairBecomesUnicodeScalar(self):
		self.assertEqual(utils.normalizeUIAText("\ud83d\ude00"), "😀")

	def test_isolatedHighSurrogateIsReplaced(self):
		self.assertEqual(utils.normalizeUIAText("A\ud83dB"), "A\ufffdB")

	def test_isolatedLowSurrogateIsReplaced(self):
		self.assertEqual(utils.normalizeUIAText("A\ude00B"), "A\ufffdB")


class TestUIATextInfoNormalization(TestCase):
	def test_textRetrievalNormalizesMalformedProviderText(self):
		textInfo = object.__new__(UIATextInfo)
		textRange = Mock()
		textRange.getText.return_value = "A\ud83dB"

		self.assertEqual(textInfo._getTextFromUIARange(textRange), "A\ufffdB")
		textRange.getText.assert_called_once_with(-1)


class TestUIAPropertyValueNormalization(TestCase):
	def test_currentStringPropertyIsNormalized(self):
		uiObject = Mock()
		uiObject._coreCycleUIAPropertyCacheElementCache = {}
		uiObject.UIAElement = Mock()
		uiObject.UIAElement.getCurrentPropertyValueEx.return_value = "A\ud83dB"

		self.assertEqual(UIA._getUIACacheablePropertyValue(uiObject, 123), "A\ufffdB")
		uiObject.UIAElement.getCurrentPropertyValueEx.assert_called_once_with(123, False)

	def test_cachedStringPropertyIsNormalized(self):
		cacheElement = Mock()
		cacheElement.getCachedPropertyValueEx.return_value = "\ud83d\ude00"
		uiObject = Mock()
		uiObject._coreCycleUIAPropertyCacheElementCache = {123: cacheElement}
		uiObject.UIAElement = Mock()

		self.assertEqual(UIA._getUIACacheablePropertyValue(uiObject, 123), "😀")
		cacheElement.getCachedPropertyValueEx.assert_called_once_with(123, False)
		uiObject.UIAElement.getCurrentPropertyValueEx.assert_not_called()

	def test_nonStringPropertyIsReturnedUnchanged(self):
		value = object()
		uiObject = Mock()
		uiObject._coreCycleUIAPropertyCacheElementCache = {}
		uiObject.UIAElement = Mock()
		uiObject.UIAElement.getCurrentPropertyValueEx.return_value = value

		self.assertIs(UIA._getUIACacheablePropertyValue(uiObject, 123), value)


class TestUIATextAttributeNormalization(TestCase):
	def test_directAttributeStringIsNormalized(self):
		textRange = Mock()
		textRange.GetAttributeValue.return_value = "A\ude00B"

		self.assertEqual(
			utils.getUIATextAttributeValueFromRange(textRange, 123),
			"A\ufffdB",
		)

	def test_attributeFetcherStringIsNormalized(self):
		textRange = Mock()
		textRange.getAttributeValue.return_value = "A\ud83dB"
		fetcher = utils.UIATextRangeAttributeValueFetcher(textRange)

		self.assertEqual(fetcher.getValue(123), "A\ufffdB")

	def test_bulkAttributeFetcherStringIsNormalized(self):
		fetcher = object.__new__(utils.BulkUIATextRangeAttributeValueFetcher)
		fetcher.IDsToValues = {123: "\ud83d\ude00"}

		self.assertEqual(fetcher.getValue(123), "😀")


class TestUIAProviderTextBoundaryRegressions(TestCase):
	def test_remoteHeadingLabelNormalization(self):
		import UIAHandler.remote as remote

		self.assertEqual(remote._normalizeProviderText("A\ud83dB"), "A\ufffdB")

	def test_visualStudioLineNumberUsesNormalizedRetrieval(self):
		from appModules.devenv import VsWpfTextViewTextInfo

		textInfo = object.__new__(VsWpfTextViewTextInfo)
		textRange = Mock()
		lineNumberRange = Mock()
		textRange.Clone.return_value = lineNumberRange
		lineNumberRange.getText.return_value = "12\ud83d"

		self.assertEqual(textInfo._getLineNumberString(textRange), "12\ufffd")
		lineNumberRange.getText.assert_called_once_with(-1)

	def test_consoleOffsetUsesNormalizedRetrieval(self):
		from NVDAObjects.UIA.winConsoleUIA import ConsoleUIATextInfoWorkaroundEndInclusive

		textInfo = object.__new__(ConsoleUIATextInfoWorkaroundEndInclusive)
		lineInfo = Mock()
		charInfo = Mock()
		lineInfo.copy.return_value = charInfo
		charInfo._rangeObj = Mock()
		charInfo._getTextFromUIARange.return_value = "A\ufffd"

		self.assertEqual(textInfo._getCurrentOffsetInThisLine(lineInfo), 2)
		charInfo._getTextFromUIARange.assert_called_once_with(charInfo._rangeObj)


class TestUIATextRangeFromElement(TestCase):
	def test_standardRangeFromChildHasPriority(self):
		textPattern = Mock()
		standardRange = Mock()
		textPattern.rangeFromChild.return_value = standardRange
		element = Mock()

		self.assertIs(utils.UIATextRangeFromElement(textPattern, element), standardRange)
		element.GetCurrentPattern.assert_not_called()

	def test_textChildPatternFallbackAfterCOMError(self):
		textPattern = Mock()
		textPattern.rangeFromChild.side_effect = COMError(-1, "failure", None)
		documentRange = Mock()
		textPattern.documentRange = documentRange
		element = Mock()
		textChildRange = Mock()
		textChildPattern = Mock(TextRange=textChildRange)
		punk = Mock()
		punk.QueryInterface.return_value = textChildPattern
		element.GetCurrentPattern.return_value = punk

		self.assertIs(utils.UIATextRangeFromElement(textPattern, element), textChildRange)
		element.GetCurrentPattern.assert_called_once_with(UIAHandler.UIA_TextChildPatternId)
		textChildRange.CompareEndpoints.assert_called_once_with(
			UIAHandler.TextPatternRangeEndpoint_Start,
			documentRange,
			UIAHandler.TextPatternRangeEndpoint_Start,
		)

	def test_textChildPatternFallbackAfterNullRange(self):
		textPattern = Mock()
		textPattern.rangeFromChild.return_value = None
		textPattern.documentRange = Mock()
		element = Mock()
		textChildRange = Mock()
		textChildPattern = Mock(TextRange=textChildRange)
		punk = Mock()
		punk.QueryInterface.return_value = textChildPattern
		element.GetCurrentPattern.return_value = punk

		self.assertIs(utils.UIATextRangeFromElement(textPattern, element), textChildRange)

	def test_textChildPatternFallbackRejectsRangeFromDifferentTextProvider(self):
		textPattern = Mock()
		textPattern.rangeFromChild.return_value = None
		textPattern.documentRange = Mock()
		element = Mock()
		textChildRange = Mock()
		textChildRange.CompareEndpoints.side_effect = COMError(-1, "different provider", None)
		textChildPattern = Mock(TextRange=textChildRange)
		punk = Mock()
		punk.QueryInterface.return_value = textChildPattern
		element.GetCurrentPattern.return_value = punk

		self.assertIsNone(utils.UIATextRangeFromElement(textPattern, element))
