"use strict";
// Browser locale is a preference, not proof of geographic location.
function chooseLocale(preferred, override = "auto") {
  const valid = [];
  for (const item of preferred || []) {
    try { const tag = Intl.getCanonicalLocales(item)[0];
      if (["en", "pt", "es"].includes(tag.split("-")[0])) valid.push(tag);
    } catch (_) { /* malformed browser hints are ignored */ }
  }
  if (override === "auto") return valid[0] || "en";
  if (!["en", "pt", "es"].includes(override)) return valid[0] || "en";
  return valid.find(tag => tag.split("-")[0] === override) || {en:"en",pt:"pt-BR",es:"es"}[override];
}
