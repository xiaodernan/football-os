/**
 * The knowledge library's nine categories, as the reader's language spells them.
 *
 * The slug is an API fact; this maps it to a catalogue key so the library never prints
 * a raw slug where a label belongs. Unknown slugs keep the slug (honest fallback for a
 * category the static map has not met yet) — they change by one line here, not by a schema move.
 */
const CATEGORY_KEYS: Record<string, string> = {
  tactics: "tactics",
  training: "training",
  "sports-science": "sports-science",
  "match-analysis": "match-analysis",
  rules: "rules",
  coaching: "coaching",
  history: "history",
  "team-profile": "team-profile",
  "player-profile": "player-profile",
};

type Translate = (key: string) => string;

export function categoryLabel(t: Translate, slug: string): string {
  const key = CATEGORY_KEYS[slug];
  return key ? t(`knowledgeCategories.${key}`) : slug.replace(/_/g, " ");
}

const DIFFICULTY_KEYS: Record<string, string> = {
  beginner: "difficultyBeginner",
  intermediate: "difficultyIntermediate",
  advanced: "difficultyAdvanced",
};

export function difficultyLabel(t: Translate, difficulty: string): string {
  const key = DIFFICULTY_KEYS[difficulty.toLowerCase()];
  return key ? t(key) : difficulty;
}
