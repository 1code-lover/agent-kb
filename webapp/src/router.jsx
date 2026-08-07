import React, { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";

const RouterContext = createContext(null);

function normalizeTarget(target) {
  const value = String(target || "/").trim() || "/";
  if (/^[a-z][a-z0-9+.-]*:/i.test(value) || value.startsWith("//") || value.includes("\\")) {
    return "/";
  }
  return value.startsWith("/") ? value : "/" + value;
}

function readBrowserLocation() {
  return {
    pathname: window.location.pathname || "/",
    search: window.location.search || "",
    hash: window.location.hash || "",
  };
}

function parseHashLocation() {
  const rawHash = window.location.hash.replace(/^#/, "");
  const target = normalizeTarget(rawHash || "/");
  const url = new URL(target, window.location.origin);
  return {
    pathname: url.pathname || "/",
    search: url.search || "",
    hash: "",
  };
}

function buildHashHref(to) {
  return "#" + normalizeTarget(to);
}

function createRouterState(kind) {
  return kind === "hash" ? parseHashLocation() : readBrowserLocation();
}

function RouterProvider({ kind, children }) {
  const [location, setLocation] = useState(() => createRouterState(kind));

  useEffect(() => {
    const eventName = kind === "hash" ? "hashchange" : "popstate";
    const syncLocation = () => setLocation(createRouterState(kind));
    window.addEventListener(eventName, syncLocation);
    if (kind === "browser") {
      window.addEventListener("pushstate", syncLocation);
      window.addEventListener("replacestate", syncLocation);
    }
    syncLocation();
    return () => {
      window.removeEventListener(eventName, syncLocation);
      window.removeEventListener("pushstate", syncLocation);
      window.removeEventListener("replacestate", syncLocation);
    };
  }, [kind]);

  const navigate = useCallback(
    (to, options = {}) => {
      const target = normalizeTarget(to);
      if (kind === "hash") {
        const nextHash = buildHashHref(target);
        if (options.replace) {
          window.location.replace(nextHash);
        } else {
          window.location.hash = nextHash;
        }
        setLocation(parseHashLocation());
        return;
      }

      const method = options.replace ? "replaceState" : "pushState";
      window.history[method](null, "", target);
      setLocation(readBrowserLocation());
    },
    [kind]
  );

  const value = useMemo(() => ({ kind, location, navigate }), [kind, location, navigate]);

  return <RouterContext.Provider value={value}>{children}</RouterContext.Provider>;
}

export function BrowserRouter({ children }) {
  return <RouterProvider kind="browser">{children}</RouterProvider>;
}

export function HashRouter({ children }) {
  return <RouterProvider kind="hash">{children}</RouterProvider>;
}

export function useLocation() {
  const context = useContext(RouterContext);
  if (!context) {
    throw new Error("useLocation must be used inside RouterProvider");
  }
  return context.location;
}

export function useNavigate() {
  const context = useContext(RouterContext);
  if (!context) {
    throw new Error("useNavigate must be used inside RouterProvider");
  }
  return context.navigate;
}

export function Link({ to, replace = false, onClick, children, ...props }) {
  const context = useContext(RouterContext);
  const target = normalizeTarget(to);
  const href = context?.kind === "hash" ? buildHashHref(target) : target;

  const handleClick = (event) => {
    if (onClick) {
      onClick(event);
    }
    if (
      event.defaultPrevented ||
      event.button !== 0 ||
      event.metaKey ||
      event.altKey ||
      event.ctrlKey ||
      event.shiftKey ||
      props.target
    ) {
      return;
    }
    event.preventDefault();
    context?.navigate(target, { replace });
  };

  return (
    <a href={href} onClick={handleClick} {...props}>
      {children}
    </a>
  );
}
