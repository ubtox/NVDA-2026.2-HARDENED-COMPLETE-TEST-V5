# A part of NonVisual Desktop Access (NVDA)
# This file is covered by the GNU General Public License.
# See the file COPYING for more details.
# Copyright (C) 2026 NVDA Evolution contributors

import unittest
from unittest.mock import patch

import config
from config.configFlags import TypingEcho
import speech.speech as speech


class TestLazyProtectedTypingState(unittest.TestCase):
	def setUp(self) -> None:
		self._oldCharacterEcho = config.conf["keyboard"]["speakTypedCharacters"]
		self._oldWordEcho = config.conf["keyboard"]["speakTypedWords"]
		speech.initialize()
		speech.clearTypedWordBuffer()

	def tearDown(self) -> None:
		config.conf["keyboard"]["speakTypedCharacters"] = self._oldCharacterEcho
		config.conf["keyboard"]["speakTypedWords"] = self._oldWordEcho
		speech.clearTypedWordBuffer()

	def test_disabledEchoDoesNotQueryProtectedState(self) -> None:
		config.conf["keyboard"]["speakTypedCharacters"] = TypingEcho.OFF.value
		config.conf["keyboard"]["speakTypedWords"] = TypingEcho.OFF.value

		with patch.object(speech.api, "isTypingProtected") as isTypingProtected:
			speech.speakTypedCharacters("a")

		isTypingProtected.assert_not_called()
		self.assertEqual([], speech._curWordChars)

	def test_controlCharacterDoesNotQueryProtectedStateWhenWordEchoIsOff(self) -> None:
		config.conf["keyboard"]["speakTypedCharacters"] = TypingEcho.ALWAYS.value
		config.conf["keyboard"]["speakTypedWords"] = TypingEcho.OFF.value

		with patch.object(speech.api, "isTypingProtected") as isTypingProtected:
			speech.speakTypedCharacters("\r")

		isTypingProtected.assert_not_called()

	def test_protectedWordBufferNeverStoresClearText(self) -> None:
		config.conf["keyboard"]["speakTypedCharacters"] = TypingEcho.OFF.value
		config.conf["keyboard"]["speakTypedWords"] = TypingEcho.ALWAYS.value

		with patch.object(speech.api, "isTypingProtected", return_value=True) as isTypingProtected:
			speech.speakTypedCharacters("a")

		isTypingProtected.assert_called_once_with()
		self.assertEqual([speech.PROTECTED_CHAR], speech._curWordChars)

	def test_protectedCharacterEchoIsMasked(self) -> None:
		config.conf["keyboard"]["speakTypedCharacters"] = TypingEcho.ALWAYS.value
		config.conf["keyboard"]["speakTypedWords"] = TypingEcho.OFF.value

		with (
			patch.object(speech.api, "isTypingProtected", return_value=True) as isTypingProtected,
			patch.object(speech, "speakSpelling") as speakSpelling,
		):
			speech.speakTypedCharacters("a")

		isTypingProtected.assert_called_once_with()
		speakSpelling.assert_called_once_with(speech.PROTECTED_CHAR)
