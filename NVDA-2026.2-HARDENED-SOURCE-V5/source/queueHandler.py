# queueHandler.py
# A part of NonVisual Desktop Access (NVDA)
# Copyright (C) 2006-2018 NV Access Limited
# Copyright (C) 2026 NVDA Hardened contributors
# This file is covered by the GNU General Public License.
# See the file COPYING for more details.

from dataclasses import dataclass
import types
from queue import SimpleQueue
from time import perf_counter
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

# The core pump services several subsystems sequentially. A very large normal eventQueue backlog should not
# monopolise a whole core cycle, otherwise mouse, braille, vision and other pumps can become visibly stale.
# Direct flushQueue callers still retain the historical full-snapshot flush semantics.
_MAX_NORMAL_EVENT_ITEMS_PER_PUMP = 64

# Diagnostics are intentionally lightweight and retained in memory as the most recent pump snapshot.
# Logging is conditional so normal event traffic does not add noise to NVDA's logs.
_EVENT_QUEUE_BACKLOG_LOG_THRESHOLD = 256
_EVENT_QUEUE_LATENCY_LOG_THRESHOLD_MS = 100.0


@dataclass(frozen=True)
class _QueueFlushResult:
	itemsRemain: bool
	processedCount: int
	maxWaitMs: float


@dataclass(frozen=True)
class _EventQueueDiagnostics:
	immediatePendingBefore: int = 0
	normalPendingBefore: int = 0
	immediateProcessed: int = 0
	normalProcessed: int = 0
	maxWaitMs: float = 0.0
	pumpDurationMs: float = 0.0
	normalPendingAfter: int = 0


_lastEventQueueDiagnostics = _EventQueueDiagnostics()

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
	if queue is eventQueue:
		# The timestamp is private metadata used only for Evolution event-queue latency diagnostics.
		# Preserve the historical 3-tuple format for any non-eventQueue callers.
		targetQueue.put_nowait((func, args, kwargs, perf_counter()))
	else:
		targetQueue.put_nowait((func, args, kwargs))
	core.requestPump(immediate=_immediate)


def isRunningGenerators():
	res = len(generators) > 0
	log.debug("generators running: %s" % res)


def _flushSingleQueue(queue, maxItems: int | None = None) -> _QueueFlushResult:
	"""Flush a snapshot of queued work.

	@param maxItems: Optional upper bound for work executed during this call.
	@return: Diagnostics for the flushed snapshot.

	Items queued while the flush is running are intentionally left for a subsequent pump,
	matching the historical eventQueue behaviour and preventing an event producer from
	monopolising NVDA's main thread indefinitely.
	"""
	itemsToProcess = queue.qsize() + 1
	if maxItems is not None:
		itemsToProcess = min(itemsToProcess, maxItems)
	processedCount = 0
	maxWaitMs = 0.0
	for count in range(itemsToProcess):
		if not queue.empty():
			item = queue.get_nowait()
			queuedAt = None
			if len(item) == 4:
				(func, args, kwargs, queuedAt) = item
			else:
				(func, args, kwargs) = item
			watchdog.alive()
			processedCount += 1
			if queuedAt is not None:
				waitMs = max(0.0, (perf_counter() - queuedAt) * 1000.0)
				maxWaitMs = max(maxWaitMs, waitMs)
			try:
				func(*args, **kwargs)
			except:  # noqa: E722
				log.exception(f"Error in func {func.__qualname__}")
	return _QueueFlushResult(
		itemsRemain=not queue.empty(),
		processedCount=processedCount,
		maxWaitMs=maxWaitMs,
	)


def flushQueue(queue):
	# Latency-sensitive work must bypass normal event backlog.
	# Keep this special handling private so callers can continue using eventQueue unchanged.
	if queue is eventQueue:
		_flushSingleQueue(_immediateEventQueue)
	_flushSingleQueue(queue)


def _getEventQueueDiagnostics() -> _EventQueueDiagnostics:
	"""Return the most recent event-queue pump snapshot for diagnostics and tests."""
	return _lastEventQueueDiagnostics


def _flushEventQueueForPump() -> None:
	"""Flush event work for one core pump cycle with fairness between NVDA subsystems."""
	global _lastEventQueueDiagnostics
	immediatePendingBefore = _immediateEventQueue.qsize()
	normalPendingBefore = eventQueue.qsize()
	pumpStartedAt = perf_counter()
	immediateResult = _flushSingleQueue(_immediateEventQueue)
	normalResult = _flushSingleQueue(eventQueue, maxItems=_MAX_NORMAL_EVENT_ITEMS_PER_PUMP)
	pumpDurationMs = max(0.0, (perf_counter() - pumpStartedAt) * 1000.0)
	maxWaitMs = max(immediateResult.maxWaitMs, normalResult.maxWaitMs)
	_lastEventQueueDiagnostics = _EventQueueDiagnostics(
		immediatePendingBefore=immediatePendingBefore,
		normalPendingBefore=normalPendingBefore,
		immediateProcessed=immediateResult.processedCount,
		normalProcessed=normalResult.processedCount,
		maxWaitMs=maxWaitMs,
		pumpDurationMs=pumpDurationMs,
		normalPendingAfter=eventQueue.qsize(),
	)
	if (
		normalPendingBefore >= _EVENT_QUEUE_BACKLOG_LOG_THRESHOLD
		or maxWaitMs >= _EVENT_QUEUE_LATENCY_LOG_THRESHOLD_MS
		or pumpDurationMs >= _EVENT_QUEUE_LATENCY_LOG_THRESHOLD_MS
	):
		log.debug(
			"Event queue pressure: "
			f"immediatePending={immediatePendingBefore}, normalPending={normalPendingBefore}, "
			f"immediateProcessed={immediateResult.processedCount}, "
			f"normalProcessed={normalResult.processedCount}, "
			f"normalRemaining={_lastEventQueueDiagnostics.normalPendingAfter}, "
			f"maxWaitMs={maxWaitMs:.1f}, pumpDurationMs={pumpDurationMs:.1f}",
		)
	if normalResult.itemsRemain:
		# Continue promptly, but return control to core first so the remaining subsystem pumps get a turn.
		core.requestPump()


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
	_flushEventQueueForPump()
