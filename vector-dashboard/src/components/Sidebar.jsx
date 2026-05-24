const navItems = [
  {
    label: 'Dashboard',
    href: '#',
    current: true,
    icon: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden>
        <rect x="3" y="3" width="7" height="7" rx="1" />
        <rect x="14" y="3" width="7" height="7" rx="1" />
        <rect x="3" y="14" width="7" height="7" rx="1" />
        <rect x="14" y="14" width="7" height="7" rx="1" />
      </svg>
    ),
  },
  
]

export function Sidebar() {
  return (
    <aside className="sidebar" aria-label="Primary">
      <div className="brand">
        <div className="brand-name">VECTOR</div>
        <div className="brand-tag">Governance evaluation console</div>
      </div>
      <nav className="nav" aria-label="Main navigation">
        {navItems.map((item) => (
          <a key={item.label} href={item.href} aria-current={item.current ? 'page' : undefined}>
            {item.icon}
            {item.label}
          </a>
        ))}
      </nav>
      <div className="sidebar-foot">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden>
          <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
        </svg>
        v2.0.0
      </div>
    </aside>
  )
}
