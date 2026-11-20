# Recording retention validation

The global recording settings, channel recording settings, dedicated channel
policy save, and custom cleanup require a supported policy type and a positive
integer threshold. Invalid inputs return HTTP **422** without saving or deleting
anything. Numeric strings, fractions, and booleans are not thresholds.

| Policy | Unit | Inclusive range |
| --- | --- | --- |
| `count` | Recordings to keep | 1 to 2,147,483,647 (the legacy PostgreSQL integer count limit) |
| `size` | GiB | 1 to 8,589,934,591 (largest whole GiB in the signed 64-bit byte range) |
| `age` | Days | 1 to the number of whole calendar days since 0001-01-01 UTC (earliest representable cutoff) |

An explicit policy threshold of `0` is not supported. The separate legacy
`max_streams_per_streamer` and `max_streams` count settings accept `0` through
2,147,483,647. If no explicit policy applies, a positive channel limit wins;
otherwise the global count limit applies. An effective count limit of `0` is
unlimited and never becomes a delete-all instruction. A null channel limit
still leaves the global limit in effect.

Settings responses return stored legacy count values unchanged, even if they
cannot be submitted as new limits. Saving without the count leaves it intact.
To repair a count, send a valid integer in the affected field; sending an
invalid value explicitly returns a field-specific HTTP **422**.

`preserve_favorites` must be a JSON boolean if provided; its default is `true`.
`preserve_categories` accepts a list of names or null. Optional timeframes use
inclusive ISO date/datetime bounds (offsets are compared in UTC; no offset means
UTC), weekdays from 0 (Monday) to 6 (Sunday), and complete `timeOfDay.start` and
`timeOfDay.end` clock times. Overnight clock windows are supported.

If the effective stored rule is malformed, manual cleanup returns HTTP **409**
with the affected policy scope and field. Scheduled cleanup logs the channel ID
and reason and skips that channel. Replace the invalid setting with a valid
policy or choose inheritance explicitly for a channel; the application does not
rewrite invalid rules or pick another rule in their place.

Preview and execution select from the same completed history. They exclude
active streams and streams ended less than five minutes ago, and protect the
same favorites, named categories, and timeframes. Execution can still delete
fewer records than previewed, for example if a required file cannot be deleted
or a later preview sees a different catalog. A failed required-file deletion
retains the corresponding catalog record for retry.
