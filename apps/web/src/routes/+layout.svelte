<script lang="ts">
  import {
    dataRoute,
    documentsRoute,
    legislativeRoute,
    homeRoute,
    methodologyRoute,
    searchRoute,
    sourcesRoute,
  } from '$lib/navigation';
</script>

<svelte:head>
  <meta name="theme-color" content="#f4efe7" />
</svelte:head>

<div class="shell">
  <header class="topbar">
    <a class="brand" href={homeRoute()}>
      <span class="brand-mark">FonteAberta</span>
      <small>dados publicos oficiais</small>
    </a>

    <nav class="topnav" aria-label="Principal">
      <a href={homeRoute()}>Inicio</a>
      <a href={searchRoute()}>Busca</a>
      <a href={documentsRoute()}>Documentos</a>
      <a href={legislativeRoute()}>Legislativo</a>
      <a href={sourcesRoute()}>Fontes</a>
      <a href={dataRoute()}>Dados</a>
      <a href={methodologyRoute()}>Metodologia</a>
    </nav>
  </header>

  <main class="content">
    <slot />
  </main>

  <footer class="footer">
    <div>
      <span class="badge badge-accent">V1 presidencial 2026</span>
      <p>
        Fato &gt; Evidencia &gt; Fonte oficial
      </p>
    </div>

    <p class="soft">Resposta publica com provenance rastreavel.</p>
  </footer>
</div>

