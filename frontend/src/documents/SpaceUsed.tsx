import { isFull, usedText, type Space } from "./space";
import styles from "./SpaceUsed.module.css";

const WARN_FROM = 0.8;

export function SpaceUsed({ space }: { space: Space }) {
  const { used, limit } = space;
  const full = isFull(space);
  const text = usedText(used, limit);
  const share = limit > 0 ? Math.min(used / limit, 1) : 1;
  const meterClass = [styles.bar, share >= WARN_FROM ? styles.warn : ""]
    .filter(Boolean)
    .join(" ");

  return (
    <div className={styles.space}>
      <span aria-hidden="true">
        <span>{text}</span>
        {full && (
          <>
            {" · "}
            <strong className={styles.reached}>Limit reached</strong>
          </>
        )}
      </span>
      <div
        role="meter"
        aria-label="Space used"
        aria-valuemin={0}
        aria-valuemax={limit}
        aria-valuenow={Math.min(used, limit)}
        aria-valuetext={full ? `${text}. Limit reached` : text}
        className={meterClass}
      >
        <span
          className={[styles.fill, used > 0 ? styles.some : ""]
            .filter(Boolean)
            .join(" ")}
          style={{ width: `${String(share * 100)}%` }}
        />
      </div>
    </div>
  );
}
