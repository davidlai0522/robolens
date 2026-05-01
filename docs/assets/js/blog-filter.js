/* RoboLens — client-side keyword + date filter for the blog post listing.
 *
 * Injects a filter bar above the post cards on any page that contains
 * MkDocs Material blog articles (.md-post elements).
 * Works with MkDocs Material's instant navigation via document$.subscribe().
 */
(function () {
  "use strict";

  function init() {
    // Only run on pages that list posts (index, archive, category pages)
    const articles = Array.from(document.querySelectorAll("article.md-post"));
    if (!articles.length) return;

    // Avoid double-injecting when navigating back to the same page
    if (document.getElementById("rl-filter-bar")) return;

    // ── Collect unique years from article <time datetime="YYYY-MM-DD"> ──────
    const years = new Set();
    articles.forEach((a) => {
      const t = a.querySelector("time[datetime]");
      if (t) {
        const y = (t.getAttribute("datetime") || "").slice(0, 4);
        if (/^\d{4}$/.test(y)) years.add(y);
      }
    });
    const sortedYears = Array.from(years).sort().reverse();

    // ── Build filter bar ─────────────────────────────────────────────────────
    const bar = document.createElement("div");
    bar.id = "rl-filter-bar";
    bar.setAttribute("role", "search");
    bar.innerHTML = `
      <div class="rl-search-wrap">
        <svg class="rl-search-icon" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24">
          <path d="M9.5 3A6.5 6.5 0 0 1 16 9.5c0 1.61-.59 3.09-1.56 4.23l.27.27h.79l5 5-1.5 1.5-5-5v-.79l-.27-.27A6.516 6.516 0 0 1 9.5 16 6.5 6.5 0 0 1 3 9.5 6.5 6.5 0 0 1 9.5 3m0 2C7 5 5 7 5 9.5S7 14 9.5 14 14 12 14 9.5 12 5 9.5 5Z"/>
        </svg>
        <input
          type="search"
          id="rl-search"
          placeholder="Search posts…"
          autocomplete="off"
          aria-label="Search posts by keyword"
        />
      </div>
      <select id="rl-year" aria-label="Filter by year" title="Filter by year">
        <option value="">All years</option>
        ${sortedYears.map((y) => `<option value="${y}">${y}</option>`).join("")}
      </select>
      <span class="rl-count" id="rl-count" aria-live="polite"></span>
    `;

    // Insert before the first post, inside its parent container
    const container = articles[0].parentElement;
    container.insertBefore(bar, articles[0]);

    // ── Helpers ──────────────────────────────────────────────────────────────
    function postText(article) {
      const title = article.querySelector("h2, h3")?.textContent ?? "";
      const excerpt = article.querySelector(".md-post__excerpt")?.textContent ?? "";
      const tags = Array.from(article.querySelectorAll(".md-tag"))
        .map((el) => el.textContent)
        .join(" ");
      return (title + " " + excerpt + " " + tags).toLowerCase();
    }

    function postYear(article) {
      const t = article.querySelector("time[datetime]");
      return t ? (t.getAttribute("datetime") ?? "").slice(0, 4) : "";
    }

    // ── Filter function ──────────────────────────────────────────────────────
    function applyFilter() {
      const query = document.getElementById("rl-search").value.trim().toLowerCase();
      const year  = document.getElementById("rl-year").value;
      let shown   = 0;

      articles.forEach((a) => {
        const ok = (!query || postText(a).includes(query))
                && (!year  || postYear(a) === year);
        a.style.display = ok ? "" : "none";
        if (ok) shown++;
      });

      const badge = document.getElementById("rl-count");
      if (badge) {
        badge.textContent = (shown < articles.length)
          ? `${shown} / ${articles.length} posts`
          : "";
      }
    }

    // ── Wire events ──────────────────────────────────────────────────────────
    document.getElementById("rl-search").addEventListener("input", applyFilter);
    document.getElementById("rl-year").addEventListener("change", applyFilter);
  }

  // Initial load
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }

  // MkDocs Material instant navigation — document$ is an RxJS observable
  // exposed on window after the theme JS loads.
  if (typeof window.document$ !== "undefined") {
    window.document$.subscribe(init);
  } else {
    // Fallback: wait for the theme to expose document$ then subscribe
    window.addEventListener("load", function () {
      if (typeof window.document$ !== "undefined") {
        window.document$.subscribe(init);
      }
    });
  }
})();
