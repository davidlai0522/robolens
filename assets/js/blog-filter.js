/* JarvisForResearchers — client-side keyword + date filter for the blog post listing.
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

    // ── Build suggestion corpus from article titles + excerpt paper names ────
    const suggestionSet = new Set();
    articles.forEach((a) => {
      // Digest title
      const heading = a.querySelector("h2, h3");
      if (heading) suggestionSet.add(heading.textContent.trim());

      // Paper names mentioned in the excerpt (comma-separated after "papers this week:")
      const excerpt = a.querySelector(".md-post__excerpt")?.textContent ?? "";
      const afterColon = excerpt.replace(/^\d+\s+papers?\s+this\s+week\s*:\s*/i, "");
      afterColon.split(/,\s*/).forEach((phrase) => {
        const trimmed = phrase.replace(/\.$/, "").trim();
        if (trimmed.length >= 8) suggestionSet.add(trimmed);
      });

      // Tags
      a.querySelectorAll(".md-tag").forEach((el) => {
        const t = el.textContent.trim();
        if (t.length >= 3) suggestionSet.add(t);
      });
    });
    const allSuggestions = Array.from(suggestionSet);

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
          aria-autocomplete="list"
          aria-controls="rl-suggestions"
          aria-expanded="false"
          role="combobox"
        />
        <ul id="rl-suggestions" role="listbox" aria-label="Suggestions" hidden></ul>
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

    const searchInput   = document.getElementById("rl-search");
    const suggestList   = document.getElementById("rl-suggestions");
    let activeIndex     = -1;

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

    // ── Autocomplete helpers ──────────────────────────────────────────────────
    function closeSuggestions() {
      suggestList.hidden = true;
      suggestList.innerHTML = "";
      activeIndex = -1;
      searchInput.setAttribute("aria-expanded", "false");
    }

    function selectSuggestion(text) {
      searchInput.value = text;
      closeSuggestions();
      applyFilter();
    }

    function openSuggestions(matches) {
      suggestList.innerHTML = "";
      activeIndex = -1;
      if (!matches.length) { closeSuggestions(); return; }
      matches.forEach((text, i) => {
        const li = document.createElement("li");
        li.id = `rl-suggestion-${i}`;
        li.setAttribute("role", "option");
        li.setAttribute("aria-selected", "false");
        li.textContent = text;
        li.addEventListener("mousedown", (e) => {
          e.preventDefault(); // keep focus on input
          selectSuggestion(text);
        });
        suggestList.appendChild(li);
      });
      suggestList.hidden = false;
      searchInput.setAttribute("aria-expanded", "true");
    }

    function setActive(index) {
      const items = suggestList.querySelectorAll("li");
      items.forEach((li, i) => {
        li.setAttribute("aria-selected", i === index ? "true" : "false");
        li.classList.toggle("rl-suggestion--active", i === index);
      });
      activeIndex = index;
      if (index >= 0 && items[index]) {
        searchInput.setAttribute("aria-activedescendant", items[index].id);
      } else {
        searchInput.removeAttribute("aria-activedescendant");
      }
    }

    // ── Filter function ──────────────────────────────────────────────────────
    function applyFilter() {
      const query = searchInput.value.trim().toLowerCase();
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
    searchInput.addEventListener("input", function () {
      applyFilter();
      const q = this.value.trim().toLowerCase();
      if (q.length < 1) { closeSuggestions(); return; }
      const matches = allSuggestions
        .filter((s) => s.toLowerCase().includes(q))
        .slice(0, 8);
      openSuggestions(matches);
    });

    searchInput.addEventListener("keydown", function (e) {
      const items = suggestList.querySelectorAll("li");
      if (suggestList.hidden || !items.length) return;
      if (e.key === "ArrowDown") {
        e.preventDefault();
        setActive(Math.min(activeIndex + 1, items.length - 1));
      } else if (e.key === "ArrowUp") {
        e.preventDefault();
        setActive(Math.max(activeIndex - 1, -1));
      } else if (e.key === "Enter" && activeIndex >= 0) {
        e.preventDefault();
        selectSuggestion(items[activeIndex].textContent);
      } else if (e.key === "Escape") {
        closeSuggestions();
      }
    });

    searchInput.addEventListener("blur", function () {
      // Small delay so mousedown on a suggestion fires first
      setTimeout(closeSuggestions, 150);
    });

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
