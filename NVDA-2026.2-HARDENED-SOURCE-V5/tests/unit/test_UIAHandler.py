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
