import Link from "next/link";
import { Film } from "lucide-react";

export function Brand() {
  return <Link className="brand" href="/" aria-label="Heritage Studio home">
    <span className="brand-icon"><Film size={22} aria-hidden="true" /></span>
    <span>Heritage Studio</span>
  </Link>;
}

export function Footer() {
  return <footer className="site-footer">
    <div className="shell"><span>Heritage Studio</span><span>Family stories on film</span></div>
  </footer>;
}
