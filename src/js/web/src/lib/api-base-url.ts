export const getApiBaseUrl = () => (typeof window === "undefined" ? "" : window.location.origin)
