import type { AssigneeGroup } from "./assignees"

export type Mailbox = "Billing" | "Support" | "Sales"

export type Thread = {
  id: string
  subject: string
  preview: string
  from: string
  mailbox: Mailbox
  attachment: boolean
  unread: boolean
  status: "open" | "done" | "archived"
  lastActivity: number
  created: number
  daily: number[]
  messages: number
  people: number
  assignee: string | null
}

export type Recording = {
  id: string
  name: string
  who: string
  device: "Laptop" | "Phone" | "Tablet"
  startedAt: number
  seconds: number
  bookmarks: number
  activity: number
  locked: boolean
}

export const MAILBOXES: Mailbox[] = ["Billing", "Support", "Sales"]

export const ASSIGNEES: AssigneeGroup[] = [
  {
    id: "members",
    label: "Members",
    options: [
      { id: "u-mira", name: "Mira Solano" },
      { id: "u-theo", name: "Theo Brandt" },
      { id: "u-priya", name: "Priya Raman" },
      { id: "u-jonas", name: "Jonas Ekwueme" },
    ],
  },
  {
    id: "teams",
    label: "Teams",
    options: [
      { id: "t-billing", name: "Billing desk" },
      { id: "t-front", name: "Front line" },
    ],
  },
]

const MIN = 60_000
const HOUR = 60 * MIN
const DAY = 24 * HOUR

type ThreadSeed = Omit<Thread, "lastActivity" | "created" | "status"> & {
  lastAgo: number
  createdAgo: number
}

