# queueHandler.py
# A part of NonVisual Desktop Access (NVDA)
# Copyright (C) 2006-2026 NV Access Limited
# This file is covered by the GNU General Public License.
# See the file COPYING for more details.

import types
from queue import SimpleQueue
from logHandler import log
import watchdog
import core

# A queue for calls that should be made on NVDA's main thread.
# #11369: We use SimpleQueue rather than Queue here
# as SimpleQueue is very light-weight, does not use locks
# and ensures that garbage collection won't unexpectedly happen in the middle of queuing something
# which may cause a deadlock.
eventQueue = SimpleQueue()

# Immediate work has its own lane. Historically, _immediate only made core.requestPump run sooner,
# but the queued call still sat behind any existing eventQueue backlog. During large UIA / IA2 event bursts,
# this could delay focus and input-related work. Keeping a separate internal lane preserves the public queue API
# while allowing latency-sensitive work to bypass normal backlog at the next pump.
_immediateEventQueue = SimpleQueue()

generators = {}
lastGeneratorObjID = 0


def registerGeneratorObject(generatorObj):
	global generators, lastGeneratorObjID
	if not isinstance(generatorObj, types.GeneratorType):
		raise TypeError("Arg 2 must be a generator object, not %s" % type(generatorObj))
	lastGeneratorObjID += 1
	log.debug("Adding generator %d" % lastGeneratorObjID)
	generators[lastGeneratorObjID] = generatorObj
	core.requestPump()
	return lastGeneratorObjID


def cancelGeneratorObject(generatorObjID):
	global generators
	try:
		del generators[generatorObjID]
	except KeyError:
		pass


def queueFunction(queue, func, *args, _immediate: bool = False, **kwargs):
	"""Queue a function to be executed in a specific queue.
	@param queue: The queue to use. Currently, this can only be
		L{queueHandler.eventQueue}.
	@param func: The function to run.
	@param _immediate: Whether this work is latency-sensitive (for example input or focus).
		Immediate work targeting L{eventQueue} uses a dedicated priority lane and is therefore
		executed before normal event backlog on the next pump.
	"""
	targetQueue = _immediateEventQueue if queue is eventQueue and _immediate else queue
	targetQueue.put_nowait((func, args, kwargs))
	core.requestPump(immediate=_immediate)


def isRunningGenerators():
	res = len(generators) > 0
	log.debug("generators running: %s" % res)


def _flushSingleQueue(queue):
	"""Flush the items that were pending when this flush started.

	Items queued while the flush is running are intentionally left for a subsequent pump,
	matching the historical eventQueue behaviour and preventing an event producer from
	monopolising NVDA's main thread indefinitely.
	"""
	for count in range(queue.qsize() + 1):
		if not queue.empty():
			(func, args, kwargs) = queue.get_nowait()
			watchdog.alive()
			try:
				func(*args, **kwargs)
			except:  # noqa: E722
				log.exception(f"Error in func {func.__qualname__}")


def flushQueue(queue):
	# Latency-sensitive work must bypass normal event backlog.
	# Keep this special handling private so callers can continue using eventQueue unchanged.
	if queue is eventQueue:
		_flushSingleQueue(_immediateEventQueue)
	_flushSingleQueue(queue)


def isPendingItems(queue):
	if queue is eventQueue and not _immediateEventQueue.empty():
		return True
	return not queue.empty()


def pumpAll():
	# This dict can mutate during iteration, so wrap the keys in a list.
	for ID in list(generators):
		# KeyError could occur within the generator itself, so retrieve the generator first.
		try:
			gen = generators[ID]
		except KeyError:
			# Generator was cancelled. This is fine.
			continue
		watchdog.alive()
		try:
			next(gen)
		except StopIteration:
			log.debug("generator %s finished" % ID)
			del generators[ID]
		except:  # noqa: E722
			log.exception("error in generator %d" % ID)
			del generators[ID]
		# Lose our reference so Python can destroy the generator if appropriate.
		del gen
	if generators:
		core.requestPump()
	flushQueue(eventQueue)
