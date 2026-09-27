// 线条图标，统一 24 网格、描边 1.6，颜色跟随文字。
const PATHS = {
  back: <path d="M19 12H5M11 18l-6-6 6-6" />,
  toc: <path d="M9 6h11M9 12h11M9 18h11M4.5 6h.01M4.5 12h.01M4.5 18h.01" />,
  type: <path d="M3 18L8 5l5 13M5 13.5h6M15 18v-5.2a2.6 2.6 0 0 1 5.2 0V18M15 15.2h5.2" />,
  comment: <path d="M20 11.5a7.5 7.5 0 0 1-10.9 6.7L4 19.5l1.3-4.6A7.5 7.5 0 1 1 20 11.5z" />,
  close: <path d="M18 6L6 18M6 6l12 12" />,
  upload: <path d="M12 15V4M7.5 8.5L12 4l4.5 4.5M4.5 15v3.5a1.5 1.5 0 0 0 1.5 1.5h12a1.5 1.5 0 0 0 1.5-1.5V15" />,
  trash: <path d="M4 7h16M10 11v6M14 11v6M5.5 7l1 12.5a1 1 0 0 0 1 .9h9a1 1 0 0 0 1-.9l1-12.5M9 7V4.5h6V7" />,
  refresh: <path d="M19.5 12a7.5 7.5 0 1 1-2.2-5.3M19.5 4.5v4h-4" />,
  prev: <path d="M15 18l-6-6 6-6" />,
  next: <path d="M9 18l6-6-6-6" />,
  book: <path d="M5 4.5A1.5 1.5 0 0 1 6.5 3H19v15H6.5A1.5 1.5 0 0 0 5 19.5v-15zM5 19.5A1.5 1.5 0 0 0 6.5 21H19" />,
  search: <path d="M10.5 17a6.5 6.5 0 1 0 0-13 6.5 6.5 0 0 0 0 13zM15.5 15.5L20 20" />,
  arrowOut: <path d="M8 16L16 8M9 8h7v7" />,
  info: <path d="M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18zM12 11v5M12 8h.01" />,
  sparkle: <path d="M12 3.5l1.9 5.2 5.1 1.9-5.1 1.9L12 17.7l-1.9-5.2L5 10.6l5.1-1.9L12 3.5zM18.5 16.5l.7 1.8 1.8.7-1.8.7-.7 1.8-.7-1.8-1.8-.7 1.8-.7.7-1.8z" />,
  check: <path d="M5 12.5l4.5 4.5L19 7.5" />,
  minus: <path d="M5 12h14" />,
  plus: <path d="M12 5v14M5 12h14" />,
}

export default function Icon({ name, size, className = '' }) {
  return (
    <svg className={`icon ${className}`} viewBox="0 0 24 24" aria-hidden="true"
      style={size ? { width: size, height: size } : undefined}>
      {PATHS[name]}
    </svg>
  )
}
