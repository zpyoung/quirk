import { compareReleases } from "./status"
import type { ConditionKind, StatusEvent, StatusModel } from "./types"

const WHEN = new Intl.DateTimeFormat(undefined, {
  weekday: "short",
  hour: "2-digit",
  minute: "2-digit",
})

function when(at: number): string {
  return WHEN.format(at)
}

function morningAfter(now: number, days: number): number {
  const day = new Date(now)
  day.setDate(day.getDate() + days)
  day.setHours(8, 0, 0, 0)
  return day.getTime()
}

function nextMonday(now: number): number {
  const weekday = new Date(now).getDay()
  return morningAfter(now, (8 - weekday) % 7 || 7)
}

function str(value: unknown): string {
  return typeof value === "string" ? value : ""
}

/**
 * Shared by every "fixed in a release" condition: the hold arms when the fix
 * release is known, then trips on an occurrence from a newer release.
 */
const watchFix: NonNullable<ConditionKind["watch"]> = (hold, event) => {
  const { armed, base, commit, fix } = hold.data
  if (event.type === "release" && armed !== true) {
    const newer = !base || compareReleases(event.version, str(base)) > 0
    const carriesCommit =
      typeof commit !== "string" || (event.commits ?? []).includes(commit)
    return newer && carriesCommit
      ? { data: { armed: true, fix: event.version } }
      : undefined
  }
  if (
    event.type === "occurrence" &&
    armed === true &&
    event.release &&
    compareReleases(event.release, str(fix)) > 0
  ) {
    return {
      trip: true,
      reason: `Event in ${event.release}, newer than ${str(fix)}`,
    }
  }
}

function describeFix(
  hold: Parameters<NonNullable<ConditionKind["describe"]>>[0]
): string {
  const { armed, commit, fix } = hold.data
  const by = typeof commit === "string" ? `commit ${commit}` : null
  if (armed === true) {
    return by
      ? `Fixed by ${by} in ${str(fix)}; reopens on an event from a newer release`
      : `Fixed in ${str(fix)}; reopens on an event from a newer release`
  }
  return by
    ? `Fixed by ${by}; waiting for a release that has it`
    : "Fix expected in the next release"
}

function dueWatch(label: string): NonNullable<ConditionKind["watch"]> {
  return (hold, _event, ctx) =>
    ctx.now >= Number(hold.data.until)
      ? { trip: true, reason: label }
      : undefined
}

function signalWatch(
  name: string,
  reason: string
): NonNullable<ConditionKind["watch"]> {
  return (_hold, event: StatusEvent) =>
    event.type === "signal" && event.name === name
      ? { trip: true, reason }
      : undefined
}

function growthWatch(
  field: "occurrences" | "users",
  noun: string
): NonNullable<ConditionKind["watch"]> {
  return (hold, event, ctx) => {
    if (event.type !== "occurrence") return
    const grown = ctx.record[field] - Number(hold.data.base)
    const goal = Number(hold.value)
    return grown >= goal
      ? { trip: true, reason: `${grown} more ${noun}` }
      : undefined
  }
}

/**
 * Bug-tracker lifecycle: Resolve and Archive split buttons. `releases` are the
 * names offered under "Another existing release".
 */
