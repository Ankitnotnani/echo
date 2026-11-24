// Small stroke icons drawn inline (no icon library needed).
import type { SVGProps } from "react";

type P = SVGProps<SVGSVGElement>;

function Base({ children, ...rest }: P) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.7}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      focusable="false"
      {...rest}
    >
      {children}
    </svg>
  );
}

export const IconLogo = (p: P) => (
  <svg viewBox="0 0 24 24" aria-hidden="true" {...p}>
    <circle cx="12" cy="12" r="8.2" fill="none" stroke="currentColor" strokeWidth="2" />
    <circle cx="12" cy="12" r="3.4" fill="currentColor" />
    <path d="M4 12h2.4M17.6 12H20" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
  </svg>
);
export const IconHome = (p: P) => (
  <Base {...p}><path d="M4 11.5 12 5l8 6.5" /><path d="M6.5 10v8.5h11V10" /></Base>
);
export const IconChat = (p: P) => (
  <Base {...p}><path d="M5 6.5h14v9H10l-4 3v-3H5z" /></Base>
);
export const IconGrid = (p: P) => (
  <Base {...p}><rect x="5" y="5" width="5.5" height="5.5" rx="1.2" /><rect x="13.5" y="5" width="5.5" height="5.5" rx="1.2" /><rect x="5" y="13.5" width="5.5" height="5.5" rx="1.2" /><rect x="13.5" y="13.5" width="5.5" height="5.5" rx="1.2" /></Base>
);
export const IconSpark = (p: P) => (
  <Base {...p}><path d="M12 4.5v3M12 16.5v3M4.5 12h3M16.5 12h3M7 7l2 2M15 15l2 2M17 7l-2 2M9 15l-2 2" /></Base>
);
export const IconChart = (p: P) => (
  <Base {...p}><path d="M5 19V5M5 19h14" /><path d="M8.5 15l3-4 3 2.5L19 8" /></Base>
);
export const IconFolder = (p: P) => (
  <Base {...p}><path d="M4.5 7.5h5l1.6 2h8.4v8.5h-15z" /></Base>
);
export const IconBook = (p: P) => (
  <Base {...p}><path d="M6 5.5h9.5a2 2 0 0 1 2 2V19H8a2 2 0 0 1-2-2z" /><path d="M6 17a2 2 0 0 1 2-2h9.5" /></Base>
);
export const IconUser = (p: P) => (
  <Base {...p}><circle cx="12" cy="9" r="3.4" /><path d="M5.5 19c1.2-3 3.6-4.5 6.5-4.5s5.3 1.5 6.5 4.5" /></Base>
);
export const IconSettings = (p: P) => (
  <Base {...p}><circle cx="12" cy="12" r="2.8" /><path d="M12 4v2M12 18v2M4 12h2M18 12h2M6.3 6.3l1.4 1.4M16.3 16.3l1.4 1.4M17.7 6.3l-1.4 1.4M7.7 16.3l-1.4 1.4" /></Base>
);
export const IconBack = (p: P) => (
  <Base {...p}><path d="M14.5 6.5 9 12l5.5 5.5" /></Base>
);
export const IconForward = (p: P) => (
  <Base {...p}><path d="M5 12h13M13 7l5 5-5 5" /></Base>
);
export const IconSearch = (p: P) => (
  <Base {...p}><circle cx="11" cy="11" r="5.5" /><path d="m15.2 15.2 3.8 3.8" /></Base>
);
export const IconBell = (p: P) => (
  <Base {...p}><path d="M7 16.5V11a5 5 0 0 1 10 0v5.5l1.5 1.5h-13z" /><path d="M10.5 20h3" /></Base>
);
export const IconPlus = (p: P) => (
  <Base {...p}><path d="M12 6v12M6 12h12" /></Base>
);
export const IconCaret = (p: P) => (
  <Base {...p}><path d="m7.5 10 4.5 4.5 4.5-4.5" /></Base>
);
export const IconMic = (p: P) => (
  <Base {...p}><rect x="9.5" y="4.5" width="5" height="10" rx="2.5" /><path d="M6.5 11.5a5.5 5.5 0 0 0 11 0M12 17v2.5" /></Base>
);
export const IconSend = (p: P) => (
  <Base {...p} strokeWidth={2}><path d="M12 18.5V6M6.5 11.5 12 6l5.5 5.5" /></Base>
);
export const IconLightbulb = (p: P) => (
  <Base {...p}><path d="M9 17h6M10 20h4" /><path d="M8 13.5a5 5 0 1 1 8 0c-.8 1-1.2 1.8-1.2 3.5H9.2c0-1.7-.4-2.5-1.2-3.5z" /></Base>
);
export const IconPen = (p: P) => (
  <Base {...p}><path d="M5 19l1-4.2L15.5 5.3a2 2 0 0 1 2.8 0l.4.4a2 2 0 0 1 0 2.8L9.2 18z" /><path d="M14 7l3 3" /></Base>
);
export const IconCalendar = (p: P) => (
  <Base {...p}><rect x="4.5" y="6" width="15" height="13" rx="2" /><path d="M4.5 10h15M9 4v3.5M15 4v3.5" /></Base>
);
export const IconArrowUpRight = (p: P) => (
  <Base {...p}><path d="M8 16 16 8M9.5 8H16v6.5" /></Base>
);
export const IconBolt = (p: P) => (
  <Base {...p}><path d="M13 4 6.5 13H12l-1 7 6.5-9H12z" /></Base>
);
export const IconClock = (p: P) => (
  <Base {...p}><circle cx="12" cy="12" r="7" /><path d="M12 8.5V12l2.5 1.5" /></Base>
);
export const IconCpu = (p: P) => (
  <Base {...p}><rect x="7" y="7" width="10" height="10" rx="2" /><path d="M10 4v3M14 4v3M10 17v3M14 17v3M4 10h3M4 14h3M17 10h3M17 14h3" /></Base>
);
export const IconKey = (p: P) => (
  <Base {...p}><circle cx="8.5" cy="12" r="3.2" /><path d="M11.7 12H20M17 12v3M19.5 12v2" /></Base>
);
export const IconRetry = (p: P) => (
  <Base {...p}><path d="M18.5 9A7 7 0 1 0 19 13.5" /><path d="M19 4.5V9h-4.5" /></Base>
);
export const IconInfo = (p: P) => (
  <Base {...p}><circle cx="12" cy="12" r="8" /><path d="M12 11v5M12 8h.01" /></Base>
);
export const IconLayers = (p: P) => (
  <Base {...p}><path d="m12 4.5 8 4-8 4-8-4z" /><path d="m4 12.5 8 4 8-4M4 16.5l8 4 8-4" /></Base>
);
export const IconClose = (p: P) => (
  <Base {...p}><path d="M7 7l10 10M17 7 7 17" /></Base>
);
