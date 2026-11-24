// One Web Animations timeline for the entrance. Every element that takes part
// carries data-anim="<group>". Delays are in ms from the start.

const EASE = "cubic-bezier(.2,.8,.2,1)";

export function prefersReducedMotion(): boolean {
  return typeof window !== "undefined" && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}

function each(root: HTMLElement, group: string): HTMLElement[] {
  return Array.from(root.querySelectorAll<HTMLElement>(`[data-anim="${group}"]`));
}

function rise(el: HTMLElement, delay: number, distance = "calc(10 * var(--u))", duration = 620) {
  return el.animate(
    [
      { opacity: 0, transform: `translateY(${distance})` },
      { opacity: 1, transform: "translateY(0)" },
    ],
    { duration, delay, easing: EASE, fill: "both" },
  );
}

export function runEntrance(root: HTMLElement): Animation[] {
  const anims: Animation[] = [];

  each(root, "rail").forEach((el, i) => anims.push(rise(el, i * 40, "calc(8 * var(--u))", 520)));
  each(root, "top").forEach((el, i) => anims.push(rise(el, 120 + i * 50, "calc(-8 * var(--u))", 520)));

  each(root, "orb").forEach((el) => {
    anims.push(
      el.animate(
        [
          { opacity: 0, transform: "scale(.92)" },
          { opacity: 1, transform: "scale(1)" },
        ],
        { duration: 900, delay: 250, easing: EASE, fill: "both" },
      ),
    );
    const layer = el.querySelector<HTMLElement>(".orb-layer");
    if (layer) {
      anims.push(
        layer.animate(
          [{ clipPath: "circle(0% at 50% 50%)" }, { clipPath: "circle(75% at 50% 50%)" }],
          { duration: 900, delay: 250, easing: EASE, fill: "both" },
        ),
      );
    }
  });

  each(root, "greet").forEach((el) =>
    anims.push(el.animate([{ opacity: 0 }, { opacity: 1 }], { duration: 600, delay: 550, easing: EASE, fill: "both" })),
  );

  each(root, "word").forEach((el, i) =>
    anims.push(
      el.animate([{ transform: "translateY(105%)" }, { transform: "translateY(0)" }], {
        duration: 700,
        delay: 700 + i * 80,
        easing: EASE,
        fill: "both",
      }),
    ),
  );

  each(root, "settle").forEach((el, i) => anims.push(rise(el, 1000 + i * 110)));
  each(root, "card").forEach((el, i) => anims.push(rise(el, 1220 + i * 80)));
  each(root, "hist").forEach((el, i) => anims.push(rise(el, 1450 + i * 60, "calc(6 * var(--u))", 520)));

  return anims;
}
