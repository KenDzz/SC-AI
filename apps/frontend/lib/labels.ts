export const EVENT_LABELS: Record<string, string> = {
  RESTRICTED_AREA_INTRUSION: "Restricted area",
  HAIRNET_VIOLATION: "Missing hairnet",
  UNIFORM_VIOLATION: "Incorrect uniform",
  MACHINE_DANGER_ZONE_INTRUSION: "Machine danger zone",
  PEDESTRIAN_IN_FORKLIFT_ZONE: "Pedestrian in forklift lane",
  GREEN_COFFEE_DEFECT_RATE: "Green bean defect rate",
  ROASTED_COFFEE_DEFECT_RATE: "Roasted bean defect rate",
};

export const ZONE_LABELS: Record<string, string> = {
  RESTRICTED_AREA: "Restricted area",
  MACHINE_DANGER_ZONE: "Machine danger zone",
  FORKLIFT_LANE: "Forklift lane",
  PRODUCTION_ZONE: "Production zone",
  PACKING_ZONE: "Packing zone",
  GREEN_COFFEE_LINE: "Green coffee belt",
  ROASTED_COFFEE_LINE: "Roasted coffee belt",
  COFFEE_COUNT_LINE: "Coffee count belt",
};

export const BEAN_LABELS: Record<string, string> = {
  good: "Good",
  black: "Black",
  broken: "Broken",
  fade: "Fade",
  sour: "Sour",
  quaker: "Quaker",
  burnt: "Burnt",
  insect: "Insect",
  mould: "Mould",
  bean: "Bean",
};

export const COFFEE_STAGE_LABELS: Record<string, string> = {
  green: "Green coffee",
  roasted: "Roasted coffee",
  count: "Count only",
};

export const STATUS_LABELS: Record<string, string> = {
  NEW: "New",
  CONFIRMED: "Confirmed",
  FALSE_POSITIVE: "False positive",
  RESOLVED: "Resolved",
  ONLINE: "Online",
  OFFLINE: "Offline",
  AI_PROCESSING: "AI processing",
  DISABLED: "Disabled",
};

export const CONDITION_LABELS: Record<string, string> = {
  PERSON_INSIDE: "Person inside zone",
  HAIRNET_MISSING: "Hairnet missing",
  UNIFORM_INCORRECT: "Incorrect uniform",
  DEFECT_RATE: "Defect rate on the belt",
};

export function eventLabel(value: string) {
  return EVENT_LABELS[value] || value;
}

export function formatWhen(value?: string | null) {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat("en-GB", {
    timeZone: "Asia/Ho_Chi_Minh",
    year: "numeric",
    month: "short",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  }).format(date);
}

export function percent(value?: number | null) {
  if (value === null || value === undefined) return "—";
  return `${Math.round(value * 100)}%`;
}
