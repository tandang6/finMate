// jest-dom adds custom jest matchers for asserting on DOM nodes.
// allows you to do things like:
// expect(element).toHaveTextContent(/react/i)
// learn more: https://github.com/testing-library/jest-dom
import '@testing-library/jest-dom';

jest.mock(
  "react-router-dom",
  () => {
    const React = require("react");
    const RouterContext = React.createContext({
      location: { pathname: "/", state: null },
      navigate: () => {},
    });

    function normalizeEntry(entry) {
      if (typeof entry === "string") {
        return { pathname: entry, state: null };
      }
      return {
        pathname: entry?.pathname ?? "/",
        state: entry?.state ?? null,
      };
    }

    function MemoryRouter({ children, initialEntries = ["/"] }) {
      const [location, setLocation] = React.useState(() =>
        normalizeEntry(initialEntries[initialEntries.length - 1])
      );

      const navigate = React.useCallback((to, options = {}) => {
        if (typeof to === "string") {
          setLocation({ pathname: to, state: options.state ?? null });
        } else {
          setLocation({
            pathname: to?.pathname ?? "/",
            state: to?.state ?? options.state ?? null,
          });
        }
      }, []);

      return (
        <RouterContext.Provider value={{ location, navigate }}>
          {children}
        </RouterContext.Provider>
      );
    }

    function Routes({ children }) {
      const { location } = React.useContext(RouterContext);
      const candidates = React.Children.toArray(children);
      const match =
        candidates.find((child) => child?.props?.path === location.pathname) ??
        candidates.find((child) => child?.props?.path === "*") ??
        candidates[0];
      return match?.props?.element ?? null;
    }

    function Route() {
      return null;
    }

    function Link({ to, children, ...props }) {
      const href = typeof to === "string" ? to : to?.pathname ?? "/";
      return (
        <a href={href} {...props}>
          {children}
        </a>
      );
    }

    function useNavigate() {
      return React.useContext(RouterContext).navigate;
    }

    function useLocation() {
      return React.useContext(RouterContext).location;
    }

    return {
      MemoryRouter,
      Routes,
      Route,
      Link,
      useNavigate,
      useLocation,
    };
  },
  { virtual: true }
);
