import { useState } from "react";
import { ORB_BASE_URL } from "../lib/config";

interface OrbProps {
  reducedMotion: boolean;
  thinking?: boolean;
  className?: string;
  anim?: boolean;
}

/**
 * The glass orb. A 145u layer sits inside an 84u footprint (−30.5u margins),
 * a still plate under a muted looping video that fades in on `loadeddata`.
 * A radial mask plus `mix-blend-mode: screen` melt the black plate into the
 * page, so no square is ever visible. Reduced motion: plate only.
 */
export function Orb({ reducedMotion, thinking = false, className = "", anim = true }: OrbProps) {
  const [videoReady, setVideoReady] = useState(false);
  return (
    <div className={`orb ${thinking ? "is-thinking" : ""} ${className}`} data-anim={anim ? "orb" : undefined} aria-hidden="true">
      <div className="orb-layer">
        <img className="orb-plate" src={`${ORB_BASE_URL}/orb-plate.webp`} alt="" draggable={false} />
        {!reducedMotion && (
          <video
            className={`orb-video ${videoReady ? "is-ready" : ""}`}
            autoPlay
            muted
            loop
            playsInline
            preload="auto"
            poster={`${ORB_BASE_URL}/orb-plate.webp`}
            onLoadedData={() => setVideoReady(true)}
            disablePictureInPicture
          >
            <source src={`${ORB_BASE_URL}/orb-loop.webm`} type="video/webm" />
            <source src={`${ORB_BASE_URL}/orb-loop.mp4`} type="video/mp4" />
          </video>
        )}
      </div>
    </div>
  );
}
