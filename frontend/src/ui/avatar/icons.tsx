import type { ReactElement } from "react";
import type { AvatarName } from "./defaultAvatarName";

const ink = "#111";
const peach = "#ffc9a8";
const butter = "#ffe9a8";
const mint = "#c4f0dc";
const sky = "#bfe2ff";
const lilac = "#ddcbff";
const rose = "#ffc6d8";

export const icons: Record<
  AvatarName,
  { node: ReactElement; background: string }
> = {
  orbit: {
    background: sky,
    node: (
      <>
        <circle cx="16" cy="16" r="5" fill={ink} />
        <ellipse
          cx="16"
          cy="16"
          rx="11"
          ry="5"
          fill="none"
          stroke={ink}
          strokeWidth="1.5"
          transform="rotate(-30 16 16)"
        />
      </>
    ),
  },
  prism: {
    background: butter,
    node: (
      <>
        <path
          d="M16 6 L26 24 H6 Z"
          fill={lilac}
          stroke={ink}
          strokeWidth="1.5"
        />
        <path d="M16 6 V24" stroke={ink} strokeWidth="1.5" />
      </>
    ),
  },
  wave: {
    background: mint,
    node: (
      <path
        d="M5 13 q5.5-6 11 0 t11 0 M5 20 q5.5-6 11 0 t11 0"
        fill="none"
        stroke={ink}
        strokeWidth="1.8"
        strokeLinecap="round"
      />
    ),
  },
  grid: {
    background: butter,
    node: (
      <>
        <rect x="8" y="8" width="6" height="6" rx="1.5" fill={ink} />
        <rect
          x="18"
          y="8"
          width="6"
          height="6"
          rx="1.5"
          fill={sky}
          stroke={ink}
        />
        <rect
          x="8"
          y="18"
          width="6"
          height="6"
          rx="1.5"
          fill={peach}
          stroke={ink}
        />
        <rect x="18" y="18" width="6" height="6" rx="1.5" fill={ink} />
      </>
    ),
  },
  petal: {
    background: mint,
    node: (
      <>
        <g fill={rose} stroke={ink} strokeWidth="1.4">
          <ellipse cx="16" cy="10" rx="4" ry="6" />
          <ellipse cx="16" cy="22" rx="4" ry="6" />
          <ellipse cx="10" cy="16" rx="6" ry="4" />
          <ellipse cx="22" cy="16" rx="6" ry="4" />
        </g>
        <circle cx="16" cy="16" r="3" fill={ink} />
      </>
    ),
  },
  ring: {
    background: lilac,
    node: (
      <>
        <circle
          cx="16"
          cy="16"
          r="9"
          fill="none"
          stroke={ink}
          strokeWidth="3"
        />
        <circle
          cx="16"
          cy="16"
          r="3.5"
          fill={butter}
          stroke={ink}
          strokeWidth="1.4"
        />
      </>
    ),
  },
  stack: {
    background: rose,
    node: (
      <g stroke={ink} strokeWidth="1.4">
        <rect x="7" y="19" width="18" height="5" rx="2.5" fill={mint} />
        <rect x="9" y="13.5" width="14" height="5" rx="2.5" fill={sky} />
        <rect x="11" y="8" width="10" height="5" rx="2.5" fill={lilac} />
      </g>
    ),
  },
  spark: {
    background: lilac,
    node: (
      <path
        d="M16 5 L18.5 13.5 L27 16 L18.5 18.5 L16 27 L13.5 18.5 L5 16 L13.5 13.5 Z"
        fill={butter}
        stroke={ink}
        strokeWidth="1.4"
        strokeLinejoin="round"
      />
    ),
  },
  arc: {
    background: peach,
    node: (
      <>
        <path
          d="M7 23 A9 9 0 0 1 25 23"
          fill="none"
          stroke={ink}
          strokeWidth="3"
          strokeLinecap="round"
        />
        <circle cx="16" cy="11" r="3" fill={ink} />
      </>
    ),
  },
  tile: {
    background: sky,
    node: (
      <>
        <rect
          x="8"
          y="8"
          width="16"
          height="16"
          rx="3"
          fill={peach}
          stroke={ink}
          strokeWidth="1.4"
          transform="rotate(45 16 16)"
        />
        <rect
          x="12.5"
          y="12.5"
          width="7"
          height="7"
          rx="1.5"
          fill="#fff"
          stroke={ink}
          strokeWidth="1.4"
          transform="rotate(45 16 16)"
        />
      </>
    ),
  },
};
