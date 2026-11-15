export const avatarNames = [
  "orbit",
  "prism",
  "wave",
  "grid",
  "petal",
  "ring",
  "stack",
  "spark",
  "arc",
  "tile",
] as const;

export type AvatarName = (typeof avatarNames)[number];

export function defaultAvatarName(userId: string): AvatarName {
  let hash = 0x811c9dc5;
  for (let i = 0; i < userId.length; i += 1) {
    hash ^= userId.charCodeAt(i);
    hash = Math.imul(hash, 0x01000193);
  }
  return avatarNames[(hash >>> 0) % avatarNames.length] as AvatarName;
}