const THREADS: ThreadSeed[] = [
  {
    id: "T-101",
    subject: "Refund for a duplicate charge on order 4471",
    preview:
      "I was charged twice for the same order and only one parcel arrived.",
    from: "Lena Hartmann",
    mailbox: "Billing",
    attachment: true,
    unread: true,
    lastAgo: 2 * MIN,
    createdAgo: 7 * 30 * DAY,
    daily: [3, 4, 6, 5, 8, 7, 9, 12, 10, 14, 11, 16, 18, 21],
    messages: 21000,
    people: 116,
    assignee: null,
  },
  {
    id: "T-102",
    subject: "Cannot reset password after changing my email address",
    preview:
      "The reset link says it expired the moment I open it, on two devices.",
    from: "Dario Pellegrini",
    mailbox: "Support",
    attachment: false,
    unread: true,
    lastAgo: 10 * MIN,
    createdAgo: 12 * 30 * DAY,
    daily: [5, 7, 6, 9, 8, 10, 12, 9, 11, 13, 15, 14, 12, 16],
    messages: 785,
    people: 715,
    assignee: "u-mira",
  },
  {
    id: "T-103",
    subject: "Quote request: 40 seats, annual billing, one invoice",
    preview:
      "We would like a single invoice for all teams and a purchase order number.",
    from: "Ines Marchetti",
    mailbox: "Sales",
    attachment: true,
    unread: false,
    lastAgo: 12 * MIN,
    createdAgo: 3 * 30 * DAY,
    daily: [2, 3, 2, 4, 5, 3, 6, 5, 7, 6, 8, 7, 9, 10],
    messages: 610,
    people: 610,
    assignee: "t-front",
  },
  {
    id: "T-104",
    subject:
      "Invoice PDF shows the wrong company name and an old VAT number after the address change last quarter, please reissue every invoice from this year",
    preview:
      "Accounting rejected the last three invoices because the registered name does not match.",
    from: "Oskar Lindqvist",
    mailbox: "Billing",
    attachment: true,
    unread: true,
    lastAgo: 20 * MIN,
    createdAgo: 10 * 30 * DAY,
    daily: [1, 2, 2, 3, 3, 4, 4, 5, 6, 5, 7, 8, 9, 11],
    messages: 20000,
    people: 123,
    assignee: null,
  },
  {
    id: "T-105",
    subject: "Export keeps failing on the last step",
    preview:
      "Segfault-style crash message, then the page reloads with nothing saved.",
    from: "Noor Haddad",
    mailbox: "Support",
    attachment: false,
    unread: false,
    lastAgo: 23 * MIN,
    createdAgo: 3 * 30 * DAY,
    daily: [4, 4, 5, 6, 5, 7, 8, 7, 9, 10, 9, 11, 12, 12],
    messages: 584,
    people: 584,
    assignee: "u-theo",
  },
  {
    id: "T-106",
    subject: "Divide by zero in the weekly report",
    preview:
      "The report page shows an error whenever a team has no sessions that week.",
    from: "Camille Roussel",
    mailbox: "Support",
    attachment: false,
    unread: true,
    lastAgo: 25 * MIN,
    createdAgo: 4 * DAY,
    daily: [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 2, 6, 11, 16],
    messages: 107,
    people: 107,
    assignee: null,
  },
  {
    id: "T-107",
    subject: "No stock left for item in the checkout",
    preview:
      "Customers see an out-of-stock message although the shelf count says 40.",
    from: "Mateus Oliveira",
    mailbox: "Sales",
    attachment: false,
    unread: false,
    lastAgo: 34 * 1000,
    createdAgo: 10 * 30 * DAY,
    daily: [30, 42, 38, 55, 61, 48, 70, 66, 80, 75, 92, 110, 180, 228],
    messages: 4600,
    people: 1400,
    assignee: "u-priya",
  },
  {
    id: "T-108",
    subject: "Gift card balance missing after the upgrade",
    preview:
      "The balance shows zero since yesterday. I still have the receipt.",
    from: "Sana Qureshi",
    mailbox: "Billing",
    attachment: true,
    unread: true,
    lastAgo: 2 * MIN,
    createdAgo: 2 * DAY,
    daily: [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 9, 23],
    messages: 83,
    people: 83,
    assignee: null,
  },
  {
    id: "T-109",
    subject: "Cannot read properties of undefined when opening a project",
    preview:
      "Opening any project from the sidebar shows a blank page and a console error.",
    from: "Pieter van Dijk",
    mailbox: "Support",
    attachment: false,
    unread: false,
    lastAgo: 27 * MIN,
    createdAgo: 7 * 30 * DAY,
    daily: [20, 25, 18, 30, 28, 35, 40, 38, 60, 55, 90, 110, 130, 145],
    messages: 2200,
    people: 2000,
    assignee: "u-mira",
  },
  {
    id: "T-110",
    subject: "Partnership question from a bakery chain",
    preview: "Interested in a reseller arrangement for their 14 shops.",
    from: "Elodie Fabre",
    mailbox: "Sales",
    attachment: false,
    unread: true,
    lastAgo: 3 * HOUR,
    createdAgo: 5 * DAY,
    daily: [0, 0, 0, 0, 0, 0, 0, 0, 1, 1, 2, 2, 3, 3],
    messages: 12,
    people: 12,
    assignee: null,
  },
  {
    id: "T-111",
    subject: "Receipt email arrives in the wrong language",
    preview: "Everything else is in English but the receipt is in German.",
    from: "Hannah Weiss",
    mailbox: "Billing",
    attachment: false,
    unread: false,
    lastAgo: 5 * HOUR,
    createdAgo: 2 * 30 * DAY,
    daily: [2, 1, 3, 2, 2, 4, 3, 3, 2, 4, 3, 5, 4, 4],
    messages: 94,
    people: 61,
    assignee: "t-billing",
  },
  {
    id: "T-112",
    subject: "Can the trial be extended by a week?",
    preview:
      "We lost a few days to a holiday and would like to finish evaluating.",
    from: "Victor Almeida",
    mailbox: "Sales",
    attachment: false,
    unread: false,
    lastAgo: 1 * DAY,
    createdAgo: 9 * DAY,
    daily: [0, 0, 0, 0, 0, 1, 1, 2, 1, 3, 2, 1, 0, 1],
    messages: 9,
    people: 9,
    assignee: null,
  },
]