export function bugStatusModel(releases: string[]): StatusModel {
  return {
    open: "open",
    states: {
      open: { label: "Open", tone: "neutral", icon: "open" },
      resolved: { label: "Resolved", tone: "good", icon: "done" },
      regressed: { label: "Regressed", tone: "bad", icon: "regressed" },
      archived: { label: "Archived", tone: "muted", icon: "archived" },
      escalating: { label: "Escalating", tone: "warn", icon: "escalating" },
    },
    counters: { occurrences: "events", users: "users" },
    groups: [
      {
        id: "resolve",
        label: "Resolve",
        undoLabel: "Unresolve",
        menuLabel: "Resolved in",
        primary: "resolve-now",
        key: "r",
      },
      {
        id: "archive",
        label: "Archive",
        undoLabel: "Unarchive",
        menuLabel: "Archive",
        primary: "archive-escalating",
        key: "a",
      },
    ],
    kinds: [
      {
        id: "resolve-now",
        group: "resolve",
        label: "Resolve",
        enters: "resolved",
        trips: "regressed",
        inMenu: false,
        describe: () => "Reopens on any new event",
        watch: (_hold, event) =>
          event.type === "occurrence"
            ? { trip: true, reason: "New event after it was resolved" }
            : undefined,
      },
      {
        id: "resolve-next",
        group: "resolve",
        label: "The next release",
        hint: "The next release after the current one",
        enters: "resolved",
        trips: "regressed",
        start: (_value, ctx) => ({
          armed: false,
          base: ctx.record.release ?? "",
        }),
        watch: watchFix,
        describe: describeFix,
      },
      {
        id: "resolve-current",
        group: "resolve",
        label: "The current release",
        enters: "resolved",
        trips: "regressed",
        start: (_value, ctx) => ({
          armed: ctx.record.release !== undefined,
          base: ctx.record.release ?? "",
          fix: ctx.record.release ?? "",
        }),
        watch: watchFix,
        describe: describeFix,
      },
      {
        id: "resolve-release",
        group: "resolve",
        label: "Another existing release…",
        enters: "resolved",
        trips: "regressed",
        input: { type: "choice", label: "Release", options: releases },
        start: (value) => ({ armed: true, fix: str(value) }),
        watch: watchFix,
        describe: describeFix,
      },
      {
        id: "resolve-commit",
        group: "resolve",
        label: "A commit…",
        enters: "resolved",
        trips: "regressed",
        input: { type: "text", label: "Commit", placeholder: "e.g. a1b2c3d" },
        start: (value, ctx) => ({
          armed: false,
          base: ctx.record.release ?? "",
          commit: str(value),
        }),
        watch: watchFix,
        describe: describeFix,
      },
      {
        id: "archive-escalating",
        group: "archive",
        label: "Until escalating",
        hint: "When events exceed their weekly forecast",
        enters: "archived",
        trips: "escalating",
        watch: signalWatch("escalate", "Events exceeded their forecast"),
        describe: () => "Returns when it escalates",
      },
      {
        id: "archive-forever",
        group: "archive",
        label: "Forever",
        enters: "archived",
        describe: () => "Stays archived",
      },
      {
        id: "archive-for",
        group: "archive",
        label: "For…",
        enters: "archived",
        input: { type: "duration", label: "Archive for", default: 1, unit: "days" },
        start: (value, ctx) => ({ until: ctx.now + Number(value) }),
        watch: dueWatch("Archive period ended"),
        describe: (hold) => `Back ${when(Number(hold.data.until))}`,
      },
      {
        id: "archive-occurs",
        group: "archive",
        label: "Until this occurs again…",
        enters: "archived",
        trips: "escalating",
        input: {
          type: "count",
          label: "Occurs",
          unit: "more times",
          default: 10,
        },
        start: (_value, ctx) => ({ base: ctx.record.occurrences }),
        watch: growthWatch("occurrences", "events"),
        describe: (hold, ctx) =>
          `Returns after ${String(hold.value)} more events (${ctx.record.occurrences - Number(hold.data.base)} so far)`,
      },
      {
        id: "archive-users",
        group: "archive",
        label: "Until this affects an additional…",
        enters: "archived",
        trips: "escalating",
        input: {
          type: "count",
          label: "Affects an additional",
          unit: "users",
          default: 5,
        },
        start: (_value, ctx) => ({ base: ctx.record.users }),
        watch: growthWatch("users", "users"),
        describe: (hold, ctx) =>
          `Returns after ${String(hold.value)} more users (${ctx.record.users - Number(hold.data.base)} so far)`,
      },
    ],
  }
}

/** Task-list lifecycle: a Snooze split button and a plain Done button. */
export function taskStatusModel(): StatusModel {
  return {
    open: "open",
    states: {
      open: { label: "Open", tone: "neutral", icon: "open" },
      snoozed: { label: "Snoozed", tone: "muted", icon: "snoozed" },
      done: { label: "Done", tone: "good", icon: "done" },
    },
    groups: [
      {
        id: "snooze",
        label: "Snooze",
        undoLabel: "Wake",
        menuLabel: "Snooze until",
        primary: "snooze-tomorrow",
        key: "s",
      },
      {
        id: "done",
        label: "Done",
        undoLabel: "Reopen",
        menuLabel: "Done",
        primary: "done",
        key: "d",
      },
    ],
    kinds: [
      {
        id: "snooze-tomorrow",
        group: "snooze",
        label: "Tomorrow morning",
        enters: "snoozed",
        start: (_value, ctx) => ({ until: morningAfter(ctx.now, 1) }),
        watch: dueWatch("Snooze ended"),
        describe: (hold) => `Back ${when(Number(hold.data.until))}`,
      },
      {
        id: "snooze-monday",
        group: "snooze",
        label: "Next Monday",
        enters: "snoozed",
        start: (_value, ctx) => ({ until: nextMonday(ctx.now) }),
        watch: dueWatch("Snooze ended"),
        describe: (hold) => `Back ${when(Number(hold.data.until))}`,
      },
      {
        id: "snooze-reply",
        group: "snooze",
        label: "Until they reply",
        hint: "Returns when a reply arrives",
        enters: "snoozed",
        watch: signalWatch("reply", "They replied"),
        describe: () => "Back when they reply",
      },
      {
        id: "snooze-for",
        group: "snooze",
        label: "For…",
        enters: "snoozed",
        input: { type: "duration", label: "Snooze for", default: 2, unit: "hours" },
        start: (value, ctx) => ({ until: ctx.now + Number(value) }),
        watch: dueWatch("Snooze ended"),
        describe: (hold) => `Back ${when(Number(hold.data.until))}`,
      },
      {
        id: "done",
        group: "done",
        label: "Done",
        enters: "done",
        inMenu: false,
        describe: () => "Finished",
      },
    ],
  }
}
