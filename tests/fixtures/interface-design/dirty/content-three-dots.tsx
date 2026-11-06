const LOADING_LABEL = "Loading deploys..."; /* expect */

export function DeployList({ deploys, isLoading, ...rest }: Props) {
  const all = [...deploys];
  return (
    <section {...rest}>
      <input type="search" id="q" aria-label="Filter deploys" placeholder="Filter deploys..." />{/* expect */}
      {isLoading ? <p>Fetching...</p> : null}{/* expect */}
      <button onClick={() => retry(...all)}>Retry</button>
      <p>Loading… done</p>
    </section>
  );
}