export function buildThreads(now: number): Thread[] {
  return THREADS.map(({ lastAgo, createdAgo, ...thread }) => ({
    ...thread,
    status: "open",
    lastActivity: now - lastAgo,
    created: now - createdAgo,
  }))
}

type RecordingSeed = Omit<Recording, "startedAt"> & { startedAgo: number }

const RECORDINGS: RecordingSeed[] = [
  {
    id: "R-01",
    name: "Weekly planning call",
    who: "Jonas Ekwueme",
    device: "Laptop",
    startedAgo: 2 * MIN,
    seconds: 1760,
    bookmarks: 9,
    activity: 10,
    locked: false,
  },
  {
    id: "R-02",
    name: "Customer interview, onboarding",
    who: "Priya Raman",
    device: "Laptop",
    startedAgo: 6 * MIN,
    seconds: 359,
    bookmarks: 3,
    activity: 7,
    locked: true,
  },
  {
    id: "R-03",
    name: "Standup notes",
    who: "Mira Solano",
    device: "Phone",
    startedAgo: 7 * MIN,
    seconds: 66,
    bookmarks: 0,
    activity: 3,
    locked: false,
  },
  {
    id: "R-04",
    name: "Design walkthrough",
    who: "Theo Brandt",
    device: "Tablet",
    startedAgo: 8 * MIN,
    seconds: 87,
    bookmarks: 1,
    activity: 5,
    locked: false,
  },
  {
    id: "R-05",
    name: "Retro, sprint 14",
    who: "Lena Hartmann",
    device: "Laptop",
    startedAgo: 9 * MIN,
    seconds: 1020,
    bookmarks: 4,
    activity: 9,
    locked: false,
  },
  {
    id: "R-06",
    name: "Voice note: packaging ideas",
    who: "Dario Pellegrini",
    device: "Phone",
    startedAgo: 12 * MIN,
    seconds: 34,
    bookmarks: 0,
    activity: 2,
    locked: false,
  },
  {
    id: "R-07",
    name: "Vendor call, pricing",
    who: "Ines Marchetti",
    device: "Laptop",
    startedAgo: 15 * MIN,
    seconds: 647,
    bookmarks: 6,
    activity: 8,
    locked: true,
  },
  {
    id: "R-08",
    name: "Support huddle",
    who: "Noor Haddad",
    device: "Phone",
    startedAgo: 21 * MIN,
    seconds: 20,
    bookmarks: 0,
    activity: 1,
    locked: false,
  },
]

export function buildRecordings(now: number): Recording[] {
  return RECORDINGS.map(({ startedAgo, ...recording }) => ({
    ...recording,
    startedAt: now - startedAgo,
  }))
}

/** Relative time such as "34s ago", "2min ago", "3h ago", "4d ago". */
export function formatAgo(now: number, then: number): string {
  const seconds = Math.max(0, Math.round((now - then) / 1000))
  if (seconds < 60) return `${seconds}s ago`
  const minutes = Math.round(seconds / 60)
  if (minutes < 60) return `${minutes}min ago`
  const hours = Math.round(minutes / 60)
  if (hours < 24) return `${hours}h ago`
  return `${Math.round(hours / 24)}d ago`
}

/** Age such as "4d", "7mo", "1yr". */
export function formatAge(now: number, then: number): string {
  const days = Math.max(0, Math.floor((now - then) / DAY))
  if (days < 30) return `${days}d`
  if (days < 365) return `${Math.floor(days / 30)}mo`
  return `${Math.floor(days / 365)}yr`
}

/** Length such as "05:59". */
export function formatLength(seconds: number): string {
  const minutes = Math.floor(seconds / 60)
  return `${String(minutes).padStart(2, "0")}:${String(seconds % 60).padStart(2, "0")}`
}
