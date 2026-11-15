// Cairn theme: dark, light or system, chosen in Settings → Appearance and kept per viewer (localStorage).
// Loaded in <head> by the app and by plugin pages, so the theme applies before the first paint and follows changes
// made in another window or frame.
(function () {
  var KEY = 'cairn.theme'
  var media = window.matchMedia ? window.matchMedia('(prefers-color-scheme: light)') : null
  var fallback = 'dark' // used when storage is blocked
  function choice() { try { return localStorage.getItem(KEY) || fallback } catch (e) { return fallback } }
  function apply() {
    var c = choice()
    var light = c === 'light' || (c === 'system' && media && media.matches)
    document.documentElement.setAttribute('data-theme', light ? 'light' : 'dark')
  }
  window.b3dTheme = {
    get: choice,
    set: function (c) { fallback = c; try { localStorage.setItem(KEY, c) } catch (e) { /* storage blocked: this page only */ } apply() },
  }
  apply()
  window.addEventListener('storage', function (e) { if (e.key === KEY) apply() })
  if (media && media.addEventListener) media.addEventListener('change', apply)
})()
