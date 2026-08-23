import { render } from "preact";
import { useErrorBoundary } from "preact/hooks";
import HomePage from "./pages/HomePage.jsx";

function Root() {
  const [error, reset] = useErrorBoundary();
  if (error) {
    return (
      <s-page heading="AdFeed AI · ERROR">
        <s-banner tone="critical">
          <s-stack gap="small">
            <s-text>UI crashed: {String(error?.message || error)}</s-text>
            <s-button variant="primary" onClick={reset}>
              Retry
            </s-button>
          </s-stack>
        </s-banner>
      </s-page>
    );
  }
  return <HomePage />;
}

export default async () => {
  render(<Root />, document.body);
};
