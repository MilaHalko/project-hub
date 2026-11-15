import styles from "./DocumentsSection.module.css";
import { fileKind } from "./fileRules";

export function FileTile({ name }: { name: string }) {
  const kind = fileKind(name);
  const extension = /\.([^.]{1,4})$/.exec(name)?.[1] ?? "";
  return (
    <span
      className={[styles.tile, kind ? styles[kind] : styles.other].join(" ")}
      aria-hidden="true"
    >
      {(kind ?? extension).toUpperCase()}
    </span>
  );
}
