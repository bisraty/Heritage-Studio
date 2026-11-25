"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { MotionConfig, motion } from "motion/react";
import { AudioLines, Clapperboard, Film, Images, LockKeyhole } from "lucide-react";
import { storageKey } from "./api";
import { Brand, Footer } from "./chrome";

function Welcome({ resume }: { resume: boolean }) {
  const features = [
    { image: "voice", Icon: AudioLines, title: "Share your memory", description: "Start with a story in English or Amharic." },
    { image: "photos", Icon: Images, title: "Bring your photos", description: "Use family photographs as references for the illustrations." },
    { image: "edit", Icon: Clapperboard, title: "Review your film", description: "Edit the storyboard and listen to the narration before rendering." },
  ];
  return <>
    <section className="hero">
      <motion.div className="hero-content" initial={{ opacity: .75, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: .4 }}>
        <h1>Turn treasured family memories into <em>timeless short films.</em></h1>
        <p>Tell your story, add your photos, and make a film your family can keep.</p>
        <div className="actions justify-center">
          <Link className="button primary" href="/studio"><Film size={18} /> {resume ? "Resume Your Story" : "Start Your Story"}</Link>
          <a className="button secondary" href="#how-it-works">How It Works</a>
        </div>
      </motion.div>
    </section>
    <section className="feature-grid" id="how-it-works" aria-label="How it works">
      {features.map(({ image, Icon, title, description }, index) => (
        <motion.article className="feature panel" key={image} initial={{ opacity: .65, y: 14 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: .35, delay: index * .07 }}>
          <div className="feature-image" style={{ backgroundImage: `url('/stitch/${image}.webp')` }} />
          <div className="feature-body"><Icon className="gold" size={21} /><h2>{title}</h2><p>{description}</p></div>
        </motion.article>
      ))}
    </section>
  </>;
}

export default function Home() {
  const [resume, setResume] = useState(false);
  useEffect(() => {
    setResume(Boolean(sessionStorage.getItem(storageKey)));
  }, []);
  return <MotionConfig reducedMotion="user">
    <a href="#studio-main" className="skip-link">Skip to content</a>
    <header className="site-header landing-header">
      <div className="shell brand-bar">
        <Brand />
        <span className="local-mark"><LockKeyhole size={14} /> Local Studio</span>
      </div>
    </header>
    <main className="shell main-content" id="studio-main">
      <Welcome resume={resume} />
    </main>
    <Footer />
  </MotionConfig>;
}
