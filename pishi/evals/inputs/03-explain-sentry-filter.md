# Вопрос: «объясни по-русски, в чём тут проблема и что ты предлагаешь»

Заметки расследования (на английском, как писал агент):

Task: verify whether the "empty booking window" error (guest opens /app/<booking>, sees a blank panel) reproduces on prod, by counting Sentry events. Assumption in the task: `captureException(err)` runs right before `setError(err)` in `BookingWindow.tsx`, so every blank window must produce a Sentry event.

Findings:

1. The assumption does not hold. Since 5 May Sentry has zero events of this class — not because the bug stopped, but because commit `a7f31c0` ("reduce sentry noise") added a `beforeSend` filter that drops any event where `error.name === 'ApiError'` and status is 4xx. The blank-window error is an `ApiError` 404 (booking lookup by slug fails when the slug is stale). Every one of these is filtered client-side.
2. Independent evidence the bug is live: product analytics event `booking_window_error` — 180 occurrences in the last 30 days, 150 distinct guests. Server logs show 404 on `/api/bookings/by-slug/*` 1 400 times in the same window.
3. Why slugs go stale: the slug is regenerated when ops edits the booking's check-in date in admin (`Booking.save()` → `regen_slug()` if dates changed). The guest's old link (already emailed) then 404s. 52 of the 150 guests had a date change.
4. Sampling is 0.2 on prod (`tracesSampleRate`) — that's transactions, not errors; not the cause.

Proposal:
- Stop filtering 404 `ApiError` in `beforeSend` for the booking-window route only.
- Stop regenerating the slug on date edit; keep it stable for the booking's lifetime. One-off redirect table `old_slug → booking_id` for the 52 broken links.
- Show a real message: «Ссылка устарела — напишите в поддержку» with the booking number, instead of the blank panel.

The user needs to retell this to the CTO on a call in an hour.
