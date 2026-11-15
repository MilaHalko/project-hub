import { defaultAvatarName } from "./defaultAvatarName";
import { icons } from "./icons";
import styles from "./Avatar.module.css";

export function Avatar({ userId, size }: { userId: string; size: number }) {
  const name = defaultAvatarName(userId);
  const { node, background } = icons[name];
  return (
    <svg
      className={styles.avatar}
      data-avatar={name}
      width={size}
      height={size}
      viewBox="0 0 32 32"
      aria-hidden="true"
      focusable="false"
      style={{ background }}
    >
      {node}
    </svg>
  );
}
