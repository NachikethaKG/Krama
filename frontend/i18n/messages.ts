import { DEFAULT_LOCALE, type Locale, NAMESPACES } from "./config";

type Messages = Record<string, unknown>;

/**
 * Every namespace's messages for `locale`, each over the English ones, so a string not translated yet shows in
 * English instead of as a key.
 */
export async function loadMessages(locale: Locale): Promise<Messages> {
  const out: Messages = {};
  for (const ns of NAMESPACES) {
    const english = await load(DEFAULT_LOCALE, ns);
    const local = locale === DEFAULT_LOCALE ? {} : await load(locale, ns);
    out[ns] = merge(english, local);
  }
  return out;
}

async function load(locale: Locale, ns: string): Promise<Messages> {
  try {
    return (await import(`../messages/${locale}/${ns}.json`)).default as Messages;
  } catch {
    return {};
  }
}

function merge(base: Messages, over: Messages): Messages {
  const out: Messages = { ...base };
  for (const [key, value] of Object.entries(over)) {
    const b = out[key];
    out[key] =
      b && typeof b === "object" && value && typeof value === "object"
        ? merge(b as Messages, value as Messages)
        : value;
  }
  return out;
}
