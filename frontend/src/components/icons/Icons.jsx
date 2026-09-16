import './Icons.css';

function Svg({ children, size = 20, ...rest }) {
  return (
    <svg
      className="ic"
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.8}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      {...rest}
    >
      {children}
    </svg>
  );
}

export function IconFolder(props) {
  return (
    <Svg {...props}>
      <path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z" />
    </Svg>
  );
}

export function IconChat(props) {
  return (
    <Svg {...props}>
      <path d="M21 12a8 8 0 0 1-8 8H4l2-3a8 8 0 1 1 15-5z" />
      <path d="M8.5 12h.01M12 12h.01M15.5 12h.01" />
    </Svg>
  );
}

export function IconTarget(props) {
  return (
    <Svg {...props}>
      <circle cx="12" cy="12" r="9" />
      <circle cx="12" cy="12" r="5" />
      <circle cx="12" cy="12" r="1.2" fill="currentColor" />
    </Svg>
  );
}

export function IconChart(props) {
  return (
    <Svg {...props}>
      <path d="M4 20V10M10 20V4M16 20v-8M21 20H3" />
    </Svg>
  );
}

export function IconChevron(props) {
  return (
    <Svg {...props} size={props.size || 16}>
      <path d="M9 6l6 6-6 6" />
    </Svg>
  );
}

export function IconPencil(props) {
  return (
    <Svg {...props} size={props.size || 16}>
      <path d="M17 3l4 4L8 20l-5 1 1-5z" />
    </Svg>
  );
}

export function IconTrash(props) {
  return (
    <Svg {...props} size={props.size || 16}>
      <path d="M4 7h16M9 7V5a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v2m3 0l-1 13a1 1 0 0 1-1 1H8a1 1 0 0 1-1-1L6 7" />
    </Svg>
  );
}

export function IconPlus(props) {
  return (
    <Svg {...props} size={props.size || 16}>
      <path d="M12 5v14M5 12h14" />
    </Svg>
  );
}

export function IconX(props) {
  return (
    <Svg {...props} size={props.size || 16}>
      <path d="M6 6l12 12M18 6L6 18" />
    </Svg>
  );
}

export function IconCheck(props) {
  return (
    <Svg {...props} size={props.size || 16}>
      <path d="M4 12.5l5 5L20 6.5" />
    </Svg>
  );
}

export function IconArrowRight(props) {
  return (
    <Svg {...props} size={props.size || 18}>
      <path d="M4 12h15M13 6l6 6-6 6" />
    </Svg>
  );
}

export function IconArrowLeft(props) {
  return (
    <Svg {...props} size={props.size || 18}>
      <path d="M20 12H5M11 6l-6 6 6 6" />
    </Svg>
  );
}

export function IconUpload(props) {
  return (
    <Svg {...props} size={props.size || 40}>
      <path d="M12 16V4M7 9l5-5 5 5" />
      <path d="M4 20h16" />
    </Svg>
  );
}

export function IconFile(props) {
  return (
    <Svg {...props}>
      <path d="M6 2h8l4 4v16H6z" />
      <path d="M14 2v4h4" />
    </Svg>
  );
}

export function IconBook(props) {
  return (
    <Svg {...props} size={props.size || 26}>
      <path d="M4 5a2 2 0 0 1 2-2h13v16H6a2 2 0 0 0-2 2z" />
      <path d="M4 19a2 2 0 0 1 2-2h13" />
    </Svg>
  );
}

export function IconSpark(props) {
  return (
    <Svg {...props} size={props.size || 26}>
      <path d="M12 2l2.2 6.6L21 11l-6.8 2.4L12 20l-2.2-6.6L3 11l6.8-2.4z" />
    </Svg>
  );
}

export function IconClipboard(props) {
  return (
    <Svg {...props} size={props.size || 40}>
      <rect x="5" y="4" width="14" height="17" rx="2" />
      <path d="M9 4a2 2 0 0 1 6 0M9 12h6M9 16h4" />
    </Svg>
  );
}

export function IconGraduation(props) {
  return (
    <Svg {...props} size={props.size || 26}>
      <path d="M2 9l10-5 10 5-10 5z" />
      <path d="M6 11.5V16c0 1.5 2.7 3 6 3s6-1.5 6-3v-4.5M22 9v5" />
    </Svg>
  );
}