<style>
  :global(:root) {
    color-scheme: light;
    --bg: #f4efe7;
    --surface: rgba(255, 255, 255, 0.68);
    --surface-strong: rgba(255, 255, 255, 0.9);
    --text: #102033;
    --muted: #5e6879;
    --line: rgba(16, 32, 51, 0.14);
    --accent: #0f766e;
    --accent-strong: #134e4a;
    --accent-soft: rgba(15, 118, 110, 0.12);
    --warm: #b45309;
    --shadow: 0 28px 70px rgba(22, 33, 48, 0.12);
  }

  :global(html) {
    background: var(--bg);
  }

  :global(body) {
    margin: 0;
    min-height: 100vh;
    color: var(--text);
    font-family:
      "IBM Plex Sans",
      "Avenir Next",
      "Segoe UI",
      sans-serif;
    background:
      radial-gradient(circle at top left, rgba(15, 118, 110, 0.16), transparent 28%),
      radial-gradient(circle at top right, rgba(180, 83, 9, 0.12), transparent 26%),
      linear-gradient(180deg, #f6f1e9 0%, #fbfaf7 100%);
  }

  :global(*),
  :global(*::before),
  :global(*::after) {
    box-sizing: border-box;
  }

  :global(a) {
    color: inherit;
    text-decoration: none;
  }

  :global(a:hover) {
    color: var(--accent-strong);
  }

  :global(button),
  :global(input),
  :global(select),
  :global(textarea) {
    font: inherit;
  }

  :global(.shell) {
    min-height: 100vh;
  }

  :global(.topbar) {
    width: min(calc(100% - 2rem), 1180px);
    margin: 0 auto;
    padding: 1rem 0 0;
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 1rem;
    position: sticky;
    top: 0;
    z-index: 20;
  }

  :global(.brand) {
    display: flex;
    flex-direction: column;
    gap: 0.15rem;
  }

  :global(.brand-mark) {
    font-size: 1.12rem;
    font-weight: 700;
    letter-spacing: -0.04em;
  }

  :global(.brand small) {
    color: var(--muted);
    font-size: 0.84rem;
  }

  :global(.topnav) {
    display: flex;
    flex-wrap: wrap;
    gap: 0.4rem;
    padding: 0.4rem;
    border-radius: 999px;
    border: 1px solid var(--line);
    background: var(--surface);
    box-shadow: var(--shadow);
    backdrop-filter: blur(14px);
  }

  :global(.topnav a) {
    padding: 0.68rem 0.95rem;
    border-radius: 999px;
    color: var(--muted);
    transition:
      background-color 0.18s ease,
      color 0.18s ease,
      transform 0.18s ease;
  }

  :global(.topnav a:hover) {
    background: var(--accent-soft);
    color: var(--accent-strong);
    transform: translateY(-1px);
  }

  :global(.content) {
    width: min(calc(100% - 2rem), 1180px);
    margin: 0 auto;
    padding: 1.5rem 0 3.5rem;
  }

  :global(.hero) {
    display: grid;
    gap: 1rem;
    grid-template-columns: minmax(0, 1.6fr) minmax(320px, 0.9fr);
    align-items: stretch;
    margin-top: 1.5rem;
  }

  :global(.eyebrow) {
    margin: 0 0 0.5rem;
    color: var(--muted);
    text-transform: uppercase;
    letter-spacing: 0.18em;
    font-size: 0.72rem;
  }

  :global(h1) {
    margin: 0;
    font-size: clamp(2.65rem, 7vw, 5.8rem);
    line-height: 0.94;
    letter-spacing: -0.06em;
  }

  :global(h2) {
    margin: 0;
    font-size: clamp(1.4rem, 2vw, 2rem);
    line-height: 1.05;
    letter-spacing: -0.04em;
  }

  :global(.lead) {
    margin: 0;
    max-width: 62ch;
    color: var(--muted);
    font-size: clamp(1rem, 1.8vw, 1.12rem);
    line-height: 1.7;
  }

  :global(.card) {
    border-radius: 26px;
    border: 1px solid var(--line);
    background: var(--surface);
    box-shadow: var(--shadow);
    backdrop-filter: blur(14px);
  }

  :global(.card-strong) {
    background: var(--surface-strong);
  }

  :global(.card-pad) {
    padding: 1.2rem;
  }

  :global(.grid) {
    display: grid;
    gap: 1rem;
  }

  :global(.grid-2) {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  :global(.grid-3) {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }

  :global(.stack) {
    display: grid;
    gap: 0.9rem;
  }

  :global(.toolbar) {
    display: flex;
    flex-wrap: wrap;
    gap: 0.75rem;
    align-items: center;
  }

  :global(.button),
  :global(.button-secondary) {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: 0.5rem;
    padding: 0.85rem 1.05rem;
    border-radius: 999px;
    border: 1px solid transparent;
    font-weight: 600;
    transition:
      transform 0.18s ease,
      background-color 0.18s ease,
      border-color 0.18s ease;
  }

  :global(.button) {
    background: var(--accent-strong);
    color: #fff;
  }

  :global(.button:hover) {
    background: var(--accent);
    color: #fff;
    transform: translateY(-1px);
  }

  :global(.button-secondary) {
    border-color: var(--line);
    background: rgba(255, 255, 255, 0.56);
    color: var(--text);
  }

  :global(.button-secondary:hover) {
    border-color: rgba(15, 118, 110, 0.24);
    background: rgba(255, 255, 255, 0.9);
    color: var(--accent-strong);
    transform: translateY(-1px);
  }

  :global(.badge) {
    display: inline-flex;
    align-items: center;
    gap: 0.35rem;
    padding: 0.38rem 0.65rem;
    border-radius: 999px;
    border: 1px solid var(--line);
    background: rgba(255, 255, 255, 0.62);
    color: var(--muted);
    font-size: 0.82rem;
  }

  :global(.badge-accent) {
    border-color: rgba(15, 118, 110, 0.18);
    background: var(--accent-soft);
    color: var(--accent-strong);
  }

  :global(.metric) {
    padding: 1rem;
    border-radius: 22px;
    border: 1px solid var(--line);
    background: rgba(255, 255, 255, 0.68);
  }

  :global(.metric-label) {
    margin: 0 0 0.35rem;
    color: var(--muted);
    text-transform: uppercase;
    letter-spacing: 0.1em;
    font-size: 0.72rem;
  }

  :global(.metric-value) {
    margin: 0;
    font-size: clamp(1.45rem, 2.8vw, 2.2rem);
    line-height: 1.05;
    letter-spacing: -0.05em;
  }

  :global(.metric-note) {
    margin: 0.45rem 0 0;
    color: var(--muted);
    font-size: 0.92rem;
    line-height: 1.55;
  }

  :global(.section-title) {
    display: flex;
    justify-content: space-between;
    align-items: end;
    gap: 0.8rem;
    margin: 0 0 0.85rem;
  }

  :global(.section-title p) {
    margin: 0;
    color: var(--muted);
  }

  :global(.section) {
    padding: 1.2rem;
  }

  :global(.panel-title) {
    margin: 0 0 0.4rem;
    color: var(--muted);
    text-transform: uppercase;
    letter-spacing: 0.12em;
    font-size: 0.92rem;
  }

  :global(.list) {
    margin: 0;
    padding: 0;
    list-style: none;
  }

  :global(.list li) {
    display: flex;
    justify-content: space-between;
    gap: 1rem;
    padding: 0.8rem 0;
    border-bottom: 1px solid var(--line);
  }

  :global(.list li:last-child) {
    border-bottom: 0;
  }

  :global(.table-wrap) {
    overflow: auto;
    border-radius: 24px;
    border: 1px solid var(--line);
    background: rgba(255, 255, 255, 0.72);
  }

  :global(table) {
    width: 100%;
    min-width: 760px;
    border-collapse: collapse;
  }

  :global(th),
  :global(td) {
    padding: 0.9rem 1rem;
    border-bottom: 1px solid var(--line);
    text-align: left;
    vertical-align: top;
  }

  :global(th) {
    position: sticky;
    top: 0;
    background: rgba(244, 239, 231, 0.95);
    color: var(--muted);
    text-transform: uppercase;
    letter-spacing: 0.1em;
    font-size: 0.74rem;
  }

  :global(tr:last-child td) {
    border-bottom: 0;
  }

  :global(code),
  :global(kbd) {
    font-family:
      ui-monospace,
      SFMono-Regular,
      Menlo,
      Consolas,
      monospace;
  }

  :global(.soft) {
    color: var(--muted);
  }

  :global(.quote) {
    margin: 0;
    padding: 1rem 1.1rem;
    border-left: 4px solid var(--accent-strong);
    border-radius: 0 18px 18px 0;
    background: rgba(15, 118, 110, 0.08);
    line-height: 1.7;
  }

  :global(.aside) {
    display: grid;
    gap: 0.8rem;
  }

  :global(.note) {
    color: var(--muted);
    line-height: 1.6;
    font-size: 0.92rem;
  }

  :global(.footer) {
    width: min(calc(100% - 2rem), 1180px);
    margin: 0 auto;
    padding: 0 0 2rem;
    display: flex;
    justify-content: space-between;
    align-items: end;
    gap: 1rem;
  }

  :global(.footer p) {
    margin: 0.45rem 0 0;
  }

  @media (max-width: 900px) {
    :global(.hero),
    :global(.grid-2),
    :global(.grid-3) {
      grid-template-columns: 1fr;
    }

    :global(.topbar) {
      position: static;
      flex-direction: column;
      align-items: stretch;
    }

    :global(.footer) {
      flex-direction: column;
      align-items: start;
    }
  }

  @media (prefers-reduced-motion: reduce) {
    :global(*),
    :global(*::before),
    :global(*::after) {
      transition: none !important;
      scroll-behavior: auto !important;
    }
  }
</style>
