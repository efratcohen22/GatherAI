/** Minimal i18n foundation. Hebrew covers navigation today; add keys here as screens are translated. */
export type Lang = "en" | "he";

const dictionary: Record<string, Record<Lang, string>> = {
  overview: { en: "Overview", he: "סקירה" },
  participants: { en: "Participants", he: "משתתפים" },
  transportation: { en: "Transportation", he: "הסעות" },
  accommodations: { en: "Accommodations", he: "אירוח" },
  tasks: { en: "Tasks", he: "משימות" },
  messages: { en: "Messages", he: "הודעות" },
  assistant: { en: "AI Assistant", he: "עוזר AI" },
  simulator: { en: "Chat simulator", he: "סימולטור צ'אט" },
  event_settings: { en: "Event settings", he: "הגדרות אירוע" },
  settings: { en: "Settings", he: "הגדרות" },
  events: { en: "Events", he: "אירועים" },
  team: { en: "Team", he: "צוות" },
};

export function getLang(): Lang {
  try { return localStorage.getItem("gatherai.lang") === "he" ? "he" : "en"; } catch { return "en"; }
}

export function applyLang(lang: Lang) {
  try { localStorage.setItem("gatherai.lang", lang); } catch { /* storage unavailable */ }
  document.documentElement.lang = lang;
  document.documentElement.dir = lang === "he" ? "rtl" : "ltr";
}

export const t = (key: string): string => dictionary[key]?.[getLang()] ?? key;
