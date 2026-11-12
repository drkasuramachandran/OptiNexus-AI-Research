export const Logo = ({ size = 36 }) => (
  <svg width={size} height={size} viewBox="0 0 48 48" fill="none" aria-label="OptiNexus AI logo" data-testid="app-logo">
    <circle cx="20" cy="24" r="5" stroke="#22D3EE" strokeWidth="2" />
    <circle cx="20" cy="24" r="10" stroke="#22D3EE" strokeOpacity="0.65" strokeWidth="1.6" />
    <circle cx="20" cy="24" r="15.5" stroke="#22D3EE" strokeOpacity="0.35" strokeWidth="1.3" />
    <line x1="20" y1="24" x2="38" y2="10" stroke="currentColor" strokeOpacity="0.7" strokeWidth="1.4" />
    <line x1="20" y1="24" x2="42" y2="28" stroke="currentColor" strokeOpacity="0.7" strokeWidth="1.4" />
    <line x1="38" y1="10" x2="42" y2="28" stroke="currentColor" strokeOpacity="0.5" strokeWidth="1.2" />
    <line x1="42" y1="28" x2="34" y2="41" stroke="currentColor" strokeOpacity="0.5" strokeWidth="1.2" />
    <circle cx="38" cy="10" r="3" fill="currentColor" />
    <circle cx="42" cy="28" r="3" fill="#22D3EE" />
    <circle cx="34" cy="41" r="2.5" fill="currentColor" />
    <circle cx="20" cy="24" r="2" fill="#22D3EE" />
  </svg>
);

export const TAGLINE = "Intelligence for Scientific Discovery";
