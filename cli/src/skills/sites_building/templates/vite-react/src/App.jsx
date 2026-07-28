export default function App() {
  return (
    <>
      <a className="skip-link" href="#main">Skip to content</a>
      <header>
        <p className="eyebrow">Sandwalk Sites</p>
        <h1>Start with the finding that matters.</h1>
        <p className="lede">
          Replace this starter with clear, specific content and purposeful interaction.
        </p>
      </header>
      <main id="main">
        <section aria-labelledby="overview">
          <h2 id="overview">Overview</h2>
          <p>This Vite/React starter produces a static site with relative build assets.</p>
        </section>
      </main>
      <footer><small>Built with Sandwalk.</small></footer>
    </>
  );
}
