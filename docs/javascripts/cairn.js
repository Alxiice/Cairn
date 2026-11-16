// Home page motion: the hero's layers follow the pointer at their depth (far layers lag behind the scroll), and the showcase screenshot
// straightens as it scrolls into view. Runs on every page change (Material's instant navigation).
function cairnHome() {
  const hero = document.querySelector(".cairn-hero")
  if (!hero || hero.dataset.ready || matchMedia("(prefers-reduced-motion: reduce)").matches) return
  hero.dataset.ready = "1"
  const layers = [...hero.querySelectorAll("[data-depth]")].map((el) => [el, Number(el.dataset.depth)])
  const shot = document.querySelector(".cairn-showcase img")
  let mx = 0, my = 0, tx = 0, ty = 0, frame = 0

  const draw = () => {
    frame = 0
    if (!hero.isConnected) return removeEventListener("scroll", queue)
    tx += (mx - tx) * 0.08
    ty += (my - ty) * 0.08
    const sy = scrollY
    for (const [el, d] of layers) el.style.transform = `translate3d(${-tx * d * 60}px, ${-ty * d * 40 + sy * (0.45 - d)}px, 0)`
    if (shot) {
      const k = Math.min(1, Math.max(0, 1.4 * (1 - shot.getBoundingClientRect().top / innerHeight)))
      shot.style.transform = `rotateX(${14 * (1 - k)}deg) scale(${0.96 + 0.04 * k})`
    }
    if (Math.abs(mx - tx) > 0.001 || Math.abs(my - ty) > 0.001) queue()
  }
  const queue = () => { if (!frame) frame = requestAnimationFrame(draw) }

  hero.addEventListener("pointermove", (e) => {
    const r = hero.getBoundingClientRect()
    mx = (e.clientX - r.left) / r.width - 0.5
    my = (e.clientY - r.top) / r.height - 0.5
    queue()
  })
  hero.addEventListener("pointerleave", () => { mx = my = 0; queue() })
  addEventListener("scroll", queue, { passive: true })
  queue()
}

// Slideshow: tabs, auto-advance (paused on hover, on focus and off screen), and a tilt towards the cursor as if the
// mouse pressed the picture down there (rotation only, the centre stays put).
function cairnSlides() {
  const reduced = matchMedia("(prefers-reduced-motion: reduce)").matches
  for (const show of document.querySelectorAll(".cairn-slides:not([data-ready])")) {
    show.dataset.ready = "1"
    const tabs = [...show.querySelectorAll(".cairn-slides__tab")]
    const frames = [...show.querySelectorAll(".cairn-slides__frame")]
    const caption = show.querySelector(".cairn-slides__caption")
    const interval = Number(show.dataset.interval) || 5000
    show.style.setProperty("--cairn-interval", `${interval}ms`)
    let current = 0, timer = null

    const select = (i) => {
      current = (i + tabs.length) % tabs.length
      tabs.forEach((t, n) => { t.classList.toggle("is-active", n === current); t.setAttribute("aria-selected", String(n === current)) })
      frames.forEach((f, n) => f.classList.toggle("is-active", n === current))
      caption.textContent = tabs[current].dataset.caption
    }
    const stop = () => { clearInterval(timer); timer = null; show.classList.add("is-paused") }
    const start = () => {
      stop()
      if (reduced || !show.isConnected) return
      show.classList.remove("is-paused")
      // restart the active tab's progress bar
      const t = tabs[current]; t.classList.remove("is-active"); void t.offsetWidth; t.classList.add("is-active")
      timer = setInterval(() => select(current + 1), interval)
    }
    tabs.forEach((t, n) => t.addEventListener("click", () => { select(n); start() }))
    show.addEventListener("mouseenter", stop)
    show.addEventListener("mouseleave", start)
    show.addEventListener("focusin", stop)
    show.addEventListener("focusout", start)
    stop()
    new IntersectionObserver(([e]) => (e.isIntersecting ? start() : stop()), { threshold: 0.3 }).observe(show)
  }

  if (reduced || !matchMedia("(hover: hover)").matches) return
  const MAX_TILT = 8  // degrees at the edges
  for (const el of document.querySelectorAll("[data-tilt]:not([data-ready])")) {
    el.dataset.ready = "1"
    el.addEventListener("pointermove", (e) => {
      const r = el.getBoundingClientRect()
      const x = (e.clientX - r.left) / r.width - 0.5
      const y = (e.clientY - r.top) / r.height - 0.5
      el.classList.add("is-tilting")
      el.style.setProperty("--rx", `${(-y * 2 * MAX_TILT).toFixed(2)}deg`)
      el.style.setProperty("--ry", `${(x * 2 * MAX_TILT).toFixed(2)}deg`)
    })
    el.addEventListener("pointerleave", () => {
      el.classList.remove("is-tilting")
      el.style.setProperty("--rx", "0deg")
      el.style.setProperty("--ry", "0deg")
    })
  }
}

const cairnPage = () => { cairnHome(); cairnSlides() }
if (window.document$) document$.subscribe(cairnPage)
else document.addEventListener("DOMContentLoaded", cairnPage)
