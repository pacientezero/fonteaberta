<svelte:head>
  <title>FonteAberta Bootstrap</title>
  <meta
    name="description"
    content="Bootstrap skeleton for the FonteAberta open data platform."
  />
</svelte:head>

<script lang="ts">
  const services = [
    { name: "PostgreSQL + pgvector", port: "5432" },
    { name: "Directus", port: "8055" },
    { name: "Redis", port: "6379" },
    { name: "n8n", port: "5678" },
    { name: "Kestra", port: "8080" },
    { name: "Ollama", port: "11434" },
    { name: "AI API", port: "8000" },
  ];

  const phases = [
    "Bootstrap",
    "Data governance",
    "TSE V1",
    "Public UI",
    "Documents and RAG",
    "Expansion",
    "Hardening",
  ];
</script>

<div class="page">
  <section class="hero">
    <p class="kicker">Phase 00</p>
    <h1>FonteAberta</h1>
    <p class="lede">
      Monorepo bootstrap for an open platform of official public data with
      auditability, provenance, and reproducible calculations.
    </p>

    <div class="actions">
      <a href="http://localhost:8000/health">API health</a>
      <a href="http://localhost:8055">Directus</a>
      <a href="http://localhost:5678">n8n</a>
      <a href="http://localhost:8080">Kestra</a>
    </div>
  </section>

  <section class="grid">
    <article class="panel">
      <h2>Services</h2>
      <ul>
        {#each services as service}
          <li>
            <span>{service.name}</span>
            <strong>{service.port}</strong>
          </li>
        {/each}
      </ul>
    </article>

    <article class="panel">
      <h2>Delivery order</h2>
      <ol>
        {#each phases as phase}
          <li>{phase}</li>
        {/each}
      </ol>
    </article>
  </section>
</div>

<style>
  :global(body) {
    margin: 0;
    font-family:
      "IBM Plex Sans",
      "Inter",
      "Segoe UI",
      sans-serif;
    background:
      radial-gradient(circle at top left, rgba(72, 112, 255, 0.18), transparent 28%),
      radial-gradient(circle at top right, rgba(0, 180, 160, 0.14), transparent 24%),
      linear-gradient(180deg, #09111f 0%, #101826 45%, #f3f6fb 45%, #f3f6fb 100%);
    color: #0b1020;
  }

  .page {
    min-height: 100vh;
    display: grid;
    gap: 2rem;
    padding: 4rem 1.5rem 3rem;
    box-sizing: border-box;
  }

  .hero,
  .panel {
    width: min(100%, 1120px);
    margin: 0 auto;
  }

  .hero {
    color: #f5f7fb;
    padding: 2rem 0 4rem;
  }

  .kicker {
    text-transform: uppercase;
    letter-spacing: 0.18em;
    font-size: 0.75rem;
    color: #8eb5ff;
  }

  h1 {
    margin: 0.35rem 0 0.75rem;
    font-size: clamp(3rem, 8vw, 6.8rem);
    line-height: 0.95;
    letter-spacing: -0.06em;
    max-width: 10ch;
  }

  .lede {
    margin: 0;
    max-width: 64ch;
    font-size: clamp(1.05rem, 2vw, 1.2rem);
    line-height: 1.7;
    color: rgba(245, 247, 251, 0.78);
  }

  .actions {
    display: flex;
    flex-wrap: wrap;
    gap: 0.75rem;
    margin-top: 1.75rem;
  }

  .actions a {
    color: #09111f;
    text-decoration: none;
    background: #f3f6fb;
    border-radius: 999px;
    padding: 0.8rem 1rem;
    font-weight: 600;
    box-shadow: 0 12px 30px rgba(0, 0, 0, 0.16);
  }

  .grid {
    width: min(100%, 1120px);
    margin: 0 auto;
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 1rem;
  }

  .panel {
    background: rgba(255, 255, 255, 0.84);
    backdrop-filter: blur(12px);
    border: 1px solid rgba(255, 255, 255, 0.5);
    border-radius: 24px;
    padding: 1.25rem 1.25rem 1rem;
    box-shadow: 0 22px 60px rgba(15, 22, 37, 0.12);
  }

  .panel h2 {
    margin: 0 0 1rem;
    font-size: 1rem;
    text-transform: uppercase;
    letter-spacing: 0.12em;
    color: #49566f;
  }

  ul,
  ol {
    margin: 0;
    padding-left: 1.2rem;
  }

  ul {
    list-style: none;
    padding: 0;
  }

  li {
    display: flex;
    justify-content: space-between;
    gap: 1rem;
    padding: 0.75rem 0;
    border-bottom: 1px solid rgba(14, 23, 41, 0.08);
  }

  li:last-child {
    border-bottom: 0;
  }

  strong {
    color: #0c1730;
  }

  @media (max-width: 720px) {
    .page {
      padding-top: 2.5rem;
    }

    .grid {
      grid-template-columns: 1fr;
    }

    .actions a {
      width: 100%;
      text-align: center;
    }
  }
</style>
