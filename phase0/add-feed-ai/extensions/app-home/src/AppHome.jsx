import { render } from "preact";
import { LocationProvider, ErrorBoundary, Router, Route } from "preact-iso";

import HomePage from "./pages/HomePage.jsx";

export default async () => {
  render(<App />, document.body);
};

function App() {
  return (
    <LocationProvider>
      <ErrorBoundary>
        <Router>
          <Route path="/" component={HomePage} />
        </Router>
      </ErrorBoundary>
    </LocationProvider>
  );
}
